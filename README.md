# Spotify → YouTube Music Transfer Tool

A production-ready CLI tool that transfers your **Liked Songs** from Spotify to YouTube Music with fuzzy matching, caching, rate-limit handling, and parallel processing.

## Features

- **Full Spotify library export** – Fetches all liked songs via OAuth with automatic pagination
- **Fuzzy matching** – Uses `rapidfuzz` (token_sort_ratio) to find the best YouTube Music match
- **SQLite cache** – Avoids redundant API calls across runs
- **Rate-limit handling** – Exponential backoff + jitter on HTTP 429 / transient errors
- **Parallel search** – Thread pool (configurable workers) for YouTube Music lookups
- **Resume support** – Pick up where you left off with `--resume`
- **Dry-run mode** – Test matching without modifying playlists
- **Progress bar** – Real-time progress via `tqdm`
- **Skipped log** – All unmatched/failed tracks logged to `skipped.log`

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Spotify credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create an app and note your **Client ID** and **Client Secret**
3. Add `http://localhost:8888/callback` as a Redirect URI
4. Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

### 3. YouTube Music authentication

```bash
ytmusicapi browser
```

Follow the prompts to create `headers.json`. You will need to paste your request headers from a browser session (Developer Tools > Network tab > any request to music.youtube.com > Copy Request Headers).

> [!TIP]
> Use `http://127.0.0.1:8888/callback` instead of `localhost` in your Spotify Dashboard and `.env` to avoid deprecation warnings.

## Usage

```bash
# Full transfer
python main.py

# Process only the first 100 songs
python main.py --limit 100

# Resume from where you left off
python main.py --resume

# Dry run (match only, no playlist changes)
python main.py --dry-run

# Verbose logging
python main.py --verbose

# Custom match threshold (0-100)
python main.py --threshold 70

# Adjust concurrency
python main.py --workers 3
```

### CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--limit N` | Process only first N songs | All |
| `--resume` | Skip already-cached songs | Off |
| `--dry-run` | Match only, no playlist changes | Off |
| `--verbose` / `-v` | Debug-level logging | Off |
| `--threshold N` | Min fuzzy-match score (0-100) | 80 |
| `--workers N` | Concurrent YouTube search workers | 5 |
| `--max-retries N` | Max retry attempts | 5 |

## Project Structure

```
├── main.py             # CLI entry point & orchestration
├── spotify_client.py   # Spotify OAuth + liked songs fetcher
├── ytmusic_client.py   # YouTube Music search & playlist management
├── matcher.py          # Fuzzy matching engine (rapidfuzz)
├── cache.py            # SQLite persistent cache
├── utils.py            # Retry decorator, throttle, text normalization
├── requirements.txt    # Python dependencies
├── .env.example        # Template for Spotify credentials
└── README.md           # This file
```

## Output

At the end of each run you'll see a summary:

```
==================================================
  TRANSFER SUMMARY
==================================================
  Total songs processed : 1247
  Matched & added       : 1198
  Skipped (no match)    :   42
  Errors                :    7
  Cache hits            :    0
  Time taken            : 12m 34.5s
==================================================
```

Unmatched tracks are logged to `skipped.log` for manual review.

## License

MIT
