#!/usr/bin/env python3
"""
Comprehensive test suite for the Screenshot API service.

This script tests:
1. Configuration module
2. Security module (URL validation, IP blocking)
3. Utils module
4. Cache module
5. Flask application endpoints
6. Screenshot rendering (integration test)
"""

import sys
import os
import tempfile
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header(text: str) -> None:
    print(f"\n{BOLD}{BLUE}{'=' * 60}{RESET}")
    print(f"{BOLD}{BLUE}{text}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 60}{RESET}\n")


def print_success(text: str) -> None:
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text: str) -> None:
    print(f"{RED}✗ {text}{RESET}")


def print_info(text: str) -> None:
    print(f"{YELLOW}→ {text}{RESET}")


# =============================================================================
# TEST 1: Configuration Module
# =============================================================================
def test_config():
    print_header("Testing Configuration Module")

    from app.config import Config

    # Test default values
    print_info("Testing default values...")
    assert Config.MAX_CONCURRENCY == 2, (
        f"Expected MAX_CONCURRENCY=2, got {Config.MAX_CONCURRENCY}"
    )
    assert Config.RATE_LIMIT_PER_MINUTE == 30, (
        f"Expected RATE_LIMIT_PER_MINUTE=30, got {Config.RATE_LIMIT_PER_MINUTE}"
    )
    assert Config.CACHE_TTL_SECONDS == 300, (
        f"Expected CACHE_TTL_SECONDS=300, got {Config.CACHE_TTL_SECONDS}"
    )
    assert Config.NAV_TIMEOUT_MS == 30000, (
        f"Expected NAV_TIMEOUT_MS=30000, got {Config.NAV_TIMEOUT_MS}"
    )
    assert Config.MAX_DELAY_MS == 5000, (
        f"Expected MAX_DELAY_MS=5000, got {Config.MAX_DELAY_MS}"
    )
    print_success("Default values are correct")

    # Test CHROMIUM_ARGS
    print_info("Testing Chromium arguments...")
    assert isinstance(Config.CHROMIUM_ARGS, list), "CHROMIUM_ARGS should be a list"
    assert "--no-sandbox" in Config.CHROMIUM_ARGS, (
        "--no-sandbox should be in CHROMIUM_ARGS"
    )
    assert "--disable-setuid-sandbox" in Config.CHROMIUM_ARGS, (
        "--disable-setuid-sandbox should be in CHROMIUM_ARGS"
    )
    print_success("Chromium arguments are correctly configured")

    # Test validate method
    print_info("Testing configuration validation...")
    try:
        Config.validate()
        print_success("Configuration validation passed")
    except AssertionError as e:
        print_error(f"Configuration validation failed: {e}")
        return False

    print_success("All configuration tests passed!")
    return True


# =============================================================================
# TEST 2: Utils Module
# =============================================================================
def test_utils():
    print_header("Testing Utils Module")

    from app.utils import clamp, parse_int, Timer, format_bytes

    # Test clamp
    print_info("Testing clamp function...")
    assert clamp(5, 0, 10) == 5, "clamp(5, 0, 10) should return 5"
    assert clamp(-5, 0, 10) == 0, "clamp(-5, 0, 10) should return 0"
    assert clamp(15, 0, 10) == 10, "clamp(15, 0, 10) should return 10"
    assert clamp(5.5, 0, 10) == 5.5, "clamp(5.5, 0, 10) should return 5.5"
    print_success("clamp function works correctly")

    # Test parse_int
    print_info("Testing parse_int function...")
    assert parse_int("10", 5) == 10, "parse_int('10', 5) should return 10"
    assert parse_int("abc", 5) == 5, "parse_int('abc', 5) should return 5"
    assert parse_int(None, 5) == 5, "parse_int(None, 5) should return 5"
    assert parse_int("10", 5, 0, 8) == 8, "parse_int with max should clamp"
    assert parse_int("10", 5, 0, 20) == 10, "parse_int with range should return value"
    print_success("parse_int function works correctly")

    # Test Timer
    print_info("Testing Timer context manager...")
    with Timer() as timer:
        time.sleep(0.1)
    assert timer.elapsed >= 0.1, (
        f"Timer should measure at least 0.1s, got {timer.elapsed}"
    )
    assert timer.elapsed < 1.0, (
        f"Timer should measure less than 1s, got {timer.elapsed}"
    )
    print_success(f"Timer works correctly (measured {timer.elapsed:.3f}s)")

    # Test format_bytes
    print_info("Testing format_bytes function...")
    assert format_bytes(500) == "500.0 B", (
        f"format_bytes(500) should return '500.0 B', got '{format_bytes(500)}'"
    )
    assert format_bytes(1024) == "1.0 KB", (
        f"format_bytes(1024) should return '1.0 KB', got '{format_bytes(1024)}'"
    )
    assert format_bytes(1048576) == "1.0 MB", (
        f"format_bytes(1048576) should return '1.0 MB', got '{format_bytes(1048576)}'"
    )
    print_success("format_bytes function works correctly")

    print_success("All utils tests passed!")
    return True


# =============================================================================
# TEST 3: Security Module
# =============================================================================
def test_security():
    print_header("Testing Security Module")

    from app.security import (
        validate_url,
        is_internal_url,
        is_private_ip,
        PRIVATE_IP_RANGES,
        BLOCKED_HOSTS,
    )

    # Test URL validation - valid URLs
    print_info("Testing valid URL validation...")
    valid_urls = [
        "https://example.com",
        "http://example.com",
        "https://www.example.com/page?query=value",
        "https://example.com:8080/path",
    ]
    for url in valid_urls:
        result = validate_url(url)
        if not result.is_valid:
            print_error(
                f"Expected valid URL '{url}' to be valid: {result.error_message}"
            )
            return False
    print_success(f"All {len(valid_urls)} valid URLs passed validation")

    # Test URL validation - invalid URLs
    print_info("Testing invalid URL validation...")
    invalid_urls = [
        ("file:///etc/passwd", "file:// scheme should be blocked"),
        ("javascript:alert(1)", "javascript: scheme should be blocked"),
        ("data:text/html", "data: scheme should be blocked"),
        ("ftp://example.com", "ftp:// scheme should be blocked"),
        ("", "Empty URL should be invalid"),
    ]
    for url, expected_reason in invalid_urls:
        result = validate_url(url)
        if result.is_valid:
            print_error(f"Expected URL '{url}' to be invalid ({expected_reason})")
            return False
    print_success(f"All {len(invalid_urls)} invalid URLs were correctly rejected")

    # Test blocked hosts
    print_info("Testing blocked hosts...")
    blocked_hosts = [
        "localhost",
        "127.0.0.1",
        "169.254.169.254",
        "metadata.google.internal",
    ]
    for host in blocked_hosts:
        url = f"https://{host}/"
        result = validate_url(url)
        if result.is_valid:
            print_error(f"Expected host '{host}' to be blocked")
            return False
    print_success(f"All {len(blocked_hosts)} blocked hosts were correctly rejected")

    # Test private IP detection
    print_info("Testing private IP detection...")
    private_ips = [
        "10.0.0.1",
        "172.16.0.1",
        "172.31.255.1",
        "192.168.1.1",
        "169.254.0.1",
        "127.0.0.1",
        "::1",
        "fe80::1",
    ]
    for ip in private_ips:
        if not is_private_ip(ip):
            print_error(f"Expected IP '{ip}' to be detected as private")
            return False
    print_success(f"All {len(private_ips)} private IPs were correctly detected")

    # Test public IP detection
    print_info("Testing public IP detection...")
    public_ips = [
        "8.8.8.8",
        "1.1.1.1",
        "9.9.9.9",
        "208.67.222.222",
    ]
    for ip in public_ips:
        if is_private_ip(ip):
            print_error(f"Expected IP '{ip}' to be detected as public")
            return False
    print_success(f"All {len(public_ips)} public IPs were correctly identified")

    # Test is_internal_url function
    print_info("Testing is_internal_url function...")
    internal_urls = [
        "http://localhost",
        "http://127.0.0.1",
        "http://192.168.1.1",
        "http://169.254.169.254",
    ]
    for url in internal_urls:
        if not is_internal_url(url):
            print_error(f"Expected URL '{url}' to be internal")
            return False
    print_success(f"All {len(internal_urls)} internal URLs were correctly detected")

    # Test URLValidationResult has resolved_ip
    print_info("Testing URL validation returns resolved IP...")
    result = validate_url("https://example.com")
    if not result.is_valid:
        print_error(f"Expected valid URL to pass validation: {result.error_message}")
        return False
    if not result.resolved_ip:
        print_error("Expected resolved_ip to be populated for valid URL")
        return False
    if result.hostname != "example.com":
        print_error(f"Expected hostname 'example.com', got '{result.hostname}'")
        return False
    print_success(
        f"URL validation correctly returns resolved_ip ({result.resolved_ip})"
    )

    # Verify comprehensive IP ranges
    print_info(f"Testing comprehensive IP ranges ({len(PRIVATE_IP_RANGES)} ranges)...")
    assert len(PRIVATE_IP_RANGES) > 10, (
        f"Expected more than 10 IP ranges, got {len(PRIVATE_IP_RANGES)}"
    )
    print_success(f"Found {len(PRIVATE_IP_RANGES)} comprehensive IP ranges")

    print_success("All security tests passed!")
    return True


# =============================================================================
# TEST 4: Cache Module
# =============================================================================
def test_cache():
    print_header("Testing Cache Module")

    from app.cache import ScreenshotCache, CacheMetadata
    import tempfile
    import shutil

    # Create temporary cache directory
    temp_dir = tempfile.mkdtemp()
    try:
        cache = ScreenshotCache(cache_dir=Path(temp_dir), ttl_seconds=60)

        # Test cache key generation
        print_info("Testing cache key generation...")
        key1 = cache._get_cache_key("https://example.com", 1280, 720, False, 0, "png")
        key2 = cache._get_cache_key("https://example.com", 1280, 720, False, 0, "png")
        key3 = cache._get_cache_key("https://example.com", 1920, 1080, False, 0, "png")
        assert len(key1) == 64, f"Cache key should be 64 chars, got {len(key1)}"
        assert key1 == key2, "Same parameters should generate same key"
        assert key1 != key3, "Different parameters should generate different key"
        print_success("Cache key generation works correctly")

        # Test cache set and get
        print_info("Testing cache set/get...")
        test_image = b"fake image data"
        cache.set(
            url="https://example.com",
            width=1280,
            height=720,
            full_page=False,
            delay=0,
            format="png",
            image_bytes=test_image,
            content_type="image/png",
        )

        # Should find in cache
        result = cache.get(
            url="https://example.com",
            width=1280,
            height=720,
            full_page=False,
            delay=0,
            format="png",
        )
        if result is None:
            print_error("Cache should return data after set")
            return False
        image_bytes, content_type = result
        assert image_bytes == test_image, "Cache should return exact same data"
        assert content_type == "image/png", (
            f"Expected content_type 'image/png', got '{content_type}'"
        )
        print_success("Cache set/get works correctly")

        # Test cache miss for different parameters
        print_info("Testing cache miss for different parameters...")
        result = cache.get(
            url="https://example.com",
            width=1920,  # Different width
            height=720,
            full_page=False,
            delay=0,
            format="png",
        )
        if result is not None:
            print_error("Cache should return None for different parameters")
            return False
        print_success("Cache miss works correctly for different parameters")

        # Test cache TTL expiration
        print_info("Testing cache TTL expiration...")
        short_ttl_cache = ScreenshotCache(
            cache_dir=Path(temp_dir) / "short", ttl_seconds=1
        )
        short_ttl_cache.set(
            url="https://test.com",
            width=1280,
            height=720,
            full_page=False,
            delay=0,
            format="png",
            image_bytes=test_image,
            content_type="image/png",
        )
        time.sleep(1.5)  # Wait for expiration
        result = short_ttl_cache.get(
            url="https://test.com",
            width=1280,
            height=720,
            full_page=False,
            delay=0,
            format="png",
        )
        if result is not None:
            print_error("Cache should return None after TTL expiration")
            return False
        print_success("Cache TTL expiration works correctly")

        # Test cache stats
        print_info("Testing cache stats...")
        stats = cache.get_stats()
        assert "total_entries" in stats, "Stats should include total_entries"
        assert "total_size_bytes" in stats, "Stats should include total_size_bytes"
        print_success("Cache stats works correctly")

        # Test cache cleanup
        print_info("Testing cache cleanup...")
        removed = cache.cleanup_expired()
        assert isinstance(removed, int), "cleanup_expired should return int"
        print_success("Cache cleanup works correctly")

        # Test cache clear
        print_info("Testing cache clear...")
        cleared = cache.clear()
        assert isinstance(cleared, int), "clear should return int"
        print_success("Cache clear works correctly")

        print_success("All cache tests passed!")
        return True

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


# =============================================================================
# TEST 5: Flask Application
# =============================================================================
def test_flask_app():
    print_header("Testing Flask Application")

    from app.main import app, create_app

    # Create test app
    test_app = create_app()
    test_app.config["TESTING"] = True

    with test_app.test_client() as client:
        # Test health endpoint
        print_info("Testing /health endpoint...")
        response = client.get("/health")
        if response.status_code != 200:
            print_error(f"Expected status 200, got {response.status_code}")
            return False
        data = response.get_json()
        if data.get("status") != "ok":
            print_error(f"Expected status 'ok', got '{data.get('status')}'")
            return False
        print_success("/health endpoint works correctly")

        # Test screenshot endpoint - missing URL
        print_info("Testing /screenshot endpoint with missing URL...")
        response = client.get("/screenshot")
        if response.status_code != 400:
            print_error(
                f"Expected status 400 for missing URL, got {response.status_code}"
            )
            return False
        data = response.get_json()
        if "error" not in data:
            print_error("Expected error in response")
            return False
        print_success("/screenshot endpoint correctly rejects missing URL")

        # Test screenshot endpoint - invalid URL
        print_info("Testing /screenshot endpoint with invalid URL...")
        response = client.get("/screenshot?url=javascript:alert(1)")
        if response.status_code != 400:
            print_error(
                f"Expected status 400 for invalid URL, got {response.status_code}"
            )
            return False
        print_success("/screenshot endpoint correctly rejects invalid URL")

        # Test screenshot endpoint - blocked host
        print_info("Testing /screenshot endpoint with blocked host...")
        response = client.get("/screenshot?url=http://localhost:8080")
        if response.status_code != 400:
            print_error(
                f"Expected status 400 for blocked host, got {response.status_code}"
            )
            return False
        print_success("/screenshot endpoint correctly rejects blocked hosts")

        # Test screenshot endpoint - invalid format
        print_info("Testing /screenshot endpoint with invalid format...")
        response = client.get("/screenshot?url=https://example.com&format=webp")
        if response.status_code != 400:
            print_error(
                f"Expected status 400 for invalid format, got {response.status_code}"
            )
            return False
        print_success("/screenshot endpoint correctly rejects invalid format")

        # Test cache stats endpoint
        print_info("Testing /cache/stats endpoint...")
        response = client.get("/cache/stats")
        if response.status_code != 200:
            print_error(f"Expected status 200, got {response.status_code}")
            return False
        data = response.get_json()
        if "total_entries" not in data:
            print_error("Expected total_entries in cache stats")
            return False
        print_success("/cache/stats endpoint works correctly")

        # Test 404 handler
        print_info("Testing 404 handler...")
        response = client.get("/nonexistent")
        if response.status_code != 404:
            print_error(f"Expected status 404, got {response.status_code}")
            return False
        data = response.get_json()
        if data.get("error") != "Not found":
            print_error(f"Expected error 'Not found', got '{data.get('error')}'")
            return False
        print_success("404 handler works correctly")

        print_success("All Flask app tests passed!")
        return True


# =============================================================================
# TEST 6: Integration Test (Screenshot Capture)
# =============================================================================
def test_screenshot_capture():
    print_header("Testing Screenshot Capture (Integration Test)")

    import asyncio
    from app.screenshot import get_renderer, close_renderer, ScreenshotError

    async def capture_test():
        print_info("Initializing renderer...")
        renderer = await get_renderer()
        print_success("Renderer initialized")

        # Test capture with valid URL
        print_info("Capturing screenshot of https://example.com...")
        try:
            image_bytes = await renderer.capture(
                url="https://example.com",
                width=1280,
                height=720,
                full_page=False,
                delay=0,
                format="png",
            )
            if not image_bytes:
                print_error("Screenshot returned empty data")
                return False
            if len(image_bytes) < 1000:
                print_error(
                    f"Screenshot too small ({len(image_bytes)} bytes), may be error page"
                )
                return False
            print_success(
                f"Screenshot captured successfully ({len(image_bytes)} bytes)"
            )
        except ScreenshotError as e:
            print_error(f"Screenshot failed: {e.message}")
            return False

        # Test that private URLs are blocked
        print_info("Testing that private URLs are blocked...")
        try:
            await renderer.capture(url="http://localhost:8080", width=1280, height=720)
            print_error("Should have blocked localhost URL")
            return False
        except ScreenshotError as e:
            if "Invalid URL" in e.message or "blocked" in e.message.lower():
                print_success("Private URLs are correctly blocked")
            else:
                print_error(f"Unexpected error message: {e.message}")
                return False

        print_success("All integration tests passed!")
        return True

    # Run async test
    result = asyncio.run(capture_test())

    # Cleanup
    asyncio.run(close_renderer())

    return result


# =============================================================================
# MAIN TEST RUNNER
# =============================================================================
def main():
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}{'🔍 SCREENSHOT API - COMPREHENSIVE TEST SUITE'}{RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")

    results = []

    # Run all tests
    tests = [
        ("Configuration Module", test_config),
        ("Utils Module", test_utils),
        ("Security Module", test_security),
        ("Cache Module", test_cache),
        ("Flask Application", test_flask_app),
        ("Screenshot Capture (Integration)", test_screenshot_capture),
    ]

    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print_error(f"Test failed with exception: {e}")
            import traceback

            traceback.print_exc()
            results.append((name, False))

    # Summary
    print_header("TEST SUMMARY")
    passed = 0
    failed = 0
    for name, result in results:
        if result:
            print_success(f"{name}")
            passed += 1
        else:
            print_error(f"{name}")
            failed += 1

    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}Results: {passed} passed, {failed} failed{RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")

    if failed == 0:
        print(f"\n{GREEN}{BOLD}🎉 ALL TESTS PASSED!{RESET}\n")
        return 0
    else:
        print(f"\n{RED}{BOLD}❌ SOME TESTS FAILED{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
