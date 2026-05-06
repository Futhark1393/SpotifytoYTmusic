"""
Fuzzy matching engine – searches YouTube Music and picks the best
result using rapidfuzz similarity scoring.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from rapidfuzz import fuzz

from utils import normalize_text

logger = logging.getLogger("spotify2ytmusic")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class MatchResult:
    """Outcome of attempting to match a Spotify track on YouTube Music."""

    video_id: str
    title: str
    score: float


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------

class TrackMatcher:
    """Finds the best YouTube Music match for a given Spotify track.

    Attributes:
        threshold: Minimum similarity score (0–100) to accept a match.
        top_n: Number of YouTube search results to evaluate.
    """

    def __init__(
        self,
        ytmusic_client: "YTMusicClient",  # noqa: F821 – forward ref
        threshold: float = 80.0,
        top_n: int = 5,
    ) -> None:
        self._yt = ytmusic_client
        self.threshold = threshold
        self.top_n = top_n

    def find_best_match(
        self,
        query: str,
    ) -> tuple[Optional[MatchResult], list[MatchResult]]:
        """Search YouTube Music for *query* and return the best fuzzy match and candidates.

        Args:
            query: Search string, typically "artist - track name".

        Returns:
            A tuple of (MatchResult if a hit exceeds *threshold* else None, list of candidates).
        """
        results = self._yt.search(query, limit=self.top_n)
        if not results:
            logger.debug("No YTMusic results for: %s", query)
            return None, []

        normalised_query = normalize_text(query)
        candidates: list[MatchResult] = []
        best: Optional[MatchResult] = None
        best_score: float = 0.0

        for item in results:
            video_id = item.get("videoId")
            if not video_id:
                continue

            # Build candidate string from result metadata
            title = item.get("title", "")
            artists_list = item.get("artists") or []
            artist_names = ", ".join(a.get("name", "") for a in artists_list)
            candidate = f"{artist_names} - {title}" if artist_names else title

            normalised_candidate = normalize_text(candidate)
            score = fuzz.token_sort_ratio(normalised_query, normalised_candidate)
            
            candidates.append(MatchResult(video_id=video_id, title=candidate, score=score))

            logger.debug(
                "  candidate: %-60s  score: %.1f", candidate[:60], score
            )

            if score > best_score:
                best_score = score
                best = candidates[-1]

        # Sort candidates by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)

        if best and best.score >= self.threshold:
            logger.debug("Best match for '%s': %s (%.1f)", query, best.title, best.score)
            return best, candidates

        logger.debug(
            "No match above threshold (%.0f) for: %s (best was %.1f)",
            self.threshold,
            query,
            best_score,
        )
        return None, candidates
