"""
Disk-based caching for screenshots.

This module provides a simple disk cache with:
- SHA256-based cache keys
- TTL (Time-To-Live) expiration
- Automatic cleanup of expired entries
- Thread-safe file operations using filelock
"""

import hashlib
import json
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Optional, Tuple

import filelock

from app.config import Config

# Global lock for thread-safe cache operations (cleanup, stats, clear)
_cache_operation_lock = Lock()


class CacheMetadata:
    """Metadata stored alongside cached screenshots."""

    def __init__(
        self,
        created_at: float,
        expires_at: float,
        original_url: str,
        viewport: str,
        full_page: bool,
        delay: int,
        content_type: str,
        file_size: int,
    ):
        self.created_at = created_at
        self.expires_at = expires_at
        self.original_url = original_url
        self.viewport = viewport
        self.full_page = full_page
        self.delay = delay
        self.content_type = content_type
        self.file_size = file_size

    def to_dict(self) -> dict:
        """Convert metadata to dictionary."""
        return {
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "original_url": self.original_url,
            "viewport": self.viewport,
            "full_page": self.full_page,
            "delay": self.delay,
            "content_type": self.content_type,
            "file_size": self.file_size,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CacheMetadata":
        """Create metadata from dictionary."""
        return cls(
            created_at=data["created_at"],
            expires_at=data["expires_at"],
            original_url=data["original_url"],
            viewport=data["viewport"],
            full_page=data["full_page"],
            delay=data["delay"],
            content_type=data["content_type"],
            file_size=data["file_size"],
        )


class CacheEntry:
    """Represents a cache entry with metadata."""

    def __init__(self, file_path: Path, metadata: CacheMetadata):
        self.file_path = file_path
        self.metadata = metadata

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() > self.metadata.expires_at


class ScreenshotCache:
    """
    Disk-based cache for screenshots.

    Cache structure:
    - Cache directory contains numbered subdirectories (shard by first 2 chars of hash)
    - Each cache entry has:
      - image file (e.g., abc123...def.png)
      - metadata file (e.g., abc123...def.json)
    """

    def __init__(
        self, cache_dir: Optional[Path] = None, ttl_seconds: Optional[int] = None
    ):
        self.cache_dir = cache_dir if cache_dir is not None else Config.CACHE_DIR
        self.ttl_seconds = (
            ttl_seconds if ttl_seconds is not None else Config.CACHE_TTL_SECONDS
        )
        self.lock_timeout = 10  # seconds

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(
        self,
        url: str,
        width: int,
        height: int,
        full_page: bool,
        delay: int,
        format: str,
    ) -> str:
        """
        Generate a cache key for the given parameters.

        Args:
            url: The URL to cache
            width: Viewport width
            height: Viewport height
            full_page: Whether to capture full page
            delay: Delay in milliseconds
            format: Image format (png or jpeg)

        Returns:
            SHA256 hash as a hex string
        """
        # Create a unique key based on all parameters
        key_components = [
            url,
            f"{width}x{height}",
            "full" if full_page else "viewport",
            str(delay),
            format,
        ]
        key_string = "|".join(key_components)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _get_shard(self, cache_key: str) -> Path:
        """Get the shard directory for a cache key (first 2 chars)."""
        shard = cache_key[:2]
        shard_dir = self.cache_dir / shard
        shard_dir.mkdir(parents=True, exist_ok=True)
        return shard_dir

    def _get_file_paths(self, cache_key: str, format: str) -> Tuple[Path, Path]:
        """
        Get the file paths for a cache entry.

        Args:
            cache_key: The cache key
            format: Image format

        Returns:
            Tuple of (image_path, metadata_path)
        """
        shard_dir = self._get_shard(cache_key)
        image_path = shard_dir / f"{cache_key}.{format}"
        metadata_path = shard_dir / f"{cache_key}.json"
        return image_path, metadata_path

    def get(
        self,
        url: str,
        width: int,
        height: int,
        full_page: bool,
        delay: int,
        format: str,
    ) -> Optional[Tuple[bytes, str]]:
        """
        Retrieve a cached screenshot.

        Args:
            url: The URL that was cached
            width: Viewport width
            height: Viewport height
            full_page: Whether full page was captured
            delay: Delay in milliseconds
            format: Image format

        Returns:
            Tuple of (image_bytes, content_type) if cache hit, None otherwise
        """
        cache_key = self._get_cache_key(url, width, height, full_page, delay, format)
        image_path, metadata_path = self._get_file_paths(cache_key, format)

        # Use lock to prevent race conditions
        lock_file = self.cache_dir / f"{cache_key[:4]}.lock"
        with filelock.FileLock(str(lock_file), timeout=self.lock_timeout):
            # Check if files exist
            if not image_path.exists() or not metadata_path.exists():
                return None

            # Load metadata
            try:
                with open(metadata_path, "r") as f:
                    metadata_dict = json.load(f)
                metadata = CacheMetadata.from_dict(metadata_dict)
            except (json.JSONDecodeError, KeyError, IOError):
                # Corrupted metadata - treat as cache miss
                return None

            # Check expiration
            if time.time() > metadata.expires_at:
                # Clean up expired entry
                self._remove_entry(image_path, metadata_path)
                return None

            # Read image data
            try:
                with open(image_path, "rb") as f:
                    image_bytes = f.read()
            except IOError:
                return None

            return image_bytes, metadata.content_type

    def set(
        self,
        url: str,
        width: int,
        height: int,
        full_page: bool,
        delay: int,
        format: str,
        image_bytes: bytes,
        content_type: str,
    ) -> None:
        """
        Store a screenshot in the cache.

        Args:
            url: The URL that was captured
            width: Viewport width
            height: Viewport height
            full_page: Whether full page was captured
            delay: Delay in milliseconds
            format: Image format
            image_bytes: The screenshot image bytes
            content_type: The MIME type of the image
        """
        cache_key = self._get_cache_key(url, width, height, full_page, delay, format)
        image_path, metadata_path = self._get_file_paths(cache_key, format)

        # Use lock to prevent race conditions
        lock_file = self.cache_dir / f"{cache_key[:4]}.lock"
        with filelock.FileLock(str(lock_file), timeout=self.lock_timeout):
            now = time.time()
            expires_at = now + self.ttl_seconds

            metadata = CacheMetadata(
                created_at=now,
                expires_at=expires_at,
                original_url=url,
                viewport=f"{width}x{height}",
                full_page=full_page,
                delay=delay,
                content_type=content_type,
                file_size=len(image_bytes),
            )

            # Write image file
            with open(image_path, "wb") as f:
                f.write(image_bytes)

            # Write metadata file
            with open(metadata_path, "w") as f:
                json.dump(metadata.to_dict(), f)

    def _remove_entry(self, image_path: Path, metadata_path: Path) -> None:
        """Remove a cache entry (must be called with lock held)."""
        try:
            if image_path.exists():
                image_path.unlink()
        except OSError:
            pass

        try:
            if metadata_path.exists():
                metadata_path.unlink()
        except OSError:
            pass

    def cleanup_expired(self) -> int:
        """
        Remove all expired cache entries.

        This is an expensive operation that scans the entire cache.
        In production, this should be run periodically via a cron job.

        This method is thread-safe using a global lock.

        Returns:
            Number of entries removed
        """
        with _cache_operation_lock:
            removed_count = 0

            for shard_dir in self.cache_dir.iterdir():
                if not shard_dir.is_dir():
                    continue

                for metadata_file in shard_dir.glob("*.json"):
                    try:
                        with open(metadata_file, "r") as f:
                            metadata_dict = json.load(f)
                        metadata = CacheMetadata.from_dict(metadata_dict)

                        if time.time() > metadata.expires_at:
                            image_file = metadata_file.with_suffix(
                                "." + metadata.content_type.split("/")[-1]
                            )
                            self._remove_entry(image_file, metadata_file)
                            removed_count += 1
                    except (json.JSONDecodeError, KeyError, IOError):
                        # Corrupted or invalid - remove
                        try:
                            metadata_file.unlink()
                            removed_count += 1
                        except OSError:
                            pass

            return removed_count

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        This method is thread-safe using a global lock.

        Returns:
            Dictionary with cache statistics
        """
        with _cache_operation_lock:
            stats = {
                "total_entries": 0,
                "expired_entries": 0,
                "total_size_bytes": 0,
                "cache_dir": str(self.cache_dir),
            }

            now = time.time()

            for shard_dir in self.cache_dir.iterdir():
                if not shard_dir.is_dir():
                    continue

                for metadata_file in shard_dir.glob("*.json"):
                    try:
                        with open(metadata_file, "r") as f:
                            metadata_dict = json.load(f)
                        metadata = CacheMetadata.from_dict(metadata_dict)

                        stats["total_entries"] += 1
                        stats["total_size_bytes"] += metadata.file_size

                        if now > metadata.expires_at:
                            stats["expired_entries"] += 1
                    except (json.JSONDecodeError, KeyError, IOError):
                        pass

            return stats

    def clear(self) -> int:
        """
        Clear all cache entries.

        This method is thread-safe using a global lock.

        Returns:
            Number of entries removed
        """
        with _cache_operation_lock:
            removed_count = 0

            for shard_dir in self.cache_dir.iterdir():
                if shard_dir.is_dir():
                    for item in shard_dir.iterdir():
                        try:
                            if item.is_file():
                                item.unlink()
                                removed_count += 1
                            elif item.is_dir():
                                shutil.rmtree(item)
                                removed_count += 1
                        except OSError:
                            pass

            return removed_count
