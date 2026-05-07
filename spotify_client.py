"""
Spotify client – authenticates via OAuth (PKCE supported) and fetches all
Liked Songs with automatic pagination and rate-limit handling.
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyPKCE

from utils import Timer, retry

logger = logging.getLogger("spotify2ytmusic")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SpotifyTrack:
    """Lightweight representation of a saved Spotify track."""

    name: str
    artists: str          # comma-joined artist names
    album: str
    duration_ms: int

    @property
    def search_key(self) -> str:
        """Key used for cache look-ups and YouTube search queries."""
        return f"{self.artists} - {self.name}"


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class SpotifyClient:
    """Wraps *spotipy* to fetch the current user's Liked Songs."""

    PAGE_SIZE: int = 50  # max allowed by Spotify API

    def __init__(self) -> None:
        """Initialise the Spotify client using credentials from env vars.

        Required env vars:
            SPOTIFY_CLIENT_ID
        Optional env vars:
            SPOTIFY_CLIENT_SECRET (if set, uses standard OAuth)
            SPOTIFY_REDIRECT_URI (defaults to http://127.0.0.1:8888/callback)
        """
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")
        redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

        if not client_id or client_id == "your_client_id_here":
            raise EnvironmentError(
                "SPOTIFY_CLIENT_ID must be set. Run 'python main.py --setup' "
                "or update .env."
            )

        if client_secret in ("", "your_client_secret_here"):
            auth_manager = SpotifyPKCE(
                client_id=client_id,
                redirect_uri=redirect_uri,
                scope="user-library-read playlist-read-private playlist-read-collaborative",
            )
            logger.info("Spotify client authenticated with PKCE.")
        else:
            auth_manager = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope="user-library-read playlist-read-private playlist-read-collaborative",
            )
            logger.info("Spotify client authenticated with client secret.")
        self._sp = spotipy.Spotify(auth_manager=auth_manager)
        logger.info("Spotify client ready.")

    # ------------------------------------------------------------------

    def fetch_liked_songs(self, limit: Optional[int] = None) -> list[SpotifyTrack]:
        """Fetch all (or up to *limit*) Liked Songs from the user's library.

        Args:
            limit: If given, stop after collecting this many tracks.

        Returns:
            List of SpotifyTrack objects.
        """
        tracks: list[SpotifyTrack] = []
        offset = 0

        with Timer("Spotify fetch") as t:
            while True:
                page_size = self.PAGE_SIZE
                if limit is not None:
                    remaining = limit - len(tracks)
                    if remaining <= 0:
                        break
                    page_size = min(page_size, remaining)

                results = self._fetch_page(offset, page_size)
                items = results.get("items", [])
                if not items:
                    break

                for item in items:
                    track_obj = item.get("track")
                    if not track_obj:
                        continue
                    artists = ", ".join(
                        a["name"] for a in track_obj.get("artists", [])
                    )
                    tracks.append(
                        SpotifyTrack(
                            name=track_obj["name"],
                            artists=artists,
                            album=track_obj.get("album", {}).get("name", ""),
                            duration_ms=track_obj.get("duration_ms", 0),
                        )
                    )

                offset += len(items)
                if results.get("next") is None:
                    break

        logger.info(
            "Fetched %d liked songs from Spotify. %s", len(tracks), t
        )
        return tracks

    # ------------------------------------------------------------------

    @retry(
        max_attempts=5,
        base_delay=1.0,
        max_delay=30.0,
        retryable_exceptions=(Exception,),
    )
    def _fetch_page(self, offset: int, page_size: int) -> dict:
        """Fetch a single page of saved tracks with retry + rate-limit handling."""
        try:
            return self._sp.current_user_saved_tracks(
                limit=page_size, offset=offset
            )
        except spotipy.exceptions.SpotifyException as exc:
            if exc.http_status == 429:
                retry_after = int(exc.headers.get("Retry-After", 5)) if exc.headers else 5
                logger.warning(
                    "Spotify rate-limited (429). Sleeping %ds …", retry_after
                )
                time.sleep(retry_after)
            raise  # let @retry handle the re-attempt

    @retry(max_attempts=3, base_delay=1.0, max_delay=10.0, retryable_exceptions=(Exception,))
    def get_playlist_name(self, playlist_id: str) -> str:
        """Fetch the name of a Spotify playlist."""
        try:
            pl = self._sp.playlist(playlist_id, fields="name")
            return pl.get("name", "Imported Playlist")
        except Exception as exc:
            logger.warning("Could not fetch playlist name for %s: %s", playlist_id, exc)
            return "Imported Playlist"

    def fetch_playlist_tracks(self, playlist_id: str, limit: Optional[int] = None) -> list[SpotifyTrack]:
        """Fetch all (or up to *limit*) tracks from a specific Spotify playlist."""
        tracks: list[SpotifyTrack] = []
        offset = 0

        with Timer(f"Spotify playlist fetch ({playlist_id})") as t:
            while True:
                page_size = self.PAGE_SIZE
                if limit is not None:
                    remaining = limit - len(tracks)
                    if remaining <= 0:
                        break
                    page_size = min(page_size, remaining)

                results = self._fetch_playlist_page(playlist_id, offset, page_size)
                items = results.get("items", [])
                if not items:
                    break

                for item in items:
                    track_obj = item.get("track")
                    if not track_obj:
                        continue
                    artists = ", ".join(
                        a["name"] for a in track_obj.get("artists", [])
                    )
                    tracks.append(
                        SpotifyTrack(
                            name=track_obj["name"],
                            artists=artists,
                            album=track_obj.get("album", {}).get("name", ""),
                            duration_ms=track_obj.get("duration_ms", 0),
                        )
                    )

                offset += len(items)
                if results.get("next") is None:
                    break

        logger.info(
            "Fetched %d tracks from Spotify playlist. %s", len(tracks), t
        )
        return tracks

    @retry(
        max_attempts=5,
        base_delay=1.0,
        max_delay=30.0,
        retryable_exceptions=(Exception,),
    )
    def _fetch_playlist_page(self, playlist_id: str, offset: int, page_size: int) -> dict:
        """Fetch a single page of playlist tracks with retry + rate-limit handling."""
        try:
            return self._sp.playlist_items(
                playlist_id, limit=page_size, offset=offset
            )
        except spotipy.exceptions.SpotifyException as exc:
            if exc.http_status == 429:
                retry_after = int(exc.headers.get("Retry-After", 5)) if exc.headers else 5
                logger.warning(
                    "Spotify rate-limited (429). Sleeping %ds …", retry_after
                )
                time.sleep(retry_after)
            raise  # let @retry handle the re-attempt
