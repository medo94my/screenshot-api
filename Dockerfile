FROM python:3.12-slim

# Install system dependencies required by Chromium
# These are necessary for headless browser operation
RUN apt-get update && apt-get install -y \
    # Core browser dependencies
    wget \
    gnupg2 \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    # Additional dependencies for stability
    libxshmfence1 \
    libpq5 \
    libxcb1 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libxtst6 \
    libxi6 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers with ALL dependencies
# This installs Chromium and all required system libraries
RUN playwright install --with-deps chromium

# Verify Playwright installation
RUN python3 -c "
from playwright.sync_api import sync_playwright
p = sync_playwright().start()
b = p.chromium.launch(headless=True)
print(f'✓ Playwright chromium verified: {b}')
b.close()
p.stop()
" || { echo "ERROR: Playwright browser verification failed"; exit 1; }

# Copy application code
COPY . .

# Create cache directory
RUN mkdir -p /tmp/screenshot-cache && chmod 777 /tmp/screenshot-cache

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PORT=5000
ENV HOST=0.0.0.0
ENV MAX_CONCURRENCY=2
ENV NAV_TIMEOUT_MS=30000

# Expose port
EXPOSE 5000

# Health check - verify the app starts and health endpoint works
HEALTHCHECK --interval=30s --timeout=30s --start-period=30s --retries=3 \
    CMD python3 -c "
import urllib.request
try:
    resp = urllib.request.urlopen('http://localhost:${PORT:-5000}/health', timeout=10)
    if resp.status == 200:
        print('Health check passed')
        exit(0)
    else:
        print(f'Health check failed: {resp.status}')
        exit(1)
except Exception as e:
    print(f'Health check error: {e}')
    exit(1)
"

# Run with Gunicorn
# Note: PORT is automatically set by Render (or use default 5000 for local)
CMD gunicorn -w 2 -k gthread -t 120 -b 0.0.0.0:${PORT:-5000} app.main:app
