#!/bin/bash
#
# Deploy Screenshot API to Render
#
# Usage:
#   1. Get your Render API key from: https://dashboard.render.com/account/api
#   2. Set the API key: export RENDER_API_KEY="your-api-key"
#   3. Run: ./deploy.sh
#

set -e

REPO="https://github.com/medo94my/screenshot-api"
SERVICE_NAME="screenshot-api"

echo "========================================"
echo "🚀 Deploying Screenshot API to Render"
echo "========================================"
echo ""
echo "Repository: $REPO"
echo ""

# Check if API key is set
if [ -z "$RENDER_API_KEY" ]; then
    echo "❌ RENDER_API_KEY not set"
    echo ""
    echo "To deploy, you need a Render API key:"
    echo ""
    echo "1. Go to: https://dashboard.render.com/account/api"
    echo "2. Create a new API key"
    echo "3. Run: export RENDER_API_KEY=\"your-api-key\""
    echo "4. Run this script again"
    echo ""
    echo "Alternative: Deploy manually via Dashboard"
    echo "  https://dashboard.render.com/blueprints/new?repo=$REPO"
    exit 1
fi

echo "✓ Render API key is set"

# Get owner ID
echo ""
echo "Getting Render account info..."
OWNER_RESPONSE=$(curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
    "https://api.render.com/v1/owners")

OWNER_ID=$(echo "$OWNER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['id'])" 2>/dev/null)

if [ -z "$OWNER_ID" ]; then
    echo "❌ Failed to get owner ID"
    echo "Response: $OWNER_RESPONSE"
    exit 1
fi

echo "✓ Owner ID: $OWNER_ID"

# Check if service already exists
echo ""
echo "Checking for existing service..."
SERVICES_RESPONSE=$(curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
    "https://api.render.com/v1/services")

if echo "$SERVICES_RESPONSE" | python3 -c "import sys, json; services=json.load(sys.stdin); print([s['service']['name'] for s in services])" 2>/dev/null | grep -q "$SERVICE_NAME"; then
    echo "⚠️  Service '$SERVICE_NAME' already exists"
    echo "   Updating the service instead..."
    
    # Get existing service ID
    SERVICE_ID=$(echo "$SERVICES_RESPONSE" | python3 -c "import sys, json; services=json.load(sys.stdin); print([s['service']['id'] for s in services if s['service']['name']=='$SERVICE_NAME'][0])" 2>/dev/null)
    
    echo "   Service ID: $SERVICE_ID"
    
    # Trigger a deploy
    echo ""
    echo "Triggering deploy..."
    DEPLOY_RESPONSE=$(curl -s -X POST "https://api.render.com/v1/services/$SERVICE_ID/deploys" \
        -H "Authorization: Bearer $RENDER_API_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"commit\": \"$(git rev-parse HEAD 2>/dev/null || echo 'main')\"}")
    
    echo "✓ Deploy triggered"
    echo ""
    echo "Check deployment status at:"
    echo "  https://dashboard.render.com/web/$SERVICE_ID"
else
    echo "✓ No existing service found, creating new service..."
    
    # Create the service
    echo ""
    echo "Creating service..."
    CREATE_RESPONSE=$(curl -s -X POST "https://api.render.com/v1/services" \
        -H "Authorization: Bearer $RENDER_API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"service\": {
                \"name\": \"$SERVICE_NAME\",
                \"repo\": \"$REPO\",
                \"branch\": \"main\",
                \"rootDir\": \"\",
                \"buildCommand\": \"pip install -r requirements.txt && playwright install --with-deps chromium\",
                \"startCommand\": \"gunicorn -w 2 -k gthread -t 120 -b 0.0.0.0:\\\${PORT:-5000} app.main:app\",
                \"env\": \"python\",
                \"buildPlan\": \"standard\",
                \"autoDeploy\": \"yes\",
                \"notifyOnFail\": \"default\",
                \"healthCheckPath\": \"/health\"
            }
        }")
    
    echo "$CREATE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$CREATE_RESPONSE"
    
    # Get service ID from response
    SERVICE_ID=$(echo "$CREATE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['service']['id'])" 2>/dev/null)
    
    if [ -n "$SERVICE_ID" ]; then
        echo ""
        echo "✓ Service created successfully!"
        echo ""
        echo "Your service is being deployed..."
        echo ""
        echo "Once deployed, your service will be available at:"
        echo "  https://$SERVICE_NAME-xxxx.onrender.com"
        echo ""
        echo "Check status at:"
        echo "  https://dashboard.render.com/web/$SERVICE_ID"
    else
        echo "❌ Failed to create service"
        exit 1
    fi
fi

echo ""
echo "========================================"
echo "✅ Deployment initiated!"
echo "========================================"
