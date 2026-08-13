"""Static constants for the Deadlock cog. No Discord or network dependencies here."""

from __future__ import annotations

# Deadlock's Steam AppID (verified live against the Steam Web API and SteamDB).
STEAM_APP_ID = 1422450

STEAM_NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"

DEADLOCK_API_BASE_URL = "https://api.deadlock-api.com"

# SteamID64 - STEAM_ACCOUNT_ID_OFFSET = SteamID3 account_id (32-bit).
STEAM_ACCOUNT_ID_OFFSET = 76561197960265728

# Regions accepted by GET /v1/leaderboard/{region}.
LEADERBOARD_REGIONS = ["Europe", "Asia", "NAmerica", "SAmerica", "Oceania"]

# How long cached static assets (heroes/items/ranks) are trusted before a
# lazy refresh is attempted on next use.
ASSET_CACHE_TTL_SECONDS = 6 * 60 * 60

# Name under which cog owners register a deadlock-api.com key via
# `[p]set api deadlockapi api_key,<key>`.
DEADLOCK_API_TOKEN_SERVICE = "deadlockapi"

# Engine tick cadence for the news poller background loop. Independent of
# any single guild's configured interval -- guilds are only actually
# processed once their own interval has elapsed.
NEWS_ENGINE_TICK_SECONDS = 60

# Per-guild config bounds/defaults for the news poller.
NEWS_MIN_INTERVAL_SECONDS = 300
NEWS_DEFAULT_INTERVAL_SECONDS = 600

DEFAULT_GUILD = {
    "stats_enabled": True,
    "news_enabled": False,
    "news_channel_id": None,
    "news_interval_seconds": NEWS_DEFAULT_INTERVAL_SECONDS,
    "news_filter": "patchnotes",  # "patchnotes" | "all"
    "news_last_gid": None,
    "news_last_date": None,
    "news_last_checked": None,
}

DEFAULT_USER = {
    "account_id": None,
    "personaname": None,
    "linked_at": None,
}

EMBED_COLOR = 0xF5A623
ERROR_COLOR = 0xE74C3C
