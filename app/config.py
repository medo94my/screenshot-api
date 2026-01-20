"""
Application configuration and environment variables.
"""

import os
from pathlib import Path


class Config:
    """Configuration management for the screenshot API service."""

    # Server Configuration
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 5000))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"

    # Concurrency Settings
    MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "2"))

    # Rate Limiting (requests per minute per IP)
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))

    # Navigation Timeout (milliseconds)
    NAV_TIMEOUT_MS = int(os.getenv("NAV_TIMEOUT_MS", "30000"))

    # Cache Configuration
    CACHE_DIR = Path(os.getenv("CACHE_DIR", "/tmp/screenshot-cache"))
    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))

    # Image Response Limits
    MAX_RESPONSE_SIZE_BYTES = int(
        os.getenv("MAX_RESPONSE_SIZE_BYTES", "8388608")
    )  # 8MB
    MAX_FULLPAGE_HEIGHT = int(os.getenv("MAX_FULLPAGE_HEIGHT", "10000"))  # pixels

    # Screenshot Quality (JPEG quality 1-100)
    SCREENSHOT_QUALITY = int(os.getenv("SCREENSHOT_QUALITY", "85"))

    # Delay parameter limits (to prevent DoS)
    MAX_DELAY_MS = int(os.getenv("MAX_DELAY_MS", "5000"))  # Default 5s, max 10s

    # Browser Settings
    CHROMIUM_ARGS = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-translate",
        "--metrics-recording-only",
        "--mute-audio",
        "--no-first-run",
        "--safebrowsing-disable-auto-update",
    ]

    @classmethod
    def validate(cls) -> None:
        """Validate configuration values."""
        assert cls.MAX_CONCURRENCY >= 1, "MAX_CONCURRENCY must be >= 1"
        assert cls.MAX_CONCURRENCY <= 10, "MAX_CONCURRENCY must be <= 10"
        assert cls.RATE_LIMIT_PER_MINUTE >= 1, "RATE_LIMIT_PER_MINUTE must be >= 1"
        assert cls.CACHE_TTL_SECONDS >= 60, "CACHE_TTL_SECONDS must be >= 60"
        assert 1 <= cls.SCREENSHOT_QUALITY <= 100, "SCREENSHOT_QUALITY must be 1-100"


# Create cache directory on startup
Config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
