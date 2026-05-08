import os
import unittest

from dotenv import load_dotenv

from spotify_client import SpotifyAuthError, SpotifyClient


class SpotifyIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_dotenv()
        if os.getenv("RUN_REAL_TESTS") != "1":
            raise unittest.SkipTest(
                "Set RUN_REAL_TESTS=1 to run real Spotify integration tests."
            )
        if not os.getenv("SPOTIFY_CLIENT_ID"):
            raise unittest.SkipTest(
                "SPOTIFY_CLIENT_ID is required to run Spotify integration tests."
            )

    def test_fetch_liked_songs_real(self) -> None:
        sp = SpotifyClient()
        try:
            tracks = sp.fetch_liked_songs(limit=1)
        except SpotifyAuthError as exc:
            self.fail(f"Spotify auth failed: {exc}")
        self.assertIsInstance(tracks, list)
        if tracks:
            self.assertTrue(tracks[0].name)
            self.assertTrue(tracks[0].artists)

    def test_fetch_playlist_tracks_real(self) -> None:
        playlist_id = os.getenv("SPOTIFY_TEST_PLAYLIST_ID")
        if not playlist_id:
            raise unittest.SkipTest(
                "Set SPOTIFY_TEST_PLAYLIST_ID to run playlist integration test."
            )
        sp = SpotifyClient()
        try:
            tracks = sp.fetch_playlist_tracks(playlist_id, limit=1)
        except SpotifyAuthError as exc:
            self.fail(f"Spotify auth failed: {exc}")
        self.assertIsInstance(tracks, list)

    def test_get_playlist_name_real(self) -> None:
        playlist_id = os.getenv("SPOTIFY_TEST_PLAYLIST_ID")
        if not playlist_id:
            raise unittest.SkipTest(
                "Set SPOTIFY_TEST_PLAYLIST_ID to run playlist name integration test."
            )
        sp = SpotifyClient()
        try:
            name = sp.get_playlist_name(playlist_id)
        except SpotifyAuthError as exc:
            self.fail(f"Spotify auth failed: {exc}")
        self.assertTrue(isinstance(name, str))
        self.assertTrue(name.strip())


if __name__ == "__main__":
    unittest.main()
