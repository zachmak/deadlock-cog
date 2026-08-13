"""Composed Deadlock cog. Command groups/subcommands are defined across
`mixins/*.py`, sharing the group objects from `core/groups.py`. See
`core/groups.py`'s module docstring for why each subcommand must be a real
class-body method rather than a module-level function.
"""

from __future__ import annotations

from typing import Any

from redbot.core import Config, commands
from redbot.core.bot import Red

from .core.api import DeadlockAPIClient
from .core.constants import DEFAULT_GUILD, DEFAULT_USER
from .core.groups import deadlock, deadlockset, deadlockset_news
from .core.steamnews import SteamNewsClient
from .mixins.account import AccountCommands
from .mixins.analytics import AnalyticsCommands
from .mixins.news import NewsPoller
from .mixins.profile import ProfileCommands
from .mixins.settings import SettingsCommands

# Fixed forever once released -- do not change.
CONFIG_IDENTIFIER = 3735929292


class Deadlock(
    AccountCommands,
    ProfileCommands,
    AnalyticsCommands,
    SettingsCommands,
    NewsPoller,
    commands.Cog,
):
    """Deadlock player stats, hero/item analytics, leaderboards, and patch-note news."""

    # These must be real class attributes (not just imported names used by
    # decorators in the mixins) so Red's Cog injection discovers them and
    # binds `.cog` on them -- see core/groups.py.
    deadlock = deadlock
    deadlockset = deadlockset
    deadlockset_news = deadlockset_news

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=CONFIG_IDENTIFIER, force_registration=True
        )
        self.config.register_guild(**DEFAULT_GUILD)
        self.config.register_user(**DEFAULT_USER)
        self.api = DeadlockAPIClient(bot)
        self.steam_news = SteamNewsClient(bot)

    async def cog_load(self) -> None:
        self._start_news_engine()

    async def cog_unload(self) -> None:
        self._stop_news_engine()
        await self.api.close()
        await self.steam_news.close()

    async def red_delete_data_for_user(self, *, requester: Any, user_id: int) -> None:
        await self.config.user_from_id(user_id).clear()
