"""Client for Valve's ISteamNews/GetNewsForApp v2 endpoint. No Steam Web API
key is required for this endpoint.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import aiohttp
from redbot.core.bot import Red

from .constants import STEAM_APP_ID, STEAM_NEWS_URL
from .errors import UpstreamUnavailableError

log = logging.getLogger("red.deadlock.steamnews")

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


class SteamNewsClient:
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        # Red's Bot doesn't expose a shared aiohttp session, so this client
        # owns and lazily creates its own, closed via close() from the
        # cog's cog_unload.
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def get_news(
        self, *, count: int = 20, maxlength: int = 0
    ) -> List[Dict[str, Any]]:
        params = {
            "appid": STEAM_APP_ID,
            "count": count,
            "maxlength": maxlength,
            "format": "json",
        }
        try:
            session = await self._get_session()
            async with session.get(
                STEAM_NEWS_URL, params=params, timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    log.warning(
                        "Steam news fetch returned %s: %s", resp.status, body[:500]
                    )
                    raise UpstreamUnavailableError(f"GetNewsForApp -> {resp.status}")
                data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise UpstreamUnavailableError(str(e)) from e

        newsitems = (data.get("appnews") or {}).get("newsitems") or []
        # Don't rely on the API's own ordering being newest-first -- sort
        # explicitly so seeding/dedup logic elsewhere can assume item 0 is
        # the most recent.
        newsitems.sort(key=lambda i: int(i.get("date", 0)), reverse=True)
        return newsitems
