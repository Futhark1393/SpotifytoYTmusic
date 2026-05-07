"""
YouTube Music client – wraps ytmusicapi for searching, playlist
management, and adding tracks. Supports browser.json or oauth.json.
"""

import logging
from pathlib import Path
from typing import Any, Optional

from ytmusicapi import YTMusic

from utils import Throttle, retry

logger = logging.getLogger("spotify2ytmusic")

DEFAULT_OAUTH_PATH = Path("oauth.json")
DEFAULT_HEADERS_PATH = Path("browser.json")
DEFAULT_AUTH_PATHS = (DEFAULT_OAUTH_PATH, DEFAULT_HEADERS_PATH)
PLAYLIST_TITLE = "Spotify Liked Songs Backup"
PLAYLIST_DESCRIPTION = (
    "Auto-generated backup of Spotify Liked Songs via spotify2ytmusic."
)


class YTMusicClient:
    """High-level wrapper around *ytmusicapi.YTMusic*."""

    def __init__(
        self,
        auth_path: Optional[Path] = None,
        throttle_interval: float = 0.35,
    ) -> None:
        resolved_path = self._resolve_auth_path(auth_path)
        self._yt = YTMusic(str(resolved_path))
        self._throttle = Throttle(min_interval=throttle_interval)
        logger.info("YouTube Music client authenticated (auth: %s).", resolved_path)

    @staticmethod
    def _resolve_auth_path(auth_path: Optional[Path]) -> Path:
        if auth_path is not None:
            if auth_path.exists():
                return auth_path
            raise FileNotFoundError(
                f"YouTube Music auth file not found at '{auth_path}'.\n"
                "  Run one of these to set it up:\n"
                "    ytmusicapi oauth     (recommended, creates oauth.json)\n"
                "    ytmusicapi browser   (manual headers, creates browser.json)\n"
                "  Or run: python main.py --setup\n"
            )

        for candidate in DEFAULT_AUTH_PATHS:
            if candidate.exists():
                return candidate

        raise FileNotFoundError(
            "No YouTube Music auth file found.\n"
            "  Run one of these to set it up:\n"
            "    ytmusicapi oauth     (recommended, creates oauth.json)\n"
            "    ytmusicapi browser   (manual headers, creates browser.json)\n"
            "  Or run: python main.py --setup\n"
        )

    @retry(max_attempts=5, base_delay=1.0, max_delay=30.0)
    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search YouTube Music for songs matching *query*."""
        self._throttle.wait()
        results = self._yt.search(query, filter="songs", limit=limit)
        return results or []

    def get_or_create_playlist(self, title: str = PLAYLIST_TITLE) -> str:
        """Return the playlist ID for *title*, creating it if necessary."""
        existing = self._find_playlist(title)
        if existing:
            logger.info("Reusing existing playlist '%s' (%s).", title, existing)
            return existing
        playlist_id = self._create_playlist(title)
        logger.info("Created new playlist '%s' (%s).", title, playlist_id)
        return playlist_id

    @retry(max_attempts=3, base_delay=2.0, max_delay=15.0)
    def _find_playlist(self, title: str) -> Optional[str]:
        self._throttle.wait()
        playlists = self._yt.get_library_playlists(limit=100)
        for pl in playlists:
            if pl.get("title", "").strip().lower() == title.strip().lower():
                return pl["playlistId"]
        return None

    @retry(max_attempts=3, base_delay=2.0, max_delay=15.0)
    def _create_playlist(self, title: str) -> str:
        self._throttle.wait()
        return self._yt.create_playlist(
            title=title,
            description=PLAYLIST_DESCRIPTION,
            privacy_status="PRIVATE",
        )

    @retry(max_attempts=3, base_delay=1.5, max_delay=15.0)
    def add_tracks_to_playlist(
        self, playlist_id: str, video_ids: list[str]
    ) -> None:
        """Append tracks to a playlist, avoiding duplicates."""
        if not video_ids:
            return
        self._throttle.wait()
        self._yt.add_playlist_items(
            playlistId=playlist_id,
            videoIds=video_ids,
            duplicates=False,
        )
        logger.debug("Added %d track(s) to playlist %s.", len(video_ids), playlist_id)
