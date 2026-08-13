"""HTTP client for api.deadlock-api.com, including a small in-memory cache for
the mostly-static asset endpoints (heroes/items/ranks) so hot commands don't
each pay a network round trip just to resolve an id to a display name.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp
from redbot.core.bot import Red

from .constants import (
    ASSET_CACHE_TTL_SECONDS,
    DEADLOCK_API_BASE_URL,
    DEADLOCK_API_TOKEN_SERVICE,
)
from .errors import PlayerNotFoundError, RateLimitedError, UpstreamUnavailableError

log = logging.getLogger("red.deadlock.api")

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


class DeadlockAPIClient:
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self._asset_cache: Dict[str, tuple[float, List[dict]]] = {}

    async def _get_api_key(self) -> Optional[str]:
        tokens = await self.bot.get_shared_api_tokens(DEADLOCK_API_TOKEN_SERVICE)
        return tokens.get("api_key") or None

    async def _request(
        self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        url = f"{DEADLOCK_API_BASE_URL}{path}"
        headers = {}
        api_key = await self._get_api_key()
        if api_key:
            headers["X-API-KEY"] = api_key

        try:
            async with self.bot.session.request(
                method, url, params=params, headers=headers, timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status == 404:
                    raise PlayerNotFoundError(f"{method} {path} -> 404")
                if resp.status == 429:
                    retry_after = self._parse_retry_after(resp)
                    raise RateLimitedError(retry_after=retry_after)
                if resp.status >= 500:
                    raise UpstreamUnavailableError(f"{method} {path} -> {resp.status}")
                if resp.status >= 400:
                    body = await resp.text()
                    log.warning(
                        "deadlock-api.com %s %s returned %s: %s",
                        method,
                        path,
                        resp.status,
                        body[:500],
                    )
                    raise UpstreamUnavailableError(
                        f"{method} {path} -> {resp.status}"
                    )
                return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise UpstreamUnavailableError(str(e)) from e

    @staticmethod
    def _parse_retry_after(resp: aiohttp.ClientResponse) -> Optional[float]:
        for header in ("ratelimit-reset", "Retry-After", "retry-after"):
            value = resp.headers.get(header)
            if value is None:
                continue
            try:
                parsed = float(value)
            except ValueError:
                continue
            # ratelimit-reset may be an absolute unix timestamp on some
            # backends; treat implausibly large values as absolute and
            # convert to a relative delay. Small values are already a delta.
            if parsed > 1_000_000_000:
                return max(0.0, parsed - time.time())
            return parsed
        return None

    # -- Players -----------------------------------------------------------

    async def search_players(
        self, query: str, *, limit: int = 5
    ) -> List[Dict[str, Any]]:
        data = await self._request(
            "GET",
            "/v1/players/steam-search",
            params={"search_query": query, "limit": limit},
        )
        return data or []

    async def get_players_by_id(self, account_ids: List[int]) -> List[Dict[str, Any]]:
        if not account_ids:
            return []
        data = await self._request(
            "GET",
            "/v1/players/steam",
            params={"account_ids": ",".join(str(a) for a in account_ids)},
        )
        return data or []

    async def get_rank(self, account_id: int) -> Dict[str, Any]:
        return await self._request("GET", f"/v1/players/{account_id}/rank")

    def rank_image_url(self, account_id: int) -> str:
        return f"{DEADLOCK_API_BASE_URL}/v1/players/{account_id}/rank/image"

    async def get_match_history(self, account_id: int) -> List[Dict[str, Any]]:
        data = await self._request(
            "GET", f"/v1/players/{account_id}/match-history"
        )
        return data or []

    # -- Analytics -----------------------------------------------------------

    async def get_hero_stats(self, **filters: Any) -> List[Dict[str, Any]]:
        data = await self._request("GET", "/v1/analytics/hero-stats", params=filters)
        return data or []

    async def get_item_stats(self, **filters: Any) -> List[Dict[str, Any]]:
        data = await self._request("GET", "/v1/analytics/item-stats", params=filters)
        return data or []

    async def get_leaderboard(
        self, region: str, hero_id: Optional[int] = None
    ) -> Dict[str, Any]:
        path = f"/v1/leaderboard/{region}"
        if hero_id is not None:
            path += f"/{hero_id}"
        return await self._request("GET", path)

    # -- Static assets (cached) -----------------------------------------------

    async def _get_cached_list(self, key: str, path: str) -> List[Dict[str, Any]]:
        now = time.monotonic()
        cached = self._asset_cache.get(key)
        if cached and (now - cached[0]) < ASSET_CACHE_TTL_SECONDS:
            return cached[1]
        try:
            data = await self._request("GET", path)
        except UpstreamUnavailableError:
            if cached:
                log.warning(
                    "Failed to refresh %s asset cache; serving stale data", key
                )
                return cached[1]
            raise
        self._asset_cache[key] = (now, data or [])
        return data or []

    async def get_heroes(self) -> List[Dict[str, Any]]:
        return await self._get_cached_list("heroes", "/v1/assets/heroes")

    async def get_items(self) -> List[Dict[str, Any]]:
        return await self._get_cached_list("items", "/v1/assets/items")

    async def get_ranks(self) -> List[Dict[str, Any]]:
        return await self._get_cached_list("ranks", "/v1/assets/ranks")

    async def hero_name_map(self) -> Dict[int, str]:
        heroes = await self.get_heroes()
        return {h["id"]: h.get("name", f"Hero {h['id']}") for h in heroes}

    async def item_name_map(self) -> Dict[int, str]:
        items = await self.get_items()
        return {i["id"]: i.get("name", f"Item {i['id']}") for i in items}

    async def resolve_rank_name(self, badge: Optional[int]) -> Optional[str]:
        """Best-effort tier-name resolution for a rank `badge` value
        (badge = tier * 10 + subrank). The exact /v1/assets/ranks response
        shape wasn't verified against a live payload during design, so this
        degrades gracefully to a numeric tier label if the expected fields
        aren't present -- worth double-checking against a live response
        before relying on it for display polish.
        """
        if badge is None:
            return None
        tier = badge // 10
        try:
            ranks = await self.get_ranks()
        except UpstreamUnavailableError:
            return f"Tier {tier}"
        for r in ranks:
            if r.get("tier") == tier:
                return r.get("name") or r.get("tier_name") or f"Tier {tier}"
        return f"Tier {tier}"
