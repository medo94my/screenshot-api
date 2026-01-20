#!/bin/bash
#
# Deploy Screenshot API to VPS using Docker
#
# Usage:
#   ./deploy_to_vps.sh [server_ip] [ssh_user]
#
# Example:
#   ./deploy_to_vps.sh 123.456.789.012 root
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Deploying Screenshot API to VPS${NC}"
echo ""

# Get server IP and user from arguments or prompt
SERVER_IP=${1:-""}
SSH_USER=${2:-"root"}

if [ -z "$SERVER_IP" ]; then
    echo -e "${YELLOW}Enter server IP address:${NC} "
    read SERVER_IP
fi

if [ -z "$SSH_USER" ]; then
    SSH_USER="root"
fi

echo ""
echo "Server: $SSH_USER@$SERVER_IP"
echo ""

# Build Docker image locally
echo -e "${GREEN}[1/5] Building Docker image...${NC}"
docker build -t screenshot-api:latest . 2>&1 | tail -20
echo -e "${GREEN}✓ Image built successfully${NC}"

# Save image to tar file
echo ""
echo -e "${GREEN}[2/5] Saving Docker image...${NC}"
docker save screenshot-api:latest -o screenshot-api.tar
echo -e "${GREEN}✓ Image saved to screenshot-api.tar${NC}"

# Upload to VPS
echo ""
echo -e "${GREEN}[3/5] Uploading to VPS...${NC}"
scp -o StrictHostKeyChecking=no screenshot-api.tar $SSH_USER@$SERVER_IP:/tmp/
echo -e "${GREEN}✓ Image uploaded${NC}"

# Deploy on VPS
echo ""
echo -e "${GREEN}[4/5] Deploying on VPS...${NC}"
ssh -o StrictHostKeyChecking=no $SSH_USER@$SERVER_IP << 'EOF'
    set -e
    
    echo "Loading Docker image..."
    docker load -i /tmp/screenshot-api.tar
    echo "✓ Image loaded"
    
    echo "Stopping old container..."
    docker stop screenshot-api 2>/dev/null || true
    docker rm screenshot-api 2>/dev/null || true
    
    echo "Starting new container..."
    docker run -d \
        --name screenshot-api \
        -p 5000:5000 \
        -e PORT=5000 \
        -e HOST=0.0.0.0 \
        -e MAX_CONCURRENCY=2 \
        -e RATE_LIMIT_PER_MINUTE=30 \
        -e CACHE_TTL_SECONDS=300 \
        -e CACHE_DIR=/tmp/screenshot-cache \
        -e NAV_TIMEOUT_MS=30000 \
        -e DEBUG=false \
        -v screenshot-cache:/tmp/screenshot-cache \
        --restart unless-stopped \
        screenshot-api:latest
    
    echo "✓ Container started"
    echo ""
    echo "Waiting for service to be ready..."
    sleep 10
    
    # Test health endpoint
    if curl -s http://localhost:5000/health | grep -q "ok"; then
        echo "✓ Service is healthy!"
        echo ""
        echo "Service URL: http://$SERVER_IP:5000"
    else
        echo "⚠️  Service may not be ready yet. Check with:"
        echo "  curl http://localhost:5000/health"
        echo "  docker logs screenshot-api"
    fi
EOF

# Cleanup
echo ""
echo -e "${GREEN}[5/5] Cleaning up...${NC}"
rm -f screenshot-api.tar
echo -e "${GREEN}✓ Cleanup complete${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Your service is available at:"
echo "  http://$SERVER_IP:5000"
echo ""
echo "Test with:"
echo "  curl http://$SERVER_IP:5000/health"
echo "  curl \"http://$SERVER_IP:5000/screenshot?url=https://example.com\" -o screenshot.png"
