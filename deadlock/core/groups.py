"""Shared hybrid command-group objects.

These are created once, at module import time, and then imported by every
mixin module that contributes subcommands to them. Each subcommand must
still be attached as an actual method inside a class body (via
``@deadlock.command(...)`` etc.) rather than at module level, so that Red's
Cog machinery discovers it as a class attribute across the mixin MRO and
correctly binds ``command.cog`` at Cog instantiation.
"""

from __future__ import annotations

from redbot.core import commands


@commands.hybrid_group(name="deadlock", aliases=["dl"])
async def deadlock(self, ctx: commands.Context) -> None:
    """Deadlock player stats, leaderboards, and account linking."""


@commands.hybrid_group(name="deadlockset")
@commands.guild_only()
@commands.admin_or_permissions(manage_guild=True)
async def deadlockset(self, ctx: commands.Context) -> None:
    """Configure the Deadlock cog for this server."""


@deadlockset.group(name="news")
async def deadlockset_news(self, ctx: commands.Context) -> None:
    """Configure the Deadlock news poller for this server."""
