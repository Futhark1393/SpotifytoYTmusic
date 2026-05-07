# Context (Token-Saver)

Goal: transfer Spotify liked songs or a Spotify playlist to YouTube Music.

Inputs
- .env: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
- browser.json: YouTube Music headers (override with --headers)

Outputs
- match_cache.db: cached search results
- skipped.log: unmatched or failed tracks
- YouTube Music playlist: created or reused

Flow
1. preflight_check ensures creds and headers are present
2. SpotifyClient fetches tracks
3. TrackMatcher searches YouTube Music and scores matches
4. MatchCache stores video IDs or SKIP sentinel
5. Matched videos are added to a YouTube Music playlist
6. Summary table is printed

Key flags
--limit, --resume, --dry-run, --threshold, --workers,
--playlist, --interactive, --yt-playlist,
--headers, --cache-path, --skipped-log
