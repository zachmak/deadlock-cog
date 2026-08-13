"""Steam/Deadlock account linking commands. Deliberately NOT gated behind the
per-guild `stats_enabled` toggle -- linking is a per-user action that should
keep working even in a server where stat *lookups* are disabled, and it
always works in DMs.
"""

from __future__ import annotations

import discord
from redbot.core import commands

from ..core.converters import PlayerConverter
from ..core.errors import PlayerNotFoundError, api_error_handler
from ..core.groups import deadlock
from ..core.lookups import build_full_profile_embed


class AccountCommands:
    @deadlock.command(name="link")
    async def deadlock_link(
        self, ctx: commands.Context, *, player: PlayerConverter
    ) -> None:
        """Link your Discord account to a Deadlock/Steam account.

        `player` may be a Steam64 ID, a numeric deadlock-api account ID, a
        steamcommunity.com/profiles/<id> URL, or a display name to search for.
        """
        async with api_error_handler(ctx):
            profiles = await self.api.get_players_by_id([player.account_id])
            if not profiles:
                raise PlayerNotFoundError(f"account_id {player.account_id} not found")
            profile = profiles[0]

            await self.config.user(ctx.author).account_id.set(player.account_id)
            await self.config.user(ctx.author).personaname.set(profile.get("personaname"))
            await self.config.user(ctx.author).linked_at.set(
                int(discord.utils.utcnow().timestamp())
            )

            embed = discord.Embed(
                title="Account Linked",
                description=f"Linked to **{profile.get('personaname') or player.account_id}**.",
                color=await ctx.embed_color(),
            )
            avatar = profile.get("avatarfull") or profile.get("avatar")
            if avatar:
                embed.set_thumbnail(url=avatar)
            await ctx.send(embed=embed)

    @deadlock.command(name="unlink")
    async def deadlock_unlink(self, ctx: commands.Context) -> None:
        """Remove your linked Deadlock/Steam account."""
        account_id = await self.config.user(ctx.author).account_id()
        if account_id is None:
            await ctx.send("You don't have a linked account.")
            return
        await self.config.user(ctx.author).clear()
        await ctx.send("Your linked account has been removed.")

    @deadlock.command(name="whoami", aliases=["linked"])
    async def deadlock_whoami(self, ctx: commands.Context) -> None:
        """Show your linked Deadlock account and current rank."""
        account_id = await self.config.user(ctx.author).account_id()
        if account_id is None:
            await ctx.send(
                "You haven't linked a Deadlock/Steam account. Use "
                f"`{ctx.clean_prefix}deadlock link <name or id>`."
            )
            return
        async with api_error_handler(ctx):
            embed = await build_full_profile_embed(self.api, account_id)
            await ctx.send(embed=embed)
