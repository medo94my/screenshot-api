FROM python:3.12-slim

# Install ALL system dependencies required by Chromium/Playwright
# This includes video, audio, fonts, and media libraries
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
    # Additional dependencies
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
    # GStreamer (required for media playback)
    libgstreamer-1.0-0 \
    libgstallocators-1.0-0 \
    libgstapp-1.0-0 \
    libgstbase-1.0-0 \
    libgstpbutils-1.0-0 \
    libgstaudio-1.0-0 \
    libgsttag-1.0-0 \
    libgstvideo-1.0-0 \
    libgstgl-1.0-0 \
    libgstcodecparsers-1.0-0 \
    libgstfft-1.0-0 \
    # GTK4 (newer browser requirements)
    libgtk-4-1 \
    libgraphene-1.0-0 \
    # ICU (internationalization)
    libicu \
    libicuuc76 \
    libicudata76 \
    # Media libraries
    libxslt1.1 \
    libwoff2dec1.1.0.2 \
    libvpx9 \
    libevent-2.1-7 \
    libopus0 \
    libwebpdemux2 \
    libjxl0.11 \
    libavif16 \
    libharfbuzz-icu0 \
    libwebpmux3 \
    # Text/speech
    libflite1 \
    libenchant-2-2 \
    libsecret-1-0 \
    libhyphen0 \
    # Other
    libmanette-0.2-0 \
    libnghttp2-14 \
    libx264 \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers with ALL dependencies
# This installs Chromium and verifies it works
RUN playwright install --with-deps chromium

# Verify Playwright works
RUN python3 -c "
from playwright.sync_api import sync_playwright
p = sync_playwright().start()
b = p.chromium.launch(headless=True)
print('✅ Playwright chromium verified:', b)
b.close()
p.stop()
"

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

EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=30s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-5000}/health', timeout=10)"

# Run with Gunicorn
CMD gunicorn -w 2 -k gthread -t 120 -b 0.0.0.0:${PORT:-5000} app.main:app
