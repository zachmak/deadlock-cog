"""discord.Embed builders. Pure formatting -- callers pass already-resolved,
plain data (hero/item names resolved from the asset cache, etc.) so this
module has no API-client dependency.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Sequence

import discord

from .constants import EMBED_COLOR, ERROR_COLOR

DEADLOCK_ATTRIBUTION = "Stats via deadlock-api.com • not endorsed by Valve"


def error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=ERROR_COLOR)


def _country_flag(country_code: Optional[str]) -> str:
    if not country_code or len(country_code) != 2:
        return ""
    code = country_code.upper()
    try:
        return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code) + " "
    except ValueError:
        return ""


def build_profile_embed(
    *,
    profile: Dict[str, Any],
    rank: Optional[Dict[str, Any]],
    rank_name: Optional[str],
    rank_image_url: Optional[str],
) -> discord.Embed:
    flag = _country_flag(profile.get("countrycode"))
    name = profile.get("personaname") or f"Account {profile.get('account_id')}"
    embed = discord.Embed(
        title=f"{flag}{name}",
        url=profile.get("profileurl"),
        color=EMBED_COLOR,
    )
    avatar = profile.get("avatarfull") or profile.get("avatarmedium") or profile.get("avatar")
    if avatar:
        embed.set_thumbnail(url=avatar)
    if rank and rank_name:
        embed.add_field(name="Rank", value=rank_name, inline=True)
        subrank = rank.get("subrank")
        if subrank is not None:
            embed.add_field(name="Subrank", value=str(subrank), inline=True)
    if rank_image_url:
        embed.set_image(url=rank_image_url)
    last_match = (rank or {}).get("last_match") or {}
    if last_match.get("match_id"):
        embed.add_field(
            name="Last Match",
            value=(
                f"Match `{last_match['match_id']}` — "
                f"rank progress {last_match.get('player_rank_initial_flat_progress', '?')} → "
                f"{last_match.get('player_rank_final_flat_progress', '?')}"
            ),
            inline=False,
        )
    matches_30d = profile.get("matches_played_last_30d")
    if matches_30d is not None:
        embed.add_field(name="Matches (30d)", value=str(matches_30d), inline=True)
    embed.set_footer(text=DEADLOCK_ATTRIBUTION)
    return embed


def _paginate_rows(
    *, title: str, rows: Sequence[str], per_page: int, color: int = EMBED_COLOR
) -> List[discord.Embed]:
    if not rows:
        return [discord.Embed(title=title, description="No data found.", color=color)]
    pages: List[discord.Embed] = []
    chunks = [rows[i : i + per_page] for i in range(0, len(rows), per_page)]
    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        embed = discord.Embed(title=title, description="\n".join(chunk), color=color)
        embed.set_footer(text=f"Page {idx}/{total} • {DEADLOCK_ATTRIBUTION}")
        pages.append(embed)
    return pages


def build_matches_embeds(
    *, player_label: str, matches: List[Dict[str, Any]]
) -> List[discord.Embed]:
    rows = []
    for m in matches:
        result = "\U0001F7E2 Win" if m.get("won") else "\U0001F534 Loss"
        duration_min = (m.get("match_duration_s") or 0) // 60
        rows.append(
            f"**{m.get('hero_name', 'Unknown Hero')}** — {result} — "
            f"{m.get('player_kills', 0)}/{m.get('player_deaths', 0)}/{m.get('player_assists', 0)} "
            f"— {duration_min}m — <t:{int(m.get('start_time', 0))}:R> "
            f"([{m.get('match_id')}])"
        )
    return _paginate_rows(title=f"Recent Matches — {player_label}", rows=rows, per_page=10)


def build_hero_stats_embeds(
    *, rows: List[Dict[str, Any]], sort: str
) -> List[discord.Embed]:
    lines = []
    for i, r in enumerate(rows, start=1):
        lines.append(
            f"**{i}. {r['hero_name']}** — {r['win_rate']:.1%} WR "
            f"({r['wins']}/{r['matches']} matches)"
        )
    title = f"Hero Win Rates (sorted by {sort})"
    return _paginate_rows(title=title, rows=lines, per_page=10)


def build_item_stats_embeds(
    *, rows: List[Dict[str, Any]], sort: str
) -> List[discord.Embed]:
    lines = []
    for i, r in enumerate(rows, start=1):
        lines.append(
            f"**{i}. {r['item_name']}** — {r['win_rate']:.1%} WR "
            f"({r['wins']}/{r['matches']} matches)"
        )
    title = f"Item Win Rates (sorted by {sort})"
    return _paginate_rows(title=title, rows=lines, per_page=10)


def build_leaderboard_embeds(
    *, region: str, entries: List[Dict[str, Any]]
) -> List[discord.Embed]:
    lines = []
    for e in entries:
        heroes = ", ".join(e.get("top_hero_names", [])[:3])
        heroes_suffix = f" — {heroes}" if heroes else ""
        lines.append(f"**#{e.get('rank')}** {e.get('account_name', 'Unknown')}{heroes_suffix}")
    title = f"Deadlock Leaderboard — {region}"
    return _paginate_rows(title=title, rows=lines, per_page=20)


def build_news_embed(item: Dict[str, Any]) -> discord.Embed:
    contents = item.get("contents") or ""
    if len(contents) > 1000:
        contents = contents[:1000].rsplit(" ", 1)[0] + "…"
    embed = discord.Embed(
        title=item.get("title", "Deadlock News"),
        url=item.get("url"),
        description=contents,
        color=EMBED_COLOR,
    )
    date = item.get("date")
    if date:
        embed.timestamp = datetime.datetime.fromtimestamp(date, tz=datetime.timezone.utc)
    author = item.get("author")
    feedlabel = item.get("feedlabel")
    footer_bits = [b for b in (author, feedlabel) if b]
    embed.set_footer(text=" • ".join(footer_bits) if footer_bits else "Deadlock News")
    return embed
