FROM python:3.12-slim

# Install minimal system dependencies for Chromium
RUN apt-get update && apt-get install -y \
    wget gnupg2 ca-certificates \
    libgtk-3-0 libxcomposite1 libxdamage1 libxrandr2 libxkbcommon0 \
    libasound2 libpangocairo-1.0-0 libcairo-gobject2 libgdk-pixbuf-2.0-0 \
    libxcursor1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install --with-deps chromium

COPY . .

RUN mkdir -p /tmp/screenshot-cache && chmod 777 /tmp/screenshot-cache

ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PORT=5000
ENV HOST=0.0.0.0
ENV MAX_CONCURRENCY=2
ENV NAV_TIMEOUT_MS=30000

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=30s --start-period=30s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-5000}/health', timeout=10)"

CMD gunicorn -w 2 -k gthread -t 120 -b 0.0.0.0:${PORT:-5000} app.main:app
