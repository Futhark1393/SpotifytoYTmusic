#!/usr/bin/env python3
"""
spotify2ytmusic – Transfer Spotify Liked Songs to YouTube Music.

Usage:
    python main.py --setup                 # guided auth setup
    python main.py                         # full transfer
    python main.py --limit 50              # process first 50 songs
    python main.py --resume                # skip already-cached songs
    python main.py --dry-run --verbose     # match only, no playlist changes

Setup:
    1. pip install -r requirements.txt
    2. python main.py --setup              # Spotify PKCE + YouTube Music OAuth
    3. python main.py
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

from cache import SKIP_SENTINEL, MatchCache
from matcher import MatchResult, TrackMatcher
from spotify_client import SpotifyClient, SpotifyTrack
from utils import Timer
from ytmusic_client import YTMusicClient

console = Console()
logger: logging.Logger  # initialised in main()

BANNER = r"""
[bold green]
  ███████╗██████╗  ██████╗ ████████╗██╗███████╗██╗   ██╗
  ██╔════╝██╔══██╗██╔═══██╗╚══██╔══╝██║██╔════╝╚██╗ ██╔╝
  ███████╗██████╔╝██║   ██║   ██║   ██║█████╗   ╚████╔╝
  ╚════██║██╔═══╝ ██║   ██║   ██║   ██║██╔══╝    ╚██╔╝
  ███████║██║     ╚██████╔╝   ██║   ██║██║        ██║
  ╚══════╝╚═╝      ╚═════╝    ╚═╝   ╚═╝╚═╝        ╚═╝[/bold green]
[dim]          Spotify Liked Songs → YouTube Music Transfer[/dim]
"""


# ---------------------------------------------------------------------------
# Logging with Rich
# ---------------------------------------------------------------------------

def setup_rich_logging(verbose: bool = False) -> logging.Logger:
    """Configure Rich-powered logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%H:%M:%S]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, markup=True)],
    )
    logger = logging.getLogger("spotify2ytmusic")
    logger.setLevel(level)
    return logger


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    p = argparse.ArgumentParser(
        prog="spotify2ytmusic",
        description="Transfer your Spotify Liked Songs to YouTube Music.",
    )
    p.add_argument("--setup", action="store_true",
                   help="Run guided setup for Spotify + YouTube Music auth and exit.")
    p.add_argument("--limit", type=int, default=None,
                   help="Process only the first N liked songs.")
    p.add_argument("--resume", action="store_true",
                   help="Skip songs already present in the cache.")
    p.add_argument("--dry-run", action="store_true",
                   help="Match songs but do NOT create/modify the playlist.")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="Enable debug-level logging.")
    p.add_argument("--threshold", type=float, default=80.0,
                   help="Minimum fuzzy-match score (0-100, default=80).")
    p.add_argument("--workers", type=int, default=5,
                   help="Max concurrent YouTube search workers (default=5).")
    p.add_argument("--max-retries", type=int, default=5,
                   help="Max retry attempts for transient errors (default=5).")
    p.add_argument("--playlist", type=str, default=None,
                   help="Spotify Playlist ID or URL to transfer instead of Liked Songs.")
    p.add_argument("--interactive", "-i", action="store_true",
                   help="Prompt manually for songs that fail the threshold match.")
    p.add_argument("--headers", type=str, default=None,
                   help="Path to YouTube Music auth JSON (browser.json or oauth.json). Auto-detect if not set.")
    p.add_argument("--cache-path", type=str, default="match_cache.db",
                   help="Path to SQLite cache (default=match_cache.db).")
    p.add_argument("--skipped-log", type=str, default="skipped.log",
                   help="Path for skipped-log output (default=skipped.log).")
    p.add_argument("--yt-playlist", type=str, default=None,
                   help="Custom YouTube Music playlist title.")
    return p

def extract_playlist_id(url_or_id: str) -> str:
    """Extract just the ID from a Spotify playlist URL, or return as-is."""
    import urllib.parse
    if "spotify.com" in url_or_id:
        path = urllib.parse.urlparse(url_or_id).path
        return path.split("/")[-1]
    return url_or_id


# ---------------------------------------------------------------------------
# Skipped-songs logger
# ---------------------------------------------------------------------------

SKIPPED_LOG = Path("skipped.log")


def log_skipped(track: SpotifyTrack, reason: str) -> None:
    """Append a line to skipped.log."""
    with open(SKIPPED_LOG, "a", encoding="utf-8") as f:
        f.write(f"{track.search_key}  |  {reason}\n")


# ---------------------------------------------------------------------------
# Interactive setup wizard
# ---------------------------------------------------------------------------

ENV_FILE = Path(".env")
REDIRECT_URI_DEFAULT = "http://127.0.0.1:8888/callback"
YT_OAUTH_FILE = Path("oauth.json")
YT_BROWSER_FILE = Path("browser.json")


def _abort_env_permission() -> None:
    console.print("[red]Permission denied while updating .env.[/red]")
    console.print(
        "[yellow]Fix:[/yellow] remove the Read-only attribute, close programs using .env, "
        "or run the terminal as Administrator."
    )
    console.print(f"[dim]Path: {ENV_FILE.resolve()}[/dim]")
    raise SystemExit(1)


def _needs_spotify_setup() -> bool:
    """Return True if Spotify credentials are missing or still placeholders."""
    cid = os.getenv("SPOTIFY_CLIENT_ID", "")
    placeholders = {"", "your_client_id_here"}
    return cid in placeholders


def _write_env(client_id: str, client_secret: Optional[str], redirect_uri: str) -> None:
    """Write or update Spotify credentials in .env."""
    _update_env_value("SPOTIFY_CLIENT_ID", client_id)
    if client_secret is None:
        _update_env_value("SPOTIFY_CLIENT_SECRET", "")
    else:
        _update_env_value("SPOTIFY_CLIENT_SECRET", client_secret)
    _update_env_value("SPOTIFY_REDIRECT_URI", redirect_uri)


def _update_env_value(key: str, value: str) -> None:
    """Update a single key in the existing .env file, or append it."""
    if ENV_FILE.exists():
        try:
            text = ENV_FILE.read_text(encoding="utf-8")
        except PermissionError:
            try:
                ENV_FILE.chmod(0o600)
                text = ENV_FILE.read_text(encoding="utf-8")
            except Exception:
                _abort_env_permission()
        pattern = rf"^{re.escape(key)}=.*$"
        if re.search(pattern, text, flags=re.MULTILINE):
            text = re.sub(pattern, f"{key}={value}", text, flags=re.MULTILINE)
            try:
                ENV_FILE.write_text(text, encoding="utf-8")
            except PermissionError:
                try:
                    ENV_FILE.chmod(0o600)
                    ENV_FILE.write_text(text, encoding="utf-8")
                except Exception:
                    _abort_env_permission()
            try:
                ENV_FILE.chmod(0o600)
            except PermissionError:
                pass
            return
        # key not found – append
        text += f"\n{key}={value}\n"
        try:
            ENV_FILE.write_text(text, encoding="utf-8")
        except PermissionError:
            try:
                ENV_FILE.chmod(0o600)
                ENV_FILE.write_text(text, encoding="utf-8")
            except Exception:
                _abort_env_permission()
    else:
        try:
            ENV_FILE.write_text(f"{key}={value}\n", encoding="utf-8")
        except PermissionError:
            _abort_env_permission()
    try:
        ENV_FILE.chmod(0o600)
    except PermissionError:
        pass


def setup_spotify_credentials() -> None:
    """Run a short wizard to collect Spotify API credentials (PKCE supported)."""
    if not _needs_spotify_setup():
        console.print("[green]Spotify Client ID already configured. Skipping.[/green]")
        return

    console.print(
        Panel(
            "Spotify setup (PKCE supported):\n"
            "1. Create an app in the Spotify Developer Dashboard\n"
            f"2. Add redirect URI: {REDIRECT_URI_DEFAULT}\n"
            "3. Paste your Client ID below\n"
            "Client Secret is optional (PKCE is used if omitted).",
            title="[bold green]Setup: Spotify[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )

    while True:
        client_id = console.input("[bold cyan]  Spotify Client ID:[/bold cyan] ").strip()
        if client_id:
            break
        console.print("  [red]Client ID cannot be empty.[/red]")

    client_secret = console.input(
        "[bold cyan]  Spotify Client Secret[/bold cyan] [dim](optional, Enter to skip):[/dim] "
    ).strip()
    if not client_secret:
        client_secret = None

    redirect_uri = console.input(
        f"[bold cyan]  Redirect URI[/bold cyan] [dim](Enter for {REDIRECT_URI_DEFAULT}):[/dim] "
    ).strip()
    if not redirect_uri:
        redirect_uri = REDIRECT_URI_DEFAULT

    _write_env(client_id, client_secret, redirect_uri)
    load_dotenv(override=True)

    console.print()
    console.print("[bold green]  Credentials saved to .env[/bold green]\n")


def _run_ytmusic_setup(mode: str) -> bool:
    try:
        subprocess.run(["ytmusicapi", mode], check=True)
    except FileNotFoundError:
        console.print("[red]ytmusicapi CLI not found. Run: pip install -r requirements.txt[/red]")
        return False
    except subprocess.CalledProcessError as exc:
        console.print(f"[red]ytmusicapi {mode} failed (exit {exc.returncode}).[/red]")
        return False
    return True


def setup_ytmusic_auth() -> Optional[Path]:
    """Guide the user through YouTube Music auth setup."""
    existing = _resolve_yt_auth_path(None)
    if existing and existing.exists():
        console.print(f"[green]Found existing YouTube Music auth: {existing}[/green]")
        return existing

    console.print(
        Panel(
            "YouTube Music auth options:\n"
            "1) OAuth (recommended) – no header copy, creates oauth.json\n"
            "2) Browser headers – manual copy, creates browser.json",
            title="[bold green]Setup: YouTube Music[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )

    choice = console.input("[bold cyan]  Choose 1 or 2[/bold cyan] [dim](default: 1):[/dim] ").strip() or "1"
    if choice == "2":
        if not _run_ytmusic_setup("browser"):
            return None
        if not YT_BROWSER_FILE.exists():
            console.print("[red]browser.json was not created. Try running ytmusicapi browser again.[/red]")
            return None
        return YT_BROWSER_FILE

    if not _run_ytmusic_setup("oauth"):
        return None
    if not YT_OAUTH_FILE.exists():
        console.print("[red]oauth.json was not created. Try running ytmusicapi oauth again.[/red]")
        return None
    return YT_OAUTH_FILE


def run_setup() -> bool:
    """Run guided setup for Spotify and YouTube Music auth."""
    console.print(
        Panel(
            "Guided setup will configure Spotify and YouTube Music auth.\n"
            "This will create/update .env and generate oauth.json or browser.json.",
            title="[bold green]Setup Wizard[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )

    setup_spotify_credentials()
    yt_auth_path = setup_ytmusic_auth()
    if not yt_auth_path:
        console.print("[red]Setup incomplete. Run 'python main.py --setup' again.[/red]")
        return False

    console.print("[bold green]Setup complete. Run 'python main.py' to start.[/bold green]")
    return True


# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------

def _resolve_yt_auth_path(headers_arg: Optional[str]) -> Optional[Path]:
    if headers_arg:
        return Path(headers_arg)
    if YT_OAUTH_FILE.exists():
        return YT_OAUTH_FILE
    if YT_BROWSER_FILE.exists():
        return YT_BROWSER_FILE
    return None


def preflight_check(headers_arg: Optional[str]) -> Path:
    """Validate all prerequisites and return the resolved YT auth path."""
    errors: list[str] = []
    if _needs_spotify_setup():
        errors.append(
            "[bold]SPOTIFY_CLIENT_ID[/bold] is missing in .env\n"
            "  → Run: [bold cyan]python main.py --setup[/bold cyan]"
        )

    yt_auth_path = _resolve_yt_auth_path(headers_arg)
    if yt_auth_path is None or not yt_auth_path.exists():
        if headers_arg:
            errors.append(
                f"[bold]{headers_arg}[/bold] not found\n"
                "  → Run: [bold cyan]ytmusicapi oauth[/bold cyan] (recommended)\n"
                "  → Or: [bold cyan]ytmusicapi browser[/bold cyan]\n"
                "  → Or: [bold cyan]python main.py --setup[/bold cyan]"
            )
        else:
            errors.append(
                "No YouTube Music auth file found (oauth.json or browser.json)\n"
                "  → Run: [bold cyan]python main.py --setup[/bold cyan]"
            )

    if errors:
        msg = "\n\n".join(f"[red]✗[/red]  {e}" for e in errors)
        console.print(Panel(msg, title="[red bold]Setup Required[/red bold]",
                            border_style="red", padding=(1, 2)))
        sys.exit(1)

    console.print("[bold green]✓[/bold green]  All credentials verified — let's go!\n")
    assert yt_auth_path is not None
    return yt_auth_path


# ---------------------------------------------------------------------------
# Worker: match a single track
# ---------------------------------------------------------------------------

def _match_one(
    track: SpotifyTrack,
    matcher: TrackMatcher,
    cache: MatchCache,
    resume: bool,
) -> tuple[SpotifyTrack, Optional[MatchResult], str, list[MatchResult]]:
    """Attempt to match a single Spotify track on YouTube Music."""
    key = track.search_key

    cached = cache.get(key)
    if cached is not None:
        if cached == SKIP_SENTINEL:
            return (track, None, "cached_skip", [])
        return (
            track,
            MatchResult(video_id=cached, title="(cached)", score=100.0),
            "cached",
            []
        )

    if resume and cache.contains(key):
        return (track, None, "resumed", [])

    try:
        result, candidates = matcher.find_best_match(key)
    except Exception as exc:
        logger.error("Error matching '%s': %s", key, exc)
        cache.put(key, SKIP_SENTINEL)
        return (track, None, "error", [])

    if result is None:
        cache.put(key, SKIP_SENTINEL)
        return (track, None, "skipped", candidates)

    cache.put(key, result.video_id)
    return (track, result, "matched", candidates)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> None:
    """Execute the full transfer pipeline."""
    global logger
    logger = setup_rich_logging(verbose=args.verbose)

    load_dotenv()

    # ---- 0. Banner + preflight ----
    console.print(BANNER)
    if args.setup:
        if not run_setup():
            sys.exit(1)
        return

    yt_auth_path = preflight_check(args.headers)

    overall_timer = Timer("Total")
    overall_timer.__enter__()

    # ---- 1. Fetch Spotify songs ----
    with console.status("[bold green]Connecting to Spotify…[/bold green]"):
        sp = SpotifyClient()

    if args.playlist:
        pl_id = extract_playlist_id(args.playlist)
        with console.status("[bold green]Fetching Playlist name…[/bold green]"):
            sp_playlist_name = sp.get_playlist_name(pl_id)
            default_yt_playlist_name = f"{sp_playlist_name} (Backup)"
            yt_playlist_name = args.yt_playlist or default_yt_playlist_name
        
        with console.status(f"[bold green]Fetching tracks from '{sp_playlist_name}'…[/bold green]") as status:
            tracks = sp.fetch_playlist_tracks(pl_id, limit=args.limit)
            status.update(f"[bold green]Fetched {len(tracks)} songs![/bold green]")
        
        console.print(f"  [cyan]🎵  {len(tracks)} songs fetched from playlist '{sp_playlist_name}'[/cyan]\n")
    else:
        default_yt_playlist_name = "Spotify Liked Songs Backup"
        yt_playlist_name = args.yt_playlist or default_yt_playlist_name
        with console.status("[bold green]Fetching your Liked Songs from Spotify…[/bold green]") as status:
            tracks = sp.fetch_liked_songs(limit=args.limit)
            status.update(f"[bold green]Fetched {len(tracks)} songs![/bold green]")

        console.print(f"  [cyan]🎵  {len(tracks)} liked songs fetched from Spotify[/cyan]\n")

    if not tracks:
        console.print("[yellow]No liked songs found. Exiting.[/yellow]")
        return

    # ---- 2. Initialise YouTube Music & matcher ----
    with console.status("[bold green]Connecting to YouTube Music…[/bold green]"):
        yt = YTMusicClient(auth_path=yt_auth_path)
        matcher = TrackMatcher(yt, threshold=args.threshold)
        cache = MatchCache(db_path=Path(args.cache_path))

    console.print(f"  [cyan]📺  YouTube Music ready  |  Match threshold: {args.threshold:.0f}%  |  Workers: {args.workers}[/cyan]\n")

    # ---- 3. Match songs (parallel) ----
    global SKIPPED_LOG
    SKIPPED_LOG = Path(args.skipped_log)

    matched_ids: list[str] = []
    added_set: set[str] = set()
    stats = {"matched": 0, "skipped": 0, "cached": 0, "errors": 0}
    needs_review: list[tuple[SpotifyTrack, list[MatchResult]]] = []

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    )

    with Timer("Matching") as t_match:
        with progress:
            task = progress.add_task("Matching songs…", total=len(tracks))
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = {
                    pool.submit(_match_one, trk, matcher, cache, args.resume): trk
                    for trk in tracks
                }
                for future in as_completed(futures):
                    trk, result, status_str, candidates = future.result()
                    if status_str in ("matched", "cached"):
                        assert result is not None
                        vid = result.video_id
                        if vid not in added_set:
                            matched_ids.append(vid)
                            added_set.add(vid)
                        stats["matched"] += 1
                        if status_str == "cached":
                            stats["cached"] += 1
                    elif status_str == "cached_skip":
                        stats["skipped"] += 1
                    elif status_str == "skipped":
                        if args.interactive and candidates:
                            needs_review.append((trk, candidates))
                        else:
                            stats["skipped"] += 1
                            log_skipped(trk, "no match above threshold")
                    elif status_str == "error":
                        stats["errors"] += 1
                        log_skipped(trk, "error during matching")
                    progress.advance(task)

    # ---- 3.5 Interactive Review ----
    if args.interactive and needs_review:
        from rich.prompt import Prompt
        console.print(f"\n[bold yellow]⚠️  {len(needs_review)} songs need manual review:[/bold yellow]")
        for trk, candidates in needs_review:
            console.print(f"\n[bold cyan]?[/bold cyan] [white]{trk.search_key}[/white] was not matched confidently.")
            for idx, c in enumerate(candidates[:5], start=1):
                console.print(f"   [bold]{idx})[/bold] {c.title} [dim][Score: {c.score:.1f}%][/dim]")
            console.print("   [bold]0)[/bold] Skip this song")
            
            choices = [str(i) for i in range(len(candidates[:5]) + 1)]
            choice = Prompt.ask("Choice", choices=choices, default="0")
            
            if choice != "0":
                picked = candidates[int(choice) - 1]
                vid = picked.video_id
                if vid not in added_set:
                    matched_ids.append(vid)
                    added_set.add(vid)
                stats["matched"] += 1
                cache.put(trk.search_key, vid)  # Overwrite SKIP_SENTINEL
                console.print(f"  [green]✓ Added '{picked.title}'[/green]")
            else:
                stats["skipped"] += 1
                log_skipped(trk, "skipped interactively")

    # ---- 4. Add to YouTube Music playlist ----
    if args.dry_run:
        console.print("\n[yellow]⚡ Dry-run mode — playlist NOT modified.[/yellow]")
    else:
        with console.status(f"[bold green]Creating / finding YouTube Music playlist '{yt_playlist_name}'…[/bold green]"):
            playlist_id = yt.get_or_create_playlist(title=yt_playlist_name)

        batch_size = 25
        total_batches = (len(matched_ids) + batch_size - 1) // batch_size

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as prog2:
            btask = prog2.add_task("Adding to playlist…", total=total_batches)
            for i in range(0, len(matched_ids), batch_size):
                batch = matched_ids[i: i + batch_size]
                try:
                    yt.add_tracks_to_playlist(playlist_id, batch)
                except Exception as exc:
                    logger.error("Failed adding batch %d: %s", i // batch_size, exc)
                prog2.advance(btask)

    overall_timer.__exit__(None, None, None)

    # ---- 5. Rich summary table ----
    match_pct = (stats["matched"] / len(tracks) * 100) if tracks else 0
    skip_pct = (stats["skipped"] / len(tracks) * 100) if tracks else 0

    table = Table(
        title="Transfer Complete 🎉",
        box=box.ROUNDED,
        border_style="green",
        title_style="bold green",
        show_header=True,
        header_style="bold cyan",
        min_width=46,
    )
    table.add_column("Metric", style="bold white", justify="left")
    table.add_column("Value", justify="right")

    table.add_row("Total songs fetched", f"[white]{len(tracks)}[/white]")
    table.add_row(
        "Matched & added",
        f"[green]{stats['matched']}[/green] [dim]({match_pct:.1f}%)[/dim]",
    )
    table.add_row(
        "Skipped (no match)",
        f"[yellow]{stats['skipped']}[/yellow] [dim]({skip_pct:.1f}%)[/dim]",
    )
    table.add_row("Errors", f"[red]{stats['errors']}[/red]")
    table.add_row("Cache hits", f"[cyan]{cache.hits}[/cyan]")
    table.add_row("Time taken", f"[magenta]{overall_timer}[/magenta]")

    if stats["skipped"] > 0:
        table.add_section()
        table.add_row(
            "[dim]Skipped tracks log[/dim]",
            f"[dim]{SKIPPED_LOG}[/dim]",
        )

    console.print()
    console.print(table)
    console.print()

    if args.dry_run:
        console.print("[yellow]ℹ  Dry-run: no changes were made to YouTube Music.[/yellow]\n")

    cache.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse args and run."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        run(args)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(130)
    except Exception as exc:
        console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
