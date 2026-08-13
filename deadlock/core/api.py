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
            session = await self._get_session()
            async with session.request(
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

    async def get_player_hero_stats(self, account_id: int) -> List[Dict[str, Any]]:
        """Per-player, per-hero aggregates (matches_played, wins, kills,
        kills_per_min, damage_per_min, accuracy, etc.) -- used for `deadlock
        top` and `deadlock performance`.
        """
        data = await self._request(
            "GET", "/v1/players/hero-stats", params={"account_ids": account_id}
        )
        return data or []

    async def get_match_metadata(self, match_id: int) -> Dict[str, Any]:
        return await self._request("GET", f"/v1/matches/{match_id}/metadata")

    # -- Analytics -----------------------------------------------------------

    async def get_hero_stats(self, **filters: Any) -> List[Dict[str, Any]]:
        data = await self._request("GET", "/v1/analytics/hero-stats", params=filters)
        return data or []

    async def get_item_stats(self, **filters: Any) -> List[Dict[str, Any]]:
        data = await self._request("GET", "/v1/analytics/item-stats", params=filters)
        return data or []

    async def get_hero_counter_stats(self) -> List[Dict[str, Any]]:
        """Full hero x enemy-hero win/loss matrix. Not filterable server-side
        (confirmed live -- an enemy_hero_id query param is silently ignored),
        so this is cached like the static assets and filtered client-side.
        """
        return await self._get_cached_list(
            "hero_counters", "/v1/analytics/hero-counter-stats"
        )

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

    async def items_by_id(self) -> Dict[int, Dict[str, Any]]:
        items = await self.get_items()
        return {i["id"]: i for i in items}

    async def items_by_class_name(self) -> Dict[str, Dict[str, Any]]:
        """/v1/assets/items covers shop items *and* hero weapons/abilities
        (distinguished by a "type" field: "upgrade" | "weapon" | "ability").
        Keyed by class_name since that's how a hero's signature/innate
        abilities reference them in /v1/assets/heroes.
        """
        items = await self.get_items()
        return {i["class_name"]: i for i in items if "class_name" in i}

    async def get_hero_by_id(self, hero_id: int) -> Optional[Dict[str, Any]]:
        heroes = await self.get_heroes()
        for h in heroes:
            if h.get("id") == hero_id:
                return h
        return None

    async def resolve_rank_info(self, badge: Optional[int]) -> Optional[Dict[str, Any]]:
        """Resolve a rank `badge` value (badge = tier * 10 + subrank) to its
        tier's {tier, name, images, color} record from /v1/assets/ranks.
        Falls back to a synthetic {"tier": N, "name": "Tier N"} record if the
        tier isn't found or the assets endpoint is unreachable.
        """
        if badge is None:
            return None
        tier = badge // 10
        fallback = {"tier": tier, "name": f"Tier {tier}", "images": {}, "color": None}
        try:
            ranks = await self.get_ranks()
        except UpstreamUnavailableError:
            return fallback
        for r in ranks:
            if r.get("tier") == tier:
                return r
        return fallback

    async def resolve_rank_name(self, badge: Optional[int]) -> Optional[str]:
        info = await self.resolve_rank_info(badge)
        return info.get("name") if info else None
