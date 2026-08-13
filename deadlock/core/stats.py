"""Pure aggregation over a list of match-history entries (as returned by
DeadlockAPIClient.get_match_history) -- powers the "Overall Stats" /
ranked-season breakdown sections of the profile embed. Kept separate from
formatting.py since these are plain data computations, not Discord-facing.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Verified live: matches with a populated ranked_display_badge (i.e. real
# ranked games) all carry match_mode == 4; unranked (match_mode == 1) never
# does. No symbolic enum mapping for match_mode was found in the API docs,
# so this is pinned to the verified integer value.
RANKED_MATCH_MODE = 4


@dataclass
class MatchStatsSummary:
    total_matches: int
    wins: int
    losses: int
    win_rate: Optional[float]
    kda: Optional[float]
    most_played_hero_id: Optional[int]
    most_played_hero_matches: int
    first_match_time: Optional[int]
    last_match_time: Optional[int]
    abandons: int
    most_kills: Optional[int]
    most_deaths: Optional[int]
    most_assists: Optional[int]
    longest_match_s: Optional[int]
    most_souls: Optional[int]


_EMPTY_SUMMARY = MatchStatsSummary(
    total_matches=0,
    wins=0,
    losses=0,
    win_rate=None,
    kda=None,
    most_played_hero_id=None,
    most_played_hero_matches=0,
    first_match_time=None,
    last_match_time=None,
    abandons=0,
    most_kills=None,
    most_deaths=None,
    most_assists=None,
    longest_match_s=None,
    most_souls=None,
)


def _match_won(m: Dict[str, Any]) -> bool:
    return m.get("match_result") == m.get("player_team")


def summarize_matches(matches: List[Dict[str, Any]]) -> MatchStatsSummary:
    total = len(matches)
    if total == 0:
        return _EMPTY_SUMMARY

    wins = sum(1 for m in matches if _match_won(m))
    total_kills = sum(m.get("player_kills", 0) for m in matches)
    total_deaths = sum(m.get("player_deaths", 0) for m in matches)
    total_assists = sum(m.get("player_assists", 0) for m in matches)

    hero_counts = Counter(
        m.get("hero_id") for m in matches if m.get("hero_id") is not None
    )
    most_played_hero_id, most_played_hero_matches = (
        hero_counts.most_common(1)[0] if hero_counts else (None, 0)
    )

    start_times = [m["start_time"] for m in matches if m.get("start_time")]
    abandons = sum(1 for m in matches if (m.get("abandoned_time_s") or 0) > 0)

    return MatchStatsSummary(
        total_matches=total,
        wins=wins,
        losses=total - wins,
        win_rate=wins / total,
        kda=(total_kills + total_assists) / max(total_deaths, 1),
        most_played_hero_id=most_played_hero_id,
        most_played_hero_matches=most_played_hero_matches,
        first_match_time=min(start_times) if start_times else None,
        last_match_time=max(start_times) if start_times else None,
        abandons=abandons,
        most_kills=max((m.get("player_kills", 0) for m in matches), default=None),
        most_deaths=max((m.get("player_deaths", 0) for m in matches), default=None),
        most_assists=max((m.get("player_assists", 0) for m in matches), default=None),
        longest_match_s=max(
            (m.get("match_duration_s", 0) for m in matches), default=None
        ),
        most_souls=max((m.get("net_worth", 0) for m in matches), default=None),
    )


def filter_ranked(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [m for m in matches if m.get("match_mode") == RANKED_MATCH_MODE]
