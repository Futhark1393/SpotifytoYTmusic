"""
Utility functions: retry decorator, rate limiting, text normalization,
timing metrics, and logging setup.
"""

import functools
import logging
import random
import re
import time
from typing import Any, Callable, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

# ---------------------------------------------------------------------------
# Retry decorator with exponential back-off
# ---------------------------------------------------------------------------

class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""


def retry(
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple = (Exception,),
) -> Callable[[F], F]:
    """Decorator that retries a function with exponential back-off and jitter.

    Args:
        max_attempts: Maximum number of attempts before giving up.
        base_delay: Initial delay in seconds.
        max_delay: Cap for the back-off delay.
        retryable_exceptions: Tuple of exception types to retry on.

    Returns:
        Decorated function.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = logging.getLogger("spotify2ytmusic")
            last_exc: Optional[Exception] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    jitter = random.uniform(0, delay * 0.25)
                    sleep_time = delay + jitter
                    logger.warning(
                        "Attempt %d/%d for %s failed (%s). "
                        "Retrying in %.1fs …",
                        attempt,
                        max_attempts,
                        func.__name__,
                        exc,
                        sleep_time,
                    )
                    time.sleep(sleep_time)
            raise RetryError(
                f"All {max_attempts} attempts for {func.__name__} exhausted"
            ) from last_exc

        return wrapper  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# Request throttle
# ---------------------------------------------------------------------------

class Throttle:
    """Simple per-call throttle to avoid hammering APIs."""

    def __init__(self, min_interval: float = 0.3) -> None:
        self._min_interval = min_interval
        self._last_call = 0.0

    def wait(self) -> None:
        """Block until *min_interval* seconds have elapsed since the last call."""
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()


# ---------------------------------------------------------------------------
# Text normalization helpers
# ---------------------------------------------------------------------------

# Patterns to strip from track/artist names before fuzzy matching
_NOISE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\(feat\.?\s+[^)]*\)", re.IGNORECASE),
    re.compile(r"\[feat\.?\s+[^\]]*\]", re.IGNORECASE),
    re.compile(r"\(ft\.?\s+[^)]*\)", re.IGNORECASE),
    re.compile(r"\[ft\.?\s+[^\]]*\]", re.IGNORECASE),
    re.compile(r"\(with\s+[^)]*\)", re.IGNORECASE),
    re.compile(r"\[with\s+[^\]]*\]", re.IGNORECASE),
    re.compile(r"\(remix\)", re.IGNORECASE),
    re.compile(r"\[remix\]", re.IGNORECASE),
    re.compile(r"\(official\s*(music\s*)?video\)", re.IGNORECASE),
    re.compile(r"\[official\s*(music\s*)?video\]", re.IGNORECASE),
    re.compile(r"\(lyrics?\)", re.IGNORECASE),
    re.compile(r"\(audio\)", re.IGNORECASE),
    re.compile(r"\(live\)", re.IGNORECASE),
    re.compile(r"- remastered\s*\d*", re.IGNORECASE),
    re.compile(r"remaster(ed)?\s*\d*", re.IGNORECASE),
]


def normalize_text(text: str) -> str:
    """Lowercase, strip noise tokens (feat., remix, etc.) and collapse spaces.

    Args:
        text: Raw track or artist string.

    Returns:
        Cleaned, lowercased string.
    """
    result = text.lower()
    for pat in _NOISE_PATTERNS:
        result = pat.sub("", result)
    result = re.sub(r"\s+", " ", result).strip()
    return result


# ---------------------------------------------------------------------------
# Timing context-manager
# ---------------------------------------------------------------------------

class Timer:
    """Simple wall-clock timer."""

    def __init__(self, label: str = "") -> None:
        self.label = label
        self.start: float = 0.0
        self.elapsed: float = 0.0

    def __enter__(self) -> "Timer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        self.elapsed = time.perf_counter() - self.start

    def __str__(self) -> str:
        mins, secs = divmod(self.elapsed, 60)
        if mins:
            return f"{self.label}: {int(mins)}m {secs:.1f}s"
        return f"{self.label}: {secs:.2f}s"
