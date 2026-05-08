# Context (Token-Saver)

Goal: transfer Spotify liked songs or a Spotify playlist to YouTube Music.

Note: This tool only reads metadata endpoints; Premium is not required. A 403 usually means auth or scopes are missing.

Recommended auth: Spotify PKCE (Client Secret optional) + YouTube Music OAuth (oauth.json).

Inputs
- .env: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET (optional), SPOTIFY_REDIRECT_URI (optional)
- oauth.json or browser.json: YouTube Music auth (override with --headers)

Outputs
- match_cache.db: cached search results
- skipped.log: unmatched or failed tracks
- YouTube Music playlist: created or reused

Flow
1. preflight_check ensures Spotify ID + YT auth are present (prompts for new-user setup if auth exists)
2. SpotifyClient fetches tracks
3. TrackMatcher searches YouTube Music and scores matches
4. MatchCache stores video IDs or SKIP sentinel
5. Matched videos are added to a YouTube Music playlist
6. Summary table is printed

Key flags
--setup, --limit, --resume, --dry-run, --threshold, --workers,
--playlist, --interactive, --yt-playlist,
--headers, --cache-path, --skipped-log
--max-retries (caps retry attempts)
