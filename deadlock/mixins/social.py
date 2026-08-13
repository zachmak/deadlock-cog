"""Synergy (best teammates) and rivals (toughest opponents) commands,
derived from recent match history since deadlock-api.com doesn't expose
these relationships directly -- see core/social.py for the computation.
Gated by the per-guild `stats_enabled` toggle.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from redbot.core import commands
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu

from ..core.converters import DeadlockPlayer, PlayerConverter, resolve_player, stats_enabled_check
from ..core.errors import api_error_handler
from ..core.formatting import build_social_embeds
from ..core.groups import deadlock
from ..core.social import compute_teammates_and_opponents

MAX_SOCIAL_ROWS = 15


class SocialCommands:
    async def _send_social_result(
        self,
        ctx: commands.Context,
        *,
        resolved: DeadlockPlayer,
        rows: List[Dict[str, Any]],
        title: str,
        analyzed: int,
        empty_message: str,
    ) -> None:
        if not rows:
            await ctx.send(empty_message)
            return
        rows = rows[:MAX_SOCIAL_ROWS]
        account_ids = [r["account_id"] for r in rows]
        profiles = await self.api.get_players_by_id(account_ids)
        names = {
            p["account_id"]: p.get("personaname") or str(p["account_id"])
            for p in profiles
        }
        for r in rows:
            r["name"] = names.get(r["account_id"], str(r["account_id"]))

        label = resolved.personaname or str(resolved.account_id)
        pages = build_social_embeds(
            title=title, player_label=label, rows=rows, matches_analyzed=analyzed
        )
        if len(pages) == 1:
            await ctx.send(embed=pages[0])
        else:
            await menu(ctx, pages, DEFAULT_CONTROLS)

    @deadlock.command(name="synergy")
    @stats_enabled_check()
    async def deadlock_synergy(
        self,
        ctx: commands.Context,
        player: Optional[PlayerConverter] = None,
        matches: commands.Range[int, 1, 20] = 10,
    ) -> None:
        """Show your best teammates from recent matches, by win rate together.

        Analyzes your last `matches` games (default 10, max 20). This makes
        one extra API call per match analyzed, so it may take a few seconds.
        """
        resolved = await resolve_player(ctx, player)
        async with api_error_handler(ctx):
            async with ctx.typing():
                teammates, _opponents, analyzed = await compute_teammates_and_opponents(
                    self.api, resolved.account_id, match_limit=matches
                )
            await self._send_social_result(
                ctx,
                resolved=resolved,
                rows=teammates,
                title="Best Teammates",
                analyzed=analyzed,
                empty_message="Not enough recent match data to compute synergy.",
            )

    @deadlock.command(name="rivals")
    @stats_enabled_check()
    async def deadlock_rivals(
        self,
        ctx: commands.Context,
        player: Optional[PlayerConverter] = None,
        matches: commands.Range[int, 1, 20] = 10,
    ) -> None:
        """Show your toughest opponents from recent matches.

        Analyzes your last `matches` games (default 10, max 20). This makes
        one extra API call per match analyzed, so it may take a few seconds.
        """
        resolved = await resolve_player(ctx, player)
        async with api_error_handler(ctx):
            async with ctx.typing():
                _teammates, opponents, analyzed = await compute_teammates_and_opponents(
                    self.api, resolved.account_id, match_limit=matches
                )
            await self._send_social_result(
                ctx,
                resolved=resolved,
                rows=opponents,
                title="Toughest Rivals",
                analyzed=analyzed,
                empty_message="Not enough recent match data to compute rivals.",
            )
