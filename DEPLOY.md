# Screenshot API - Deploy to Render

## Quick Deployment

### Option 1: One-Click Deploy (Recommended)

Click this button to deploy directly to Render:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://dashboard.render.com/blueprints)

Or use this direct link:
https://dashboard.render.com/blueprints/new?repo=https://github.com/medo94my/screenshot-api

### Option 2: Manual Dashboard Deployment

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New +** → **Web Service**
3. Connect your GitHub repository: `medo94my/screenshot-api`
4. Configure with these settings:
   - **Name**: `screenshot-api`
   - **Environment**: `Python 3`
   - **Build Command**:
     ```
     pip install -r requirements.txt && playwright install --with-deps chromium
     ```
   - **Start Command**:
     ```
     gunicorn -w 2 -k gthread -t 120 -b 0.0.0.0:${PORT:-5000} app.main:app
     ```
5. Add environment variables (optional):
   ```
   CACHE_TTL_SECONDS=300
   MAX_CONCURRENCY=2
   RATE_LIMIT_PER_MINUTE=30
   MAX_DELAY_MS=5000
   ```
6. Set Health Check path: `/health`
7. Click **Create Web Service**

## After Deployment

### Get Your Service URL
After deployment, your service will be available at:
```
https://screenshot-api-xxxx.onrender.com
```

### Test the API

```bash
# Health check
curl https://screenshot-api-xxxx.onrender.com/health

# Capture a screenshot
curl "https://screenshot-api-xxxx.onrender.com/screenshot?url=https://example.com" -o screenshot.png

# With custom options
curl "https://screenshot-api-xxxx.onrender.com/screenshot?url=https://example.com&w=1366&h=768&fullPage=1&format=jpeg" -o screenshot.jpg
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check - returns `{"status": "ok"}` |
| `/screenshot` | GET | Capture screenshot (see parameters below) |
| `/cache/stats` | GET | Get cache statistics |
| `/cache/cleanup` | POST | Clean expired cache entries |

### Screenshot Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `url` | string | - | - | **Required.** URL to capture |
| `w` | int | 1280 | 320-1920 | Viewport width |
| `h` | int | 720 | 240-1080 | Viewport height |
| `fullPage` | int | 0 | 0-1 | Capture full page |
| `delay` | int | 0 | 0-5000 | Delay in ms |
| `format` | string | png | png\|jpeg | Image format |

### Example Responses

**Success (200):**
```bash
# Returns binary image data
Content-Type: image/png
X-Cache: MISS
Cache-Control: public, max-age=300
```

**Error (400):**
```json
{
  "error": "Invalid URL",
  "message": "Only HTTP and HTTPS protocols are allowed"
}
```

**Rate Limited (429):**
```json
{
  "error": "Rate limit exceeded",
  "message": "Maximum 30 requests per minute allowed",
  "retry_after": 45
}
```

## Troubleshooting

### Build Fails
- Ensure Playwright browsers are installed: `playwright install --with-deps chromium`
- Check that Python 3.12 is selected

### Screenshot Timeout
- Increase `NAV_TIMEOUT_MS` environment variable
- The page might be taking too long to load

### Memory Issues
- Reduce `MAX_CONCURRENCY` to 1
- Reduce `MAX_FULLPAGE_HEIGHT`

### Out of Memory (OOM)
- Upgrade to a larger instance type (Standard or above)
- The default starter plan has limited RAM

## Security Notes

This service includes comprehensive SSRF protection:
- Blocks access to private IP ranges (RFC 1918, RFC 6598, etc.)
- Blocks localhost and metadata endpoints
- Uses request interception to validate all browser requests
- Thread-safe rate limiting to prevent abuse

For production use, consider:
- Adding authentication to the API
- Setting up a custom domain with SSL
- Configuring a CDN in front of the service
