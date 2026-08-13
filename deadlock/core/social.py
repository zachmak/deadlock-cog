"""Synergy (best teammates) and rivals (toughest enemies) computation.

deadlock-api.com doesn't expose per-player teammate/opponent relationships
directly, so this pulls a player's recent match history and fetches full
match metadata (concurrently) for each of those matches to see the other 11
players in each one, then tallies wins/losses per teammate and per opponent.
This is inherently approximate -- it only reflects however many recent
matches were analyzed, capped by the caller (see mixins/social.py) to keep
the per-invocation API cost and latency bounded.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .api import DeadlockAPIClient
from .errors import DeadlockCogError


async def _fetch_match_safe(
    api: DeadlockAPIClient, match_id: int
) -> Optional[Dict[str, Any]]:
    try:
        return await api.get_match_metadata(match_id)
    except DeadlockCogError:
        # Best-effort aggregation: one unreachable/malformed match shouldn't
        # abort the whole synergy/rivals computation.
        return None


def _to_sorted_rows(bucket: Dict[int, List[int]]) -> List[Dict[str, Any]]:
    rows = [
        {"account_id": aid, "matches": m, "wins": w} for aid, (m, w) in bucket.items()
    ]
    rows.sort(key=lambda r: r["matches"], reverse=True)
    return rows


async def compute_teammates_and_opponents(
    api: DeadlockAPIClient, account_id: int, *, match_limit: int
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    """Returns (teammate_rows, opponent_rows, matches_analyzed).

    Each row is {"account_id", "matches", "wins"} where "wins" counts how
    many of those shared matches the target player (account_id) won --
    i.e. this doubles as a per-teammate/per-opponent win rate.
    """
    history = await api.get_match_history(account_id)
    match_ids = [m["match_id"] for m in history[:match_limit]]
    if not match_ids:
        return [], [], 0

    results = await asyncio.gather(*(_fetch_match_safe(api, mid) for mid in match_ids))

    teammates: Dict[int, List[int]] = defaultdict(lambda: [0, 0])
    opponents: Dict[int, List[int]] = defaultdict(lambda: [0, 0])
    analyzed = 0

    for data in results:
        if data is None:
            continue
        match_info = data.get("match_info") or {}
        players = match_info.get("players") or []
        me = next((p for p in players if p.get("account_id") == account_id), None)
        if me is None:
            continue
        analyzed += 1
        my_team = me.get("team")
        won = match_info.get("winning_team") == my_team

        for p in players:
            other_id = p.get("account_id")
            if other_id is None or other_id == account_id:
                continue
            bucket = teammates if p.get("team") == my_team else opponents
            entry = bucket[other_id]
            entry[0] += 1
            if won:
                entry[1] += 1

    return _to_sorted_rows(teammates), _to_sorted_rows(opponents), analyzed
