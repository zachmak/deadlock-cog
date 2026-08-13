"""Small orchestration helpers shared by more than one command (e.g. `deadlock
profile` and `deadlock whoami` both need "fetch profile + rank, build embed").
Kept separate from the mixins since they don't touch Discord's Context.
"""

from __future__ import annotations

import discord

from .api import DeadlockAPIClient
from .errors import PlayerNotFoundError, UpstreamUnavailableError
from .formatting import build_profile_embed
from .stats import filter_ranked, summarize_matches


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

    try:
        history = await api.get_match_history(account_id)
    except UpstreamUnavailableError:
        history = []

    overall = summarize_matches(history)
    ranked_summary = summarize_matches(filter_ranked(history))

    most_played_hero_name = None
    if overall.most_played_hero_id is not None:
        hero_names = await api.hero_name_map()
        most_played_hero_name = hero_names.get(overall.most_played_hero_id)

    season_name = None
    if ranked_summary.total_matches:
        season_name = await api.current_ranked_season_name()

    return build_profile_embed(
        profile=profile,
        rank=rank,
        rank_info=rank_info,
        rank_image_url=rank_image_url,
        overall=overall,
        most_played_hero_name=most_played_hero_name,
        ranked_summary=ranked_summary,
        season_name=season_name,
    )
