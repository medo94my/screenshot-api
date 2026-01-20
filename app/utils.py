"""
Utility functions for the screenshot API.
"""

from typing import Any, Optional


def clamp(value: Any, min_value: Any, max_value: Any) -> Any:
    """
    Clamp a value between a minimum and maximum.

    Args:
        value: The value to clamp
        min_value: The minimum allowed value
        max_value: The maximum allowed value

    Returns:
        The clamped value
    """
    if value < min_value:
        return min_value
    if value > max_value:
        return max_value
    return value


def parse_int(
    value: Any,
    default: int,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> Optional[int]:
    """
    Parse an integer value with validation.

    Args:
        value: The value to parse
        default: Default value if parsing fails
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        Parsed integer or default
    """
    try:
        parsed = int(value)
        if min_value is not None and parsed < min_value:
            return min_value
        if max_value is not None and parsed > max_value:
            return max_value
        return parsed
    except (TypeError, ValueError):
        return default


def generate_request_id() -> str:
    """
    Generate a unique request ID.

    Returns:
        A unique string identifier
    """
    import uuid

    return str(uuid.uuid4())[:8]


def format_bytes(num_bytes: int) -> str:
    """
    Format bytes as a human-readable string.

    Args:
        num_bytes: Number of bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    value = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


class Timer:
    """Simple timer context manager for measuring execution time."""

    def __init__(self):
        self.elapsed: float = 0.0
        self._start_time: Optional[float] = None

    def __enter__(self):
        import time

        self._start_time = time.time()
        return self

    def __exit__(self, *args):
        import time

        self.elapsed = time.time() - self._start_time  # type: ignore
