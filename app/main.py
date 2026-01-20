"""
Main Flask application and API endpoints.
"""

import asyncio
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from functools import wraps
from threading import Lock
from typing import Dict, Optional

from flask import Flask, jsonify, request, Response, current_app

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Config
from app.security import validate_url
from app.cache import ScreenshotCache
from app.screenshot import (
    ScreenshotRenderer,
    get_renderer,
    close_renderer,
    ScreenshotError,
)
from app.utils import clamp, parse_int, generate_request_id

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global lock for thread-safe rate limiting
_rate_limit_lock = Lock()


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Load configuration
    app.config["MAX_CONCURRENCY"] = Config.MAX_CONCURRENCY
    app.config["RATE_LIMIT_PER_MINUTE"] = Config.RATE_LIMIT_PER_MINUTE

    # Initialize cache
    cache = ScreenshotCache()
    app.config["cache"] = cache

    # Rate limiting storage (in-memory for MVP)
    rate_limit_storage: Dict[str, list] = defaultdict(list)
    app.config["rate_limit_storage"] = rate_limit_storage

    # Register routes
    register_routes(app)

    # Register lifecycle handlers
    register_lifecycle_handlers(app)

    return app


def check_rate_limit(client_ip: str) -> tuple[bool, int, int]:
    """
    Check if a client has exceeded the rate limit.

    This function is thread-safe using a lock to prevent race conditions
    in concurrent environments (e.g., Gunicorn with multiple workers).

    Args:
        client_ip: The client IP address

    Returns:
        Tuple of (is_allowed, remaining, reset_time_seconds)
    """
    rate_limit = current_app.config["RATE_LIMIT_PER_MINUTE"]
    now = time.time()
    window_start = now - 60

    # Thread-safe read-modify-write operation
    with _rate_limit_lock:
        request_times = current_app.config["rate_limit_storage"].get(client_ip, [])
        request_times = [t for t in request_times if t > window_start]

        if len(request_times) >= rate_limit:
            # Find when the oldest request in the window will expire
            oldest = min(request_times) if request_times else now
            reset_time = int(oldest + 60 - now)
            return False, 0, max(1, reset_time)

        # Record this request
        request_times.append(now)
        current_app.config["rate_limit_storage"][client_ip] = request_times

        remaining = rate_limit - len(request_times)
        return True, remaining, 60


def rate_limit(max_requests: int = 30):
    """
    Decorator for rate limiting endpoints.

    Args:
        max_requests: Maximum requests per minute
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr or "unknown"

            is_allowed, remaining, reset_time = check_rate_limit(client_ip)

            # Add rate limit headers
            response_headers = {
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_time),
            }

            if not is_allowed:
                response = jsonify(
                    {
                        "error": "Rate limit exceeded",
                        "message": f"Maximum {max_requests} requests per minute allowed",
                        "retry_after": reset_time,
                    }
                )
                response.status_code = 429
                for key, value in response_headers.items():
                    response.headers[key] = value
                return response

            result = f(*args, **kwargs)

            # Add headers to successful responses
            if isinstance(result, tuple):
                response_data, status_code = (
                    result[0],
                    result[1] if len(result) > 1 else 200,
                )
                if hasattr(response_data, "headers"):
                    for key, value in response_headers.items():
                        response_data.headers[key] = value
                return response_data, status_code
            elif hasattr(result, "headers"):
                for key, value in response_headers.items():
                    result.headers[key] = value

            return result

        return decorated_function

    return decorator


def register_routes(app: Flask) -> None:
    """Register all API routes."""

    @app.route("/health", methods=["GET"])
    def health_check():
        """
        Health check endpoint.

        Returns:
            JSON response with status
        """
        return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})

    @app.route("/screenshot", methods=["GET"])
    @rate_limit(max_requests=Config.RATE_LIMIT_PER_MINUTE)
    def capture_screenshot():
        """
        Capture a screenshot of a given URL.

        Query Parameters:
            url (required): The URL to capture
            w (optional): Viewport width (default 1280, range 320-1920)
            h (optional): Viewport height (default 720, range 240-1080)
            fullPage (optional): Capture full page (0 or 1, default 0)
            delay (optional): Delay in ms before screenshot (default 0, range 0-10000)
            format (optional): Image format - 'png' or 'jpeg' (default 'png')

        Returns:
            Image bytes with appropriate Content-Type header

        Status Codes:
            200: Success
            400: Invalid request (invalid URL or parameters)
            413: Response too large
            429: Rate limit exceeded
            500: Internal server error
            504: Navigation timeout
        """
        request_id = generate_request_id()
        client_ip = request.remote_addr or "unknown"

        # Log request start
        logger.info(f"[{request_id}] Request from {client_ip}")

        # Parse and validate parameters
        url = request.args.get("url", "").strip()

        if not url:
            logger.warning(f"[{request_id}] Missing URL parameter")
            return jsonify(
                {
                    "error": "Missing required parameter",
                    "message": "URL parameter is required",
                }
            ), 400

        # Validate URL
        validation = validate_url(url)
        if not validation.is_valid:
            logger.warning(
                f"[{request_id}] URL validation failed: {validation.error_message}"
            )
            return jsonify(
                {"error": "Invalid URL", "message": validation.error_message}
            ), 400

        # Parse optional parameters
        width = parse_int(request.args.get("w"), 1280, 320, 1920) or 1280
        height = parse_int(request.args.get("h"), 720, 240, 1080) or 720
        full_page = request.args.get("fullPage", "0").lower() in ("1", "true", "yes")
        delay = parse_int(request.args.get("delay"), 0, 0, Config.MAX_DELAY_MS) or 0
        format_param = request.args.get("format", "png").lower()
        if format_param not in ("png", "jpeg"):
            return jsonify(
                {
                    "error": "Invalid parameter",
                    "message": "format must be 'png' or 'jpeg'",
                }
            ), 400

        # Check cache first
        cache = current_app.config["cache"]
        cache_result = cache.get(url, width, height, full_page, delay, format_param)

        if cache_result:
            image_bytes, content_type = cache_result
            logger.info(f"[{request_id}] Cache HIT")
            response = Response(image_bytes, mimetype=content_type)
            response.headers["X-Cache"] = "HIT"
            response.headers["Cache-Control"] = "public, max-age=60"
            return response

        logger.info(f"[{request_id}] Cache MISS - rendering")

        # Render the screenshot
        async def render_and_cache():
            renderer = await get_renderer()
            try:
                image_bytes = await renderer.capture(
                    url=url,
                    width=width,
                    height=height,
                    full_page=full_page,
                    delay=delay,
                    format=format_param,
                    quality=Config.SCREENSHOT_QUALITY,
                )
                # Cache the result
                content_type = f"image/{format_param}"
                cache.set(
                    url=url,
                    width=width,
                    height=height,
                    full_page=full_page,
                    delay=delay,
                    format=format_param,
                    image_bytes=image_bytes,
                    content_type=content_type,
                )
                return image_bytes, content_type
            except ScreenshotError as e:
                logger.error(f"[{request_id}] Screenshot error: {e.message}")
                raise

        try:
            # Run the async renderer in the event loop
            image_bytes, content_type = asyncio.run(render_and_cache())

            logger.info(
                f"[{request_id}] Rendered successfully - {len(image_bytes)} bytes"
            )

            response = Response(image_bytes, mimetype=content_type)
            response.headers["X-Cache"] = "MISS"
            response.headers["Cache-Control"] = (
                f"public, max-age={Config.CACHE_TTL_SECONDS}"
            )
            return response

        except ScreenshotError as e:
            return jsonify(
                {"error": "Screenshot capture failed", "message": e.message}
            ), e.status_code
        except Exception as e:
            logger.exception(f"[{request_id}] Unexpected error: {str(e)}")
            return jsonify(
                {
                    "error": "Internal server error",
                    "message": "An unexpected error occurred",
                }
            ), 500

    @app.route("/cache/stats", methods=["GET"])
    def cache_stats():
        """
        Get cache statistics (for monitoring).

        Returns:
            JSON with cache statistics
        """
        cache = current_app.config["cache"]
        stats = cache.get_stats()
        return jsonify(stats)

    @app.route("/cache/cleanup", methods=["POST"])
    def cleanup_cache():
        """
        Trigger cache cleanup (remove expired entries).

        Returns:
            JSON with number of removed entries
        """
        cache = current_app.config["cache"]
        removed = cache.cleanup_expired()
        return jsonify(
            {
                "removed_entries": removed,
                "message": f"Cleaned up {removed} expired cache entries",
            }
        )

    @app.errorhandler(404)
    def not_found(error):
        return jsonify(
            {"error": "Not found", "message": "The requested endpoint does not exist"}
        ), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify(
            {
                "error": "Method not allowed",
                "message": "The HTTP method is not allowed for this endpoint",
            }
        ), 405

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify(
            {
                "error": "Internal server error",
                "message": "An unexpected error occurred",
            }
        ), 500


def register_lifecycle_handlers(app: Flask) -> None:
    """Register application lifecycle handlers."""

    @app.before_request
    def before_first_request():
        """Initialize browser on first request if needed."""
        pass  # Browser is initialized lazily in capture_screenshot

    def shutdown_handler():
        """Clean up resources on shutdown."""
        logger.info("Shutting down - closing browser...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(close_renderer())
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        finally:
            loop.close()

    # Register atexit handler
    import atexit

    atexit.register(shutdown_handler)


# Create the application instance
app = create_app()


if __name__ == "__main__":
    Config.validate()

    # Initialize the browser
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(get_renderer())
        logger.info("Browser initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize browser: {e}")
        sys.exit(1)
    finally:
        loop.close()

    # Run the Flask development server
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, threaded=True)
