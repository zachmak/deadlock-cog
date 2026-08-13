"""Global hero/item win-rate analytics and regional leaderboard commands.
Gated by the per-guild `stats_enabled` toggle.
"""

from __future__ import annotations

import random
from typing import Literal, Optional

from discord import app_commands
from redbot.core import commands
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu

from ..core.converters import (
    HeroConverter,
    ItemConverter,
    hero_autocomplete,
    item_autocomplete,
    stats_enabled_check,
)
from ..core.errors import api_error_handler
from ..core.formatting import (
    build_counter_embeds,
    build_hero_info_embed,
    build_hero_stats_embeds,
    build_item_info_embed,
    build_item_stats_embeds,
    build_leaderboard_embeds,
    build_news_embed,
    build_random_hero_embed,
)
from ..core.groups import deadlock

MIN_COUNTER_MATCHES = 50
MIN_BUILD_MATCHES = 20

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

    @deadlock.command(name="leaderboard", aliases=["lb", "ladder"])
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

    @deadlock.command(name="hero")
    @stats_enabled_check()
    @app_commands.describe(name="Hero name")
    @app_commands.autocomplete(name=hero_autocomplete)
    async def deadlock_hero(self, ctx: commands.Context, *, name: HeroConverter) -> None:
        """Show info about a hero: lore, role, playstyle, and abilities."""
        async with api_error_handler(ctx):
            hero = await self.api.get_hero_by_id(name)
            if hero is None:
                await ctx.send("Hero not found.")
                return
            ability_map = await self.api.items_by_class_name()
            sig_keys = sorted(
                k for k in (hero.get("items") or {}) if k.startswith("signature")
            )
            abilities = [
                ability_map[hero["items"][k]]
                for k in sig_keys
                if hero["items"][k] in ability_map
            ]
            embed = build_hero_info_embed(hero=hero, abilities=abilities)
            await ctx.send(embed=embed)

    @deadlock.command(name="item")
    @stats_enabled_check()
    @app_commands.describe(name="Item name")
    @app_commands.autocomplete(name=item_autocomplete)
    async def deadlock_item(self, ctx: commands.Context, *, name: ItemConverter) -> None:
        """Show info about a shop item: description, tier, and cost."""
        async with api_error_handler(ctx):
            items_by_id = await self.api.items_by_id()
            item = items_by_id.get(name)
            if item is None:
                await ctx.send("Item not found.")
                return
            embed = build_item_info_embed(item=item)
            await ctx.send(embed=embed)

    @deadlock.command(name="counter", aliases=["counters"])
    @stats_enabled_check()
    @app_commands.describe(hero="Hero to find counters for")
    @app_commands.autocomplete(hero=hero_autocomplete)
    async def deadlock_counter(self, ctx: commands.Context, *, hero: HeroConverter) -> None:
        """Show heroes that counter a given hero, by win rate against them."""
        async with api_error_handler(ctx):
            hero_names = await self.api.hero_name_map()
            target_name = hero_names.get(hero, f"Hero {hero}")

            raw = await self.api.get_hero_counter_stats()
            rows = []
            for r in raw:
                if r.get("enemy_hero_id") != hero:
                    continue
                matches = r.get("matches_played", 0)
                if matches < MIN_COUNTER_MATCHES:
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
            rows.sort(key=lambda r: r["win_rate"], reverse=True)

            pages = build_counter_embeds(hero_name=target_name, rows=rows)
            if len(pages) == 1:
                await ctx.send(embed=pages[0])
            else:
                await menu(ctx, pages, DEFAULT_CONTROLS)

    @deadlock.command(name="build", aliases=["builds"])
    @stats_enabled_check()
    @app_commands.describe(hero="Hero to show the best-performing items for")
    @app_commands.autocomplete(hero=hero_autocomplete)
    async def deadlock_build(self, ctx: commands.Context, *, hero: HeroConverter) -> None:
        """Show the best-performing items for a hero, by win rate."""
        async with api_error_handler(ctx):
            hero_names = await self.api.hero_name_map()
            hero_name = hero_names.get(hero, f"Hero {hero}")

            raw = await self.api.get_item_stats(hero_id=hero)
            item_names = await self.api.item_name_map()
            rows = []
            for r in raw:
                matches = r.get("matches", 0)
                if matches < MIN_BUILD_MATCHES:
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
            rows.sort(key=lambda r: r["win_rate"], reverse=True)

            pages = build_item_stats_embeds(
                rows=rows, sort="winrate", title=f"Best Items — {hero_name}"
            )
            if len(pages) == 1:
                await ctx.send(embed=pages[0])
            else:
                await menu(ctx, pages, DEFAULT_CONTROLS)

    @deadlock.command(name="random", aliases=["randomhero"])
    @stats_enabled_check()
    async def deadlock_random(self, ctx: commands.Context) -> None:
        """Pick a random hero for you to play."""
        async with api_error_handler(ctx):
            heroes = await self.api.get_heroes()
            playable = [
                h for h in heroes if h.get("player_selectable") and not h.get("disabled")
            ]
            if not playable:
                await ctx.send("Couldn't find any heroes right now.")
                return
            hero = random.choice(playable)
            embed = build_random_hero_embed(hero=hero)
            await ctx.send(embed=embed)

    @deadlock.command(name="patch", aliases=["patchnotes"])
    @stats_enabled_check()
    async def deadlock_patch(self, ctx: commands.Context) -> None:
        """Show the latest Deadlock patch notes."""
        async with api_error_handler(ctx):
            # get_news() already sorts newest-first.
            items = await self.steam_news.get_news(count=20, maxlength=0)
            patch_items = [i for i in items if "patchnotes" in i.get("tags", [])]
            if not patch_items:
                await ctx.send("Couldn't find any recent patch notes.")
                return
            embed = build_news_embed(patch_items[0], max_length=3900)
            await ctx.send(embed=embed)
