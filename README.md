# Screenshot API

A self-hosted website screenshot API service built with Flask and Playwright. Similar to ScreenshotAPI.net, this service renders public URLs in a headless Chromium browser and returns screenshots.

## Features

- **Fast Screenshot Capture**: Uses Playwright with headless Chromium for reliable rendering
- **SSRF Protection**: Comprehensive security measures to prevent server-side request forgery
- **Rate Limiting**: In-memory token bucket rate limiting (30 req/min per IP)
- **Caching**: Disk-based cache with TTL to reduce redundant renders
- **Configurable**: All settings via environment variables
- **Docker Ready**: Deployable on Render.com or any Docker-compatible platform

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Request                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Flask Application                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ /health     │  │ /screenshot │  │ Rate Limiting       │ │
│  │ endpoint    │  │ endpoint    │  │ (per-IP)            │ │
│  └─────────────┘  └──────┬──────┘  └─────────────────────┘ │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Security Validation                     │    │
│  │  • URL scheme validation (http/https only)          │    │
│  │  • Private IP range blocking                        │    │
│  │  • DNS resolution validation                        │    │
│  │  • Blocked host patterns                            │    │
│  └────────────────────────┬────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Cache Check                             │    │
│  │  • SHA256 cache key (url + viewport + options)      │    │
│  │  • TTL-based expiration                             │    │
│  │  • Disk-based storage                               │    │
│  └────────────────────────┬────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Playwright Renderer                     │    │
│  │  • Single browser instance (reused)                 │    │
│  │  • New context/page per request (isolated)          │    │
│  │  • Semaphore for concurrency control                │    │
│  └────────────────────────┬────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Response                                │    │
│  │  • Image bytes (PNG/JPEG)                           │    │
│  │  • Appropriate Content-Type header                  │    │
│  │  • Cache-Control headers                            │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install --with-deps chromium

# Run the application
python -m app.main
```

### Using Docker

```bash
# Build the image
docker build -t screenshot-api .

# Run the container
docker run -p 5000:5000 \
  -e PORT=5000 \
  -e CACHE_DIR=/tmp/screenshot-cache \
  screenshot-api
```

## API Endpoints

### GET /health

Health check endpoint. Returns the service status.

**Response:**
```json
{
    "status": "ok",
    "timestamp": "2024-01-01T00:00:00"
}
```

### GET /screenshot

Capture a screenshot of a URL.

**Query Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `url` | string | - | - | **Required.** The URL to capture |
| `w` | int | 1280 | 320-1920 | Viewport width in pixels |
| `h` | int | 720 | 240-1080 | Viewport height in pixels |
| `fullPage` | int | 0 | 0-1 | Capture full page (1) or viewport only (0) |
| `delay` | int | 0 | 0-10000 | Delay in milliseconds before screenshot |
| `format` | string | "png" | "png"\|"jpeg" | Image format |

**Response:** Binary image data with appropriate Content-Type header.

**Example:**
```bash
# Basic screenshot
curl "http://localhost:5000/screenshot?url=https://example.com" -o screenshot.png

# Full page with custom viewport
curl "http://localhost:5000/screenshot?url=https://example.com&w=1366&h=768&fullPage=1" -o fullpage.png

# With delay for dynamic content
curl "http://localhost:5000/screenshot?url=https://example.com&delay=1000" -o delayed.png

# JPEG format
curl "http://localhost:5000/screenshot?url=https://example.com&format=jpeg" -o screenshot.jpg
```

### GET /cache/stats

Get cache statistics (for monitoring).

**Response:**
```json
{
    "total_entries": 10,
    "expired_entries": 2,
    "total_size_bytes": 5242880,
    "cache_dir": "/tmp/screenshot-cache"
}
```

### POST /cache/cleanup

Remove expired cache entries.

**Response:**
```json
{
    "removed_entries": 5,
    "message": "Cleaned up 5 expired cache entries"
}
```

## Configuration

All configuration is done via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | "0.0.0.0" | Server host |
| `PORT` | 5000 | Server port |
| `DEBUG` | "false" | Enable debug mode |
| `MAX_CONCURRENCY` | 2 | Maximum concurrent screenshot renders |
| `RATE_LIMIT_PER_MINUTE` | 30 | Rate limit per IP (requests/minute) |
| `NAV_TIMEOUT_MS` | 30000 | Navigation timeout in milliseconds |
| `CACHE_DIR` | "/tmp/screenshot-cache" | Cache directory path |
| `CACHE_TTL_SECONDS` | 300 | Cache TTL in seconds |
| `MAX_RESPONSE_SIZE_BYTES` | 8388608 | Maximum response size (8MB) |
| `MAX_FULLPAGE_HEIGHT` | 10000 | Maximum full-page capture height |
| `SCREENSHOT_QUALITY` | 85 | JPEG quality (1-100) |
| `MAX_DELAY_MS` | 5000 | Maximum screenshot delay in milliseconds |

## Security

### SSRF Protection

The service implements multiple layers of protection against Server-Side Request Forgery attacks:

1. **URL Scheme Validation**: Only `http://` and `https://` protocols are allowed
2. **Private IP Blocking**: Blocks access to:
   - RFC 1918 private addresses (10.x.x.x, 172.16.x.x, 192.168.x.x)
   - Link-local addresses (169.254.x.x)
   - Loopback addresses (127.x.x.x)
   - Documentation addresses (192.0.2.x, 198.51.100.x, 203.0.113.x)
   - Carrier-Grade NAT (100.64.0.0/10)
   - Benchmark testing ranges (198.18.0.0/15)
   - Multicast and reserved ranges (224.0.0.0/4, 240.0.0.0/4)
   - IPv6 private/local addresses (fc00::/7, fe80::/10, etc.)
3. **DNS Resolution Validation**: Resolves hostnames and blocks if any IP is private
4. **IP Pinning with Host Header Preservation**: After DNS validation, the service uses the resolved IP with Host header to prevent DNS rebinding attacks
5. **Request Interception**: All browser requests (including redirects and subresources) are intercepted and validated
6. **Blocked Hosts**: Explicitly blocks:
   - `localhost` and variants
   - AWS metadata endpoint (169.254.169.254)
   - GCP metadata endpoint (metadata.google.internal)
7. **URL Pattern Blocking**: Blocks dangerous patterns like `file://`, `data:`, `javascript:`

### Additional Security Measures

- **Concurrency Limits**: Maximum 2 concurrent renders (configurable) to prevent resource exhaustion
- **Response Size Limits**: 8MB max response size to prevent memory issues
- **Timeout Management**: 30-second navigation timeout with configurable limits
- **Rate Limiting**: Thread-safe in-memory rate limiting (30 req/min per IP) using threading.Lock
- **Thread Safety**: All shared state (rate limiting, cache operations) protected with proper locking
- **Delay Limits**: Maximum screenshot delay reduced to 5 seconds by default (configurable) to prevent DoS
- **No Sensitive Data Exposure**: Error messages don't leak internal details
- **Cache Thread Safety**: Cache cleanup and statistics operations use global locks

## Deployment on Render.com

### Option 1: Manual Deployment

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Create Render Web Service**
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click "New +" and select "Web Service"
   - Connect your GitHub repository
    - Configure the service:
      - **Build Command**: `pip install -r requirements.txt && playwright install --with-deps chromium`
      - **Start Command**: `gunicorn -w 2 -k gthread -t 120 -b 0.0.0.0:${PORT:-5000} app.main:app`
      - **Instance Type**: Choose an appropriate tier (minimum 1 GB RAM recommended)
   - Set environment variables (optional):
     - `CACHE_TTL_SECONDS`: 300
     - `MAX_CONCURRENCY`: 2
     - `RATE_LIMIT_PER_MINUTE`: 30
   - Click "Create Web Service"

3. **Health Check**
   - Render will automatically use `/health` as the health check endpoint
   - The service will be available at your Render URL

### Option 2: Render Blueprint (render.yaml)

Render supports declarative deployments using `render.yaml`. The service uses Docker, and Render automatically sets the `PORT` environment variable.

```yaml
services:
  - type: web
    name: screenshot-api
    plan: standard
    region: oregon
    docker:
      context: .
      dockerfile: Dockerfile
    buildCommand: |
      pip install -r requirements.txt
      playwright install --with-deps chromium
    startCommand: gunicorn -w 2 -k gthread -t 120 -b 0.0.0.0:${PORT:-5000} app.main:app
    envVars:
      - key: CACHE_TTL_SECONDS
        value: 300
      - key: MAX_CONCURRENCY
        value: 2
      - key: RATE_LIMIT_PER_MINUTE
        value: 30
    healthCheckPath: /health
```

To deploy with the blueprint:
1. Push `render.yaml` to your GitHub repository
2. Go to [Render Blueprint Dashboard](https://dashboard.render.com/blueprints)
3. Click "New Blueprint Instance"
4. Connect your repository
5. Click "Apply"

### Recommended Render Settings

- **Instance Type**: Standard (at least 1 GB RAM, 1 CPU)
- **Health Check Path**: `/health`
- **Environment Variables**: Adjust based on your needs

## Monitoring

### Logs

The service logs important events:
- Request ID, client IP, render time
- Cache hit/miss status
- Errors and exceptions

Example log format:
```
2024-01-01 00:00:00 - app.main - INFO - [abc12345] Request from 192.168.1.1
2024-01-01 00:00:01 - app.main - INFO - [abc12345] Cache MISS - rendering
2024-01-01 00:00:02 - app.main - INFO - [abc12345] Rendered successfully - 524288 bytes
```

### Rate Limiting Headers

The `/screenshot` endpoint returns rate limit headers:

- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Remaining requests in the window
- `X-RateLimit-Reset`: Seconds until the limit resets

### Cache Headers

- `X-Cache`: "HIT" or "MISS"
- `Cache-Control`: Caching directives for CDN/proxies

## Performance Considerations

### Concurrency

The `MAX_CONCURRENCY` setting controls how many screenshots can be rendered simultaneously. Higher values improve throughput but increase memory usage.

### Cache

The disk cache significantly reduces rendering load:
- Configure `CACHE_TTL_SECONDS` based on how often pages change
- Monitor cache size with `/cache/stats`
- Periodically clean expired entries with `/cache/cleanup`

### Browser Reuse

The service reuses a single Chromium browser instance:
- Reduces startup overhead
- Each request gets a fresh context/page for isolation
- Browser is properly closed on shutdown

## Troubleshooting

### Common Issues

**Browser initialization fails:**
- Ensure Playwright and dependencies are installed: `playwright install --with-deps chromium`
- Check available system memory (Chromium requires significant RAM)

**Timeouts:**
- Increase `NAV_TIMEOUT_MS` for slow-loading pages
- Check network connectivity

**Memory issues:**
- Reduce `MAX_CONCURRENCY`
- Lower `MAX_FULLPAGE_HEIGHT`
- Monitor with `/cache/stats`

### Testing

```bash
# Health check
curl http://localhost:5000/health

# Basic screenshot
curl "http://localhost:5000/screenshot?url=https://example.com" -o example.png

# Full page
curl "http://localhost:5000/screenshot?url=https://example.com&fullPage=1" -o fullpage.png

# Check cache stats
curl http://localhost:5000/cache/stats
```

## License

MIT License - feel free to use this project for your own purposes.
