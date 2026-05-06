"""
SQLite-backed persistent cache for YouTube Music search results.
All public methods are protected by a threading.Lock for safe use
across concurrent threads (ThreadPoolExecutor workers).
"""

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger("spotify2ytmusic")

# Sentinel stored when a track had no acceptable match
SKIP_SENTINEL = "__SKIP__"

# Default cache file path
DEFAULT_CACHE_PATH = Path("match_cache.db")


class MatchCache:
    """Thread-safe, on-disk cache backed by SQLite.

    Attributes:
        hits: Number of cache hits recorded during this session.
    """

    def __init__(self, db_path: Path = DEFAULT_CACHE_PATH) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache "
            "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        self._conn.commit()
        self.hits: int = 0
        logger.debug("Cache opened at %s", db_path)

    def get(self, key: str) -> Optional[str]:
        """Look up a cached videoId. Returns None if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM cache WHERE key = ?", (key,)
            ).fetchone()
            if row is not None:
                self.hits += 1
                return row[0]
            return None

    def put(self, key: str, value: str) -> None:
        """Insert or update a cache entry."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)",
                (key, value),
            )
            self._conn.commit()

    def contains(self, key: str) -> bool:
        """Check whether a key exists without counting a hit."""
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM cache WHERE key = ?", (key,)
            ).fetchone()
            return row is not None

    def size(self) -> int:
        """Return the total number of entries in the cache."""
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM cache").fetchone()
            return row[0] if row else 0

    def close(self) -> None:
        """Flush and close the database connection."""
        self._conn.close()
        logger.debug("Cache closed (%s)", self._db_path)
