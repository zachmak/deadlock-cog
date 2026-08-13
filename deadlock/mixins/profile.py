"""Player profile/rank and match-history commands. Gated by the per-guild
`stats_enabled` toggle (bypassed automatically in DMs, see
core.converters.stats_enabled_check).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from redbot.core import commands
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu

from ..core.converters import PlayerConverter, resolve_player, stats_enabled_check
from ..core.errors import api_error_handler
from ..core.formatting import build_matches_embeds
from ..core.groups import deadlock
from ..core.lookups import build_full_profile_embed


def _match_won(match: Dict[str, Any]) -> bool:
    """Best-effort win detection from `player_match_outcome`. The exact enum
    mapping wasn't verified against a live payload during design (only a
    sample value of 2 was observed) -- treat this as provisional and confirm
    against real match-history data (a known win vs. a known loss) before
    trusting the win/loss column in `deadlock matches`.
    """
    outcome = match.get("player_match_outcome")
    return outcome == 1


class ProfileCommands:
    @deadlock.command(name="profile", aliases=["rank"])
    @stats_enabled_check()
    async def deadlock_profile(
        self, ctx: commands.Context, *, player: Optional[PlayerConverter] = None
    ) -> None:
        """Show a player's Deadlock profile and rank.

        Defaults to your linked account if no player is given.
        """
        resolved = await resolve_player(ctx, player)
        async with api_error_handler(ctx):
            embed = await build_full_profile_embed(self.api, resolved.account_id)
            await ctx.send(embed=embed)

    @deadlock.command(name="matches", aliases=["history", "mh"])
    @stats_enabled_check()
    async def deadlock_matches(
        self,
        ctx: commands.Context,
        player: Optional[PlayerConverter] = None,
        count: commands.Range[int, 1, 50] = 20,
    ) -> None:
        """Show a player's recent Deadlock match history."""
        resolved = await resolve_player(ctx, player)
        async with api_error_handler(ctx):
            history = await self.api.get_match_history(resolved.account_id)
            hero_names = await self.api.hero_name_map()

            matches = []
            for raw in history[:count]:
                m = dict(raw)
                m["hero_name"] = hero_names.get(
                    m.get("hero_id"), f"Hero {m.get('hero_id')}"
                )
                m["won"] = _match_won(m)
                matches.append(m)

            label = resolved.personaname or str(resolved.account_id)
            pages = build_matches_embeds(player_label=label, matches=matches)
            if len(pages) == 1:
                await ctx.send(embed=pages[0])
            else:
                await menu(ctx, pages, DEFAULT_CONTROLS)
