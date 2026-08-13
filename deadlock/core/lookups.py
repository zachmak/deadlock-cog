"""Small orchestration helpers shared by more than one command (e.g. `deadlock
profile` and `deadlock whoami` both need "fetch profile + rank, build embed").
Kept separate from the mixins since they don't touch Discord's Context.
"""

from __future__ import annotations

import discord

from .api import DeadlockAPIClient
from .errors import PlayerNotFoundError
from .formatting import build_profile_embed


async def build_full_profile_embed(api: DeadlockAPIClient, account_id: int) -> discord.Embed:
    profiles = await api.get_players_by_id([account_id])
    profile = profiles[0] if profiles else {"account_id": account_id}

    try:
        rank = await api.get_rank(account_id)
    except PlayerNotFoundError:
        rank = None

    rank_name = await api.resolve_rank_name(rank.get("badge") if rank else None)
    rank_image_url = api.rank_image_url(account_id) if rank else None

    return build_profile_embed(
        profile=profile, rank=rank, rank_name=rank_name, rank_image_url=rank_image_url
    )
