"""Small orchestration helpers shared by more than one command (e.g. `deadlock
profile` and `deadlock whoami` both need "fetch profile + rank, build embed").
Kept separate from the mixins since they don't touch Discord's Context.
"""

from __future__ import annotations

import discord

from .api import DeadlockAPIClient
from .errors import PlayerNotFoundError, UpstreamUnavailableError
from .formatting import build_profile_embed


async def build_full_profile_embed(api: DeadlockAPIClient, account_id: int) -> discord.Embed:
    profiles = await api.get_players_by_id([account_id])
    profile = profiles[0] if profiles else {"account_id": account_id}

    try:
        rank = await api.get_rank(account_id)
    except PlayerNotFoundError:
        rank = None

    # A `badge` of 0 is a valid tier index ("Obscurus"), not a sentinel for
    # "no data" -- the real signal that this account has never played a
    # ranked match is `last_match` being absent (verified live: unranked
    # matches never carry a ranked_display_badge, only match_mode == 4
    # ranked ones do). Treat that as genuinely unranked rather than
    # mislabeling it with a tier name.
    is_ranked = bool(rank and rank.get("last_match"))
    rank_info = await api.resolve_rank_info(rank.get("badge")) if is_ranked else None
    rank_image_url = api.rank_image_url(account_id) if is_ranked else None

    hero_stats = []
    try:
        hero_stats = await api.get_player_hero_stats(account_id)
    except UpstreamUnavailableError:
        pass

    total_matches = sum(h.get("matches_played", 0) for h in hero_stats)
    total_wins = sum(h.get("wins", 0) for h in hero_stats)
    total_kills = sum(h.get("kills", 0) for h in hero_stats)
    total_deaths = sum(h.get("deaths", 0) for h in hero_stats)
    total_assists = sum(h.get("assists", 0) for h in hero_stats)

    win_rate = (total_wins / total_matches) if total_matches else None
    kda = ((total_kills + total_assists) / max(total_deaths, 1)) if total_matches else None

    top_hero_name = None
    if hero_stats:
        hero_names = await api.hero_name_map()
        top = max(hero_stats, key=lambda h: h.get("matches_played", 0))
        top_hero_name = hero_names.get(top.get("hero_id"))

    return build_profile_embed(
        profile=profile,
        rank=rank,
        rank_info=rank_info,
        rank_image_url=rank_image_url,
        total_matches=total_matches,
        win_rate=win_rate,
        kda=kda,
        top_hero_name=top_hero_name,
    )
