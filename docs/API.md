# API Snapshot

main.py
- setup_rich_logging(verbose): configure logging with Rich
- build_parser(): define CLI flags
- extract_playlist_id(url_or_id): parse Spotify playlist ID
- preflight_check(headers_path): validate .env and headers JSON
- interactive_setup(): prompt and write Spotify credentials
- log_skipped(track, reason): append a line to skipped log
- _match_one(track, matcher, cache, resume): worker for fuzzy matching
- run(args): orchestration pipeline

spotify_client.py
- SpotifyTrack.search_key: artist - title key for search/cache
- SpotifyClient.fetch_liked_songs(limit): fetch saved tracks
- SpotifyClient.fetch_playlist_tracks(playlist_id, limit): fetch playlist tracks
- SpotifyClient.get_playlist_name(playlist_id): fetch playlist name

ytmusic_client.py
- YTMusicClient.search(query, limit): search YouTube Music
- YTMusicClient.get_or_create_playlist(title): reuse or create playlist
- YTMusicClient.add_tracks_to_playlist(playlist_id, video_ids): add items

matcher.py
- TrackMatcher.find_best_match(query): return best match and candidates
- MatchResult: video_id, title, score

cache.py
- MatchCache.get(key): retrieve cached value
- MatchCache.put(key, value): store cached value
- MatchCache.contains(key): check presence
- MatchCache.size(): count entries
- MatchCache.close(): close DB connection

utils.py
- retry(...): decorator with backoff + jitter
- Throttle.wait(): per-call throttle
- normalize_text(text): normalize for fuzzy matching
- Timer: timing context manager
