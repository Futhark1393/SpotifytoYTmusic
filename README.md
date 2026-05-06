# Spotify → YouTube Music Transfer Tool

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Build](https://github.com/kemalsebzeci/SpotifytoYTmusic/actions/workflows/lint.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)
![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)

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

### 2. Spotify credentials (interactive wizard)

On first run, the CLI will automatically detect that credentials are missing and launch an **interactive setup wizard** that walks you through entering your Spotify API keys:

```
⚙  Setup Wizard
  Spotify Client ID:     <paste your client id>
  Spotify Client Secret: <paste your client secret>
  Redirect URI:          (Enter for http://127.0.0.1:8888/callback)

  ✓  Credentials saved to .env
```

To get your credentials:

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create an app and note your **Client ID** and **Client Secret**
3. Add `http://127.0.0.1:8888/callback` as a Redirect URI

> [!TIP]
> You can also manually create a `.env` file from the template: `cp .env.example .env`

### 3. YouTube Music authentication

```bash
ytmusicapi browser
```

Follow the prompts to create `browser.json`. You will need to paste your request headers from a browser session (Developer Tools > Network tab > any request to music.youtube.com > Copy Request Headers).

## Usage

### Using Docker (Recommended)

You can run the tool without installing Python locally using Docker. Make sure you have your `.env` and `browser.json` files ready in the project directory.

```bash
docker build -t spotify2ytmusic .
docker run -it --rm \
  -v $(pwd)/.env:/app/.env \
  -v $(pwd)/browser.json:/app/browser.json \
  -v $(pwd)/match_cache.db:/app/match_cache.db \
  spotify2ytmusic --help
```

### Using Python

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

MIT License

Copyright (c) 2026 Kemal Sebzeci

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
