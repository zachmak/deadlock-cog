"""Admin-only server configuration: `[p]deadlockset ...`. The root
`deadlockset` group is decorated with @commands.guild_only() +
@commands.admin_or_permissions(manage_guild=True) in core/groups.py, and
that gating is enforced for every subcommand (including the nested `news`
group) since discord.py's Group.invoke() runs each parent group's own
checks before dispatching to the child -- no need to re-decorate every leaf.
"""

from __future__ import annotations

from typing import Literal

import discord
from redbot.core import commands

from ..core.constants import NEWS_MIN_INTERVAL_SECONDS
from ..core.errors import UpstreamUnavailableError
from ..core.groups import deadlockset, deadlockset_news


class SettingsCommands:
    @deadlockset.command(name="stats")
    async def deadlockset_stats(self, ctx: commands.Context, enabled: bool) -> None:
        """Enable or disable Deadlock stat commands in this server."""
        await self.config.guild(ctx.guild).stats_enabled.set(enabled)
        state = "enabled" if enabled else "disabled"
        await ctx.send(f"Deadlock stat commands are now {state} in this server.")

    @deadlockset_news.command(name="enable")
    async def deadlockset_news_enable(self, ctx: commands.Context) -> None:
        """Enable the Deadlock news poller in this server."""
        gconf = self.config.guild(ctx.guild)
        await gconf.news_enabled.set(True)
        # Reseed on every disabled->enabled transition (including a fresh
        # first-ever enable) so we never dump a news backlog into the channel.
        await self._seed_news_watermark(ctx.guild)

        channel_id = await gconf.news_channel_id()
        if channel_id is None:
            await ctx.send(
                "Deadlock news is enabled, but no channel is configured yet. "
                f"Set one with `{ctx.clean_prefix}deadlockset news channel <#channel>`."
            )
        else:
            await ctx.send("Deadlock news is now enabled for this server.")

    @deadlockset_news.command(name="disable")
    async def deadlockset_news_disable(self, ctx: commands.Context) -> None:
        """Disable the Deadlock news poller in this server."""
        await self.config.guild(ctx.guild).news_enabled.set(False)
        await ctx.send("Deadlock news is now disabled for this server.")

    @deadlockset_news.command(name="channel")
    async def deadlockset_news_channel(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        """Set the channel Deadlock news is posted to."""
        await self.config.guild(ctx.guild).news_channel_id.set(channel.id)
        perms = channel.permissions_for(ctx.guild.me)
        if not (perms.send_messages and perms.embed_links):
            await ctx.send(
                f"Channel set to {channel.mention}, but I'm missing Send Messages "
                "and/or Embed Links permission there -- news won't post until "
                "that's fixed."
            )
        else:
            await ctx.send(f"Deadlock news will be posted to {channel.mention}.")

    @deadlockset_news.command(name="interval")
    async def deadlockset_news_interval(
        self, ctx: commands.Context, minutes: commands.Range[int, 1, 1440]
    ) -> None:
        """Set how often (in minutes) the news feed is checked. Minimum 5."""
        seconds = minutes * 60
        if seconds < NEWS_MIN_INTERVAL_SECONDS:
            await ctx.send(
                f"Minimum interval is {NEWS_MIN_INTERVAL_SECONDS // 60} minutes."
            )
            return
        await self.config.guild(ctx.guild).news_interval_seconds.set(seconds)
        await ctx.send(f"Deadlock news will now be checked every {minutes} minute(s).")

    @deadlockset_news.command(name="filter")
    async def deadlockset_news_filter(
        self, ctx: commands.Context, mode: Literal["patchnotes", "all"]
    ) -> None:
        """Choose whether to post only patch notes, or all Deadlock news."""
        await self.config.guild(ctx.guild).news_filter.set(mode)
        await ctx.send(f"Deadlock news filter set to `{mode}`.")

    @deadlockset.command(name="showsettings", aliases=["settings"])
    async def deadlockset_showsettings(self, ctx: commands.Context) -> None:
        """Show the current Deadlock configuration for this server."""
        data = await self.config.guild(ctx.guild).all()
        channel = (
            ctx.guild.get_channel(data["news_channel_id"])
            if data["news_channel_id"]
            else None
        )
        embed = discord.Embed(title="Deadlock Settings", color=await ctx.embed_color())
        embed.add_field(
            name="Stats commands",
            value="Enabled" if data["stats_enabled"] else "Disabled",
            inline=True,
        )
        embed.add_field(
            name="News poller",
            value="Enabled" if data["news_enabled"] else "Disabled",
            inline=True,
        )
        embed.add_field(
            name="News channel",
            value=channel.mention if channel else "Not set",
            inline=True,
        )
        embed.add_field(
            name="News interval",
            value=f"{data['news_interval_seconds'] // 60} minute(s)",
            inline=True,
        )
        embed.add_field(name="News filter", value=data["news_filter"], inline=True)
        last_checked = data["news_last_checked"]
        embed.add_field(
            name="Last checked",
            value=f"<t:{last_checked}:R>" if last_checked else "Never",
            inline=True,
        )
        await ctx.send(embed=embed)

    async def _seed_news_watermark(self, guild: discord.Guild) -> None:
        """Fetch the latest news and record it as the watermark WITHOUT
        posting anything, so enabling the feed never dumps old news into
        the channel.
        """
        try:
            items = await self.steam_news.get_news(count=5, maxlength=0)
        except UpstreamUnavailableError:
            # Leave the watermark as None; the poll loop's own seed path
            # will pick it up on the first successful tick instead.
            return
        filter_mode = await self.config.guild(guild).news_filter()
        filtered = [
            i
            for i in items
            if filter_mode == "all" or "patchnotes" in i.get("tags", [])
        ]
        if filtered:
            latest = filtered[0]
            await self.config.guild(guild).news_last_gid.set(str(latest["gid"]))
            await self.config.guild(guild).news_last_date.set(int(latest["date"]))
