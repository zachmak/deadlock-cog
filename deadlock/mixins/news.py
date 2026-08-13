"""Background poller for Valve's Steam news feed. A single fixed-cadence
engine tick checks which guilds are "due" (per their own configured
interval) and, if any are, fetches the feed once and shares it across all
due guilds that tick.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import discord
from discord.ext import tasks

from ..core.constants import NEWS_ENGINE_TICK_SECONDS
from ..core.errors import UpstreamUnavailableError
from ..core.formatting import build_news_embed

log = logging.getLogger("red.deadlock.news")


class NewsPoller:
    def _start_news_engine(self) -> None:
        if not self._news_engine.is_running():
            self._news_engine.start()

    def _stop_news_engine(self) -> None:
        self._news_engine.cancel()

    @tasks.loop(seconds=NEWS_ENGINE_TICK_SECONDS)
    async def _news_engine(self) -> None:
        # tasks.loop cancels itself permanently on an unhandled exception,
        # so the tick body must never let one escape.
        try:
            await self._run_news_tick()
        except Exception:
            log.exception("Unhandled error in Deadlock news engine tick")

    @_news_engine.before_loop
    async def _before_news_engine(self) -> None:
        await self.bot.wait_until_red_ready()

    async def _run_news_tick(self) -> None:
        now = int(time.time())
        all_guilds: Dict[int, Dict[str, Any]] = await self.config.all_guilds()
        due_ids = [
            gid
            for gid, d in all_guilds.items()
            if d.get("news_enabled")
            and d.get("news_channel_id")
            and (now - (d.get("news_last_checked") or 0))
            >= d.get("news_interval_seconds", 0)
        ]
        if not due_ids:
            return

        try:
            items = await self.steam_news.get_news(count=20, maxlength=0)
        except UpstreamUnavailableError as e:
            log.warning("Deadlock news fetch failed, will retry next tick: %s", e)
            return

        for gid in due_ids:
            guild = self.bot.get_guild(gid)
            await self._process_guild_news(guild, items, now)

    async def _process_guild_news(
        self, guild: Optional[discord.Guild], items: List[Dict[str, Any]], now: int
    ) -> None:
        if guild is None:
            return
        gconf = self.config.guild(guild)
        data = await gconf.all()

        channel = guild.get_channel(data["news_channel_id"])
        if not isinstance(channel, discord.TextChannel):
            # Channel deleted, or config predates a type change -- skip this
            # tick but keep the guild's own cadence rather than retrying
            # every engine tick.
            await gconf.news_last_checked.set(now)
            return

        perms = channel.permissions_for(guild.me)
        if not (perms.send_messages and perms.embed_links):
            await gconf.news_last_checked.set(now)
            return

        filter_mode = data["news_filter"]
        filtered = [
            i
            for i in items
            if filter_mode == "all" or "patchnotes" in i.get("tags", [])
        ]

        if data["news_last_gid"] is None:
            # Belt-and-suspenders seed path: normally already seeded
            # synchronously by `deadlockset news enable`. Nothing is posted
            # here either way.
            if filtered:
                await gconf.news_last_gid.set(str(filtered[0]["gid"]))
                await gconf.news_last_date.set(int(filtered[0]["date"]))
            await gconf.news_last_checked.set(now)
            return

        last_date = data["news_last_date"] or 0
        last_gid = data["news_last_gid"]
        new_items = [
            i
            for i in filtered
            if str(i["gid"]) != last_gid and int(i["date"]) > last_date
        ]
        new_items.sort(key=lambda i: int(i["date"]))  # oldest first, so posts land in order

        for item in new_items:
            try:
                await channel.send(embed=build_news_embed(item))
            except discord.Forbidden:
                # Permissions changed mid-tick; stop posting, retry next due tick.
                break
            except discord.HTTPException:
                continue

        if new_items:
            latest = new_items[-1]
            await gconf.news_last_gid.set(str(latest["gid"]))
            await gconf.news_last_date.set(int(latest["date"]))
        await gconf.news_last_checked.set(now)
