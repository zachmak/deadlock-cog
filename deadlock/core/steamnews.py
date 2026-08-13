"""Client for Valve's ISteamNews/GetNewsForApp v2 endpoint. No Steam Web API
key is required for this endpoint.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

import aiohttp
from redbot.core.bot import Red

from .constants import STEAM_APP_ID, STEAM_NEWS_URL
from .errors import UpstreamUnavailableError

log = logging.getLogger("red.deadlock.steamnews")

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


class SteamNewsClient:
    def __init__(self, bot: Red) -> None:
        self.bot = bot

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
            async with self.bot.session.get(
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
