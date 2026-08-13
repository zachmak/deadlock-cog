"""Global hero/item win-rate analytics and regional leaderboard commands.
Gated by the per-guild `stats_enabled` toggle.
"""

from __future__ import annotations

from typing import Literal, Optional

from discord import app_commands
from redbot.core import commands
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu

from ..core.converters import HeroConverter, hero_autocomplete, stats_enabled_check
from ..core.errors import api_error_handler
from ..core.formatting import (
    build_hero_stats_embeds,
    build_item_stats_embeds,
    build_leaderboard_embeds,
)
from ..core.groups import deadlock

# Must match core.constants.LEADERBOARD_REGIONS -- kept as a literal here
# (rather than built from the constant) so discord.py can generate a native
# slash-command choice dropdown for it.
Region = Literal["Europe", "Asia", "NAmerica", "SAmerica", "Oceania"]


class AnalyticsCommands:
    @deadlock.command(name="heroes", aliases=["herostats"])
    @stats_enabled_check()
    async def deadlock_heroes(
        self,
        ctx: commands.Context,
        sort: Literal["winrate", "matches"] = "winrate",
        min_matches: commands.Range[int, 0, 100000] = 100,
    ) -> None:
        """Show global Deadlock hero win-rate stats."""
        async with api_error_handler(ctx):
            raw = await self.api.get_hero_stats()
            hero_names = await self.api.hero_name_map()

            rows = []
            for r in raw:
                matches = r.get("matches", 0)
                if matches < min_matches:
                    continue
                wins = r.get("wins", 0)
                rows.append(
                    {
                        "hero_name": hero_names.get(
                            r.get("hero_id"), f"Hero {r.get('hero_id')}"
                        ),
                        "matches": matches,
                        "wins": wins,
                        "win_rate": (wins / matches) if matches else 0.0,
                    }
                )
            sort_key = "win_rate" if sort == "winrate" else "matches"
            rows.sort(key=lambda r: r[sort_key], reverse=True)

            pages = build_hero_stats_embeds(rows=rows, sort=sort)
            if len(pages) == 1:
                await ctx.send(embed=pages[0])
            else:
                await menu(ctx, pages, DEFAULT_CONTROLS)

    @deadlock.command(name="items", aliases=["itemstats"])
    @stats_enabled_check()
    async def deadlock_items(
        self,
        ctx: commands.Context,
        sort: Literal["winrate", "matches"] = "winrate",
        min_matches: commands.Range[int, 0, 100000] = 50,
    ) -> None:
        """Show global Deadlock item win-rate stats."""
        async with api_error_handler(ctx):
            raw = await self.api.get_item_stats()
            item_names = await self.api.item_name_map()

            rows = []
            for r in raw:
                matches = r.get("matches", 0)
                if matches < min_matches:
                    continue
                wins = r.get("wins", 0)
                rows.append(
                    {
                        "item_name": item_names.get(
                            r.get("item_id"), f"Item {r.get('item_id')}"
                        ),
                        "matches": matches,
                        "wins": wins,
                        "win_rate": (wins / matches) if matches else 0.0,
                    }
                )
            sort_key = "win_rate" if sort == "winrate" else "matches"
            rows.sort(key=lambda r: r[sort_key], reverse=True)

            pages = build_item_stats_embeds(rows=rows, sort=sort)
            if len(pages) == 1:
                await ctx.send(embed=pages[0])
            else:
                await menu(ctx, pages, DEFAULT_CONTROLS)

    @deadlock.command(name="leaderboard", aliases=["lb", "top"])
    @stats_enabled_check()
    @app_commands.describe(
        region="Region to show the leaderboard for",
        hero="Optional hero name to filter the leaderboard by",
    )
    @app_commands.autocomplete(hero=hero_autocomplete)
    async def deadlock_leaderboard(
        self,
        ctx: commands.Context,
        region: Region,
        *,
        hero: Optional[HeroConverter] = None,
    ) -> None:
        """Show the regional Deadlock ranked player leaderboard."""
        async with api_error_handler(ctx):
            data = await self.api.get_leaderboard(region, hero_id=hero)
            hero_names = await self.api.hero_name_map()

            entries = []
            for e in data.get("entries") or []:
                top_ids = e.get("top_hero_ids") or []
                entries.append(
                    {
                        "rank": e.get("rank"),
                        "account_name": e.get("account_name"),
                        "top_hero_names": [
                            hero_names.get(i, f"Hero {i}") for i in top_ids
                        ],
                    }
                )
            pages = build_leaderboard_embeds(region=region, entries=entries)
            if len(pages) == 1:
                await ctx.send(embed=pages[0])
            else:
                await menu(ctx, pages, DEFAULT_CONTROLS)
