"""Shared hybrid command-group objects.

These are created once, inside a throwaway class body (never instantiated),
and then imported by every mixin module that contributes subcommands to
them. Each subcommand must still be attached as an actual method inside a
class body (via ``@deadlock.command(...)`` etc.) rather than at module
level, for two independent reasons:

1. So Red's Cog machinery discovers it as a class attribute across the
   mixin MRO and correctly binds ``command.cog`` at Cog instantiation.
2. So discord.py's ``discord.utils.is_inside_class()`` (which keys off
   ``func.__qualname__`` containing a dotted class path) correctly detects
   two leading parameters to skip (``self`` and ``ctx``) when computing the
   command's parameter list. A callback defined at plain module level has a
   bare ``__qualname__`` with no dot, so is_inside_class() returns False and
   only ONE leading parameter gets skipped -- leaving ``ctx`` itself
   misidentified as a real command parameter. For a HybridGroup that trips
   Red's own `if not invoke_without_command and self.params: raise TypeError`
   guard in redbot/core/commands/commands.py, since a non-empty `params`
   on a group with the (Red) default `invoke_without_command=False` is
   exactly the case that guard exists to catch. This was found the hard way
   via a live `[p]load` failure -- see git history for the traceback.
"""

from __future__ import annotations

from redbot.core import commands


class _GroupDefs:
    """Never instantiated -- exists purely so the methods below get a
    dotted __qualname__ (see module docstring)."""

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


deadlock = _GroupDefs.deadlock
deadlockset = _GroupDefs.deadlockset
deadlockset_news = _GroupDefs.deadlockset_news
