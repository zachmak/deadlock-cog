"""Argument converters and shared command-checks.

PlayerConverter resolves a wide variety of user-supplied player references
(numeric account_id, Steam64 id, a steamcommunity.com/profiles/<id> URL, or a
free-text display name) down to a deadlock-api.com account_id.
HeroConverter resolves free-text hero names against the cached hero list.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import List, Optional

import discord
from discord import app_commands
from redbot.core import commands

from .constants import STEAM_ACCOUNT_ID_OFFSET
from .errors import RateLimitedError, UpstreamUnavailableError

STEAM64_PROFILE_RE = re.compile(r"steamcommunity\.com/profiles/(\d{17})", re.IGNORECASE)
VANITY_URL_RE = re.compile(r"steamcommunity\.com/id/([^/\s]+)", re.IGNORECASE)


@dataclass
class DeadlockPlayer:
    account_id: int
    personaname: Optional[str] = None
    source: str = "id"  # "id" | "url" | "search" | "linked"


def _steam64_to_account_id(value: int) -> int:
    if value >= STEAM_ACCOUNT_ID_OFFSET:
        return value - STEAM_ACCOUNT_ID_OFFSET
    return value


class PlayerConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> DeadlockPlayer:
        arg = argument.strip()
        api = ctx.cog.api

        if arg.isdigit():
            return DeadlockPlayer(account_id=_steam64_to_account_id(int(arg)), source="id")

        if m := STEAM64_PROFILE_RE.search(arg):
            return DeadlockPlayer(
                account_id=_steam64_to_account_id(int(m.group(1))), source="url"
            )

        if VANITY_URL_RE.search(arg):
            raise commands.BadArgument(
                "Vanity Steam URLs (steamcommunity.com/id/...) aren't supported — "
                "use a numeric Steam profile URL, a Steam/account ID, or the "
                "player's display name instead."
            )

        try:
            results = await api.search_players(arg, limit=5)
        except RateLimitedError:
            raise commands.BadArgument(
                "deadlock-api.com is rate-limited right now; try again shortly."
            )
        except UpstreamUnavailableError:
            raise commands.BadArgument(
                "Couldn't reach deadlock-api.com to search for that name."
            )
        if not results:
            raise commands.BadArgument(f"No Deadlock/Steam profiles found matching `{arg}`.")

        best = max(results, key=lambda r: r.get("matches_played_last_30d") or 0)
        return DeadlockPlayer(
            account_id=best["account_id"],
            personaname=best.get("personaname"),
            source="search",
        )


async def resolve_player(
    ctx: commands.Context, player: Optional[DeadlockPlayer]
) -> DeadlockPlayer:
    """Fall back to the caller's linked account when no player argument was given."""
    if player is not None:
        return player
    account_id = await ctx.cog.config.user(ctx.author).account_id()
    if account_id is None:
        raise commands.UserFeedbackCheckFailure(
            "You haven't linked a Steam/Deadlock account. Use "
            f"`{ctx.clean_prefix}deadlock link <name or id>`, or provide a player."
        )
    personaname = await ctx.cog.config.user(ctx.author).personaname()
    return DeadlockPlayer(account_id=account_id, personaname=personaname, source="linked")


class HeroConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> int:
        heroes = await ctx.cog.api.get_heroes()
        return _match_hero(heroes, argument)


def _match_hero(heroes: List[dict], argument: str) -> int:
    arg_lower = argument.strip().lower()
    for h in heroes:
        if h.get("name", "").lower() == arg_lower or h.get("class_name", "").lower() == arg_lower:
            return h["id"]
    names = [h.get("name", "") for h in heroes]
    close = difflib.get_close_matches(argument, names, n=1, cutoff=0.6)
    if close:
        for h in heroes:
            if h.get("name") == close[0]:
                return h["id"]
    raise commands.BadArgument(
        f"No hero found matching `{argument}`."
        + (f" Did you mean `{close[0]}`?" if close else "")
    )


async def hero_autocomplete(
    interaction: discord.Interaction, current: str
) -> List[app_commands.Choice[str]]:
    cog = interaction.client.get_cog("Deadlock")
    if cog is None:
        return []
    try:
        heroes = await cog.api.get_heroes()
    except UpstreamUnavailableError:
        return []
    current_lower = current.lower()
    matches = [
        h.get("name", "")
        for h in heroes
        if current_lower in h.get("name", "").lower()
    ]
    return [app_commands.Choice(name=n, value=n) for n in matches[:25]]


def stats_enabled_check():
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            return True
        return await ctx.cog.config.guild(ctx.guild).stats_enabled()

    return commands.check(predicate)
