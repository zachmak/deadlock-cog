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
from ..core.formatting import (
    build_match_detail_embed,
    build_matches_embeds,
    build_performance_embed,
    build_top_heroes_embeds,
)
from ..core.groups import deadlock
from ..core.lookups import build_full_profile_embed


def _match_won(match: Dict[str, Any]) -> bool:
    """`match_result` is the winning team's id (verified live against
    `winning_team` in /v1/matches/{id}/metadata for the same match), so a
    win is simply the player's own team matching it.
    """
    return match.get("match_result") == match.get("player_team")


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

    @deadlock.command(name="top")
    @stats_enabled_check()
    async def deadlock_top(
        self,
        ctx: commands.Context,
        player: Optional[PlayerConverter] = None,
        count: commands.Range[int, 1, 25] = 10,
    ) -> None:
        """Show a player's best heroes, ranked by matches played."""
        resolved = await resolve_player(ctx, player)
        async with api_error_handler(ctx):
            raw = await self.api.get_player_hero_stats(resolved.account_id)
            hero_names = await self.api.hero_name_map()

            rows = []
            for r in raw:
                matches_played = r.get("matches_played", 0)
                if matches_played <= 0:
                    continue
                rows.append(
                    {
                        "hero_name": hero_names.get(
                            r.get("hero_id"), f"Hero {r.get('hero_id')}"
                        ),
                        "matches_played": matches_played,
                        "win_rate": r.get("wins", 0) / matches_played,
                        "kills_per_min": r.get("kills_per_min", 0.0),
                        "deaths_per_min": r.get("deaths_per_min", 0.0),
                        "assists_per_min": r.get("assists_per_min", 0.0),
                    }
                )
            rows.sort(key=lambda r: r["matches_played"], reverse=True)
            rows = rows[:count]

            label = resolved.personaname or str(resolved.account_id)
            pages = build_top_heroes_embeds(player_label=label, rows=rows)
            if len(pages) == 1:
                await ctx.send(embed=pages[0])
            else:
                await menu(ctx, pages, DEFAULT_CONTROLS)

    @deadlock.command(name="performance", aliases=["playstyle"])
    @stats_enabled_check()
    async def deadlock_performance(
        self, ctx: commands.Context, *, player: Optional[PlayerConverter] = None
    ) -> None:
        """Show an approximate playstyle breakdown derived from your hero stats.

        These tags are a simple heuristic computed from your aggregate
        stats, not an official Deadlock feature -- treat them as a fun
        approximation, not a precise classification.
        """
        resolved = await resolve_player(ctx, player)
        async with api_error_handler(ctx):
            raw = await self.api.get_player_hero_stats(resolved.account_id)
            if not raw:
                await ctx.send("No match data found for that player.")
                return

            total_matches = sum(r.get("matches_played", 0) for r in raw)
            total_wins = sum(r.get("wins", 0) for r in raw)
            total_kills = sum(r.get("kills", 0) for r in raw)
            total_deaths = sum(r.get("deaths", 0) for r in raw)
            total_assists = sum(r.get("assists", 0) for r in raw)
            total_damage = sum(r.get("total_player_damage", 0) for r in raw)
            total_time_s = sum(r.get("time_played", 0) for r in raw)

            minutes = (total_time_s / 60) or 1.0
            kda = (total_kills + total_assists) / max(total_deaths, 1)
            damage_per_min = total_damage / minutes
            deaths_per_min = total_deaths / minutes
            kills_per_min = total_kills / minutes

            tags = []
            if kda >= 3.0 and damage_per_min >= 500:
                tags.append("Hard Carry")
            if total_assists > 0 and total_assists >= total_kills * 2:
                tags.append("Support")
            if deaths_per_min <= 0.15:
                tags.append("Survivor")
            if kills_per_min >= 0.5:
                tags.append("Aggressive")
            if not tags:
                tags.append("Balanced")

            win_rate = (total_wins / total_matches) if total_matches else 0.0
            summary = {
                "Matches": str(total_matches),
                "Win Rate": f"{win_rate:.1%}",
                "KDA": f"{kda:.2f}",
                "Damage/min": f"{damage_per_min:.0f}",
            }
            label = resolved.personaname or str(resolved.account_id)
            embed = build_performance_embed(player_label=label, tags=tags, summary=summary)
            await ctx.send(embed=embed)

    @deadlock.command(name="match")
    @stats_enabled_check()
    async def deadlock_match(self, ctx: commands.Context, match_id: int) -> None:
        """Show a full breakdown for a specific Deadlock match ID."""
        async with api_error_handler(ctx):
            data = await self.api.get_match_metadata(match_id)
            match_info = data.get("match_info") or {}
            players = match_info.get("players") or []
            account_ids = [
                p["account_id"] for p in players if p.get("account_id") is not None
            ]

            hero_names = await self.api.hero_name_map()
            profiles = (
                await self.api.get_players_by_id(account_ids) if account_ids else []
            )
            player_names = {
                p["account_id"]: p.get("personaname") or str(p["account_id"])
                for p in profiles
            }

            embed = build_match_detail_embed(
                match_info=match_info, hero_names=hero_names, player_names=player_names
            )
            await ctx.send(embed=embed)
