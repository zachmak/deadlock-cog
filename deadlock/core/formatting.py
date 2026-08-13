"""discord.Embed builders. Pure formatting -- callers pass already-resolved,
plain data (hero/item names resolved from the asset cache, etc.) so this
module has no API-client dependency.
"""

from __future__ import annotations

import datetime
import re
from typing import Any, Dict, List, Optional, Sequence

import discord

from .constants import EMBED_COLOR, ERROR_COLOR
from .stats import MatchStatsSummary

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=ERROR_COLOR)


def _strip_html(text: Optional[str]) -> str:
    """deadlock-api's ability/item descriptions embed raw HTML (spans for
    highlighted values, occasional inline SVGs) -- strip tags for a plain
    Discord-friendly line. Not a full HTML parser, just good enough for
    these simple, mostly-flat description strings.
    """
    if not text:
        return ""
    return _HTML_TAG_RE.sub("", text).strip()


def _country_flag(country_code: Optional[str]) -> str:
    if not country_code or len(country_code) != 2:
        return ""
    code = country_code.upper()
    try:
        return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code) + " "
    except ValueError:
        return ""


def _parse_hex_color(color: Optional[str]) -> Optional[int]:
    if not color:
        return None
    try:
        return int(color.lstrip("#"), 16)
    except ValueError:
        return None


def _format_date(ts: Optional[int]) -> str:
    if not ts:
        return "—"
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime(
        "%Y-%m-%d"
    )


def _format_match_duration(seconds: Optional[int]) -> str:
    if seconds is None:
        return "—"
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m {secs}s"


def _rank_label(rank: Optional[Dict[str, Any]], rank_info: Optional[Dict[str, Any]]) -> str:
    if not rank_info:
        return "Unranked"
    label = rank_info.get("name", "Unranked")
    subrank = (rank or {}).get("subrank")
    return f"{label} {subrank}" if subrank else label


def _overall_stats_block(
    overall: MatchStatsSummary, most_played_hero_name: Optional[str]
) -> str:
    lines = []
    if most_played_hero_name:
        lines.append(
            f"**Most Played:** {most_played_hero_name} "
            f"({overall.most_played_hero_matches} matches)"
        )
    lines.append(f"**Total Matches:** {overall.total_matches}")
    if overall.win_rate is not None:
        lines.append(
            f"**Win Rate:** {overall.win_rate:.2%} ({overall.wins}-{overall.losses})"
        )
    if overall.kda is not None:
        lines.append(f"**KDA:** {overall.kda:.2f}")
    lines.append(f"**First Match:** {_format_date(overall.first_match_time)}")
    lines.append(f"**Last Match:** {_format_date(overall.last_match_time)}")
    lines.append(f"**Left Early:** {overall.abandons} time(s)")
    if overall.most_kills is not None:
        lines.append(f"**Most Kills (game):** {overall.most_kills}")
    if overall.most_deaths is not None:
        lines.append(f"**Most Deaths (game):** {overall.most_deaths}")
    if overall.most_assists is not None:
        lines.append(f"**Most Assists (game):** {overall.most_assists}")
    if overall.longest_match_s is not None:
        lines.append(f"**Longest Match:** {_format_match_duration(overall.longest_match_s)}")
    if overall.most_souls is not None:
        lines.append(f"**Most Souls:** {overall.most_souls:,}")
    return "\n".join(lines)


def _ranked_stats_block(
    ranked: MatchStatsSummary, rank: Optional[Dict[str, Any]], rank_info: Optional[Dict[str, Any]]
) -> str:
    lines = [f"**Rank:** {_rank_label(rank, rank_info)}"]
    lines.append(f"**Win Rate:** {ranked.win_rate:.2%} ({ranked.wins}-{ranked.losses})")
    lines.append(f"**KDA:** {ranked.kda:.2f}")
    return "\n".join(lines)


def build_profile_embed(
    *,
    profile: Dict[str, Any],
    rank: Optional[Dict[str, Any]],
    rank_info: Optional[Dict[str, Any]],
    rank_image_url: Optional[str],
    overall: MatchStatsSummary,
    most_played_hero_name: Optional[str] = None,
    ranked_summary: Optional[MatchStatsSummary] = None,
    season_name: Optional[str] = None,
) -> discord.Embed:
    flag = _country_flag(profile.get("countrycode"))
    name = profile.get("personaname") or f"Account {profile.get('account_id')}"
    color = _parse_hex_color((rank_info or {}).get("color")) or EMBED_COLOR
    embed = discord.Embed(
        title=f"{flag}{name}",
        url=profile.get("profileurl"),
        color=color,
    )
    avatar = profile.get("avatarfull") or profile.get("avatarmedium") or profile.get("avatar")
    if avatar:
        embed.set_thumbnail(url=avatar)
    if rank_info:
        rank_icon = (rank_info.get("images") or {}).get("small") or (
            rank_info.get("images") or {}
        ).get("large")
        embed.set_author(name=_rank_label(rank, rank_info), icon_url=rank_icon)
        if rank_image_url:
            embed.set_image(url=rank_image_url)
    elif rank is not None:
        # `rank` was fetched successfully but has no last_match -- this
        # account has never completed a ranked match, distinct from a real
        # (if low) tier, so don't imply an earned rank tier name.
        embed.set_author(name="Unranked")

    if overall.total_matches:
        embed.add_field(
            name="\U0001F4CA Overall Stats",
            value=_overall_stats_block(overall, most_played_hero_name),
            inline=False,
        )
    else:
        embed.add_field(name="\U0001F4CA Overall Stats", value="No match data found.", inline=False)

    if ranked_summary and ranked_summary.total_matches:
        title = (
            f"\U0001F3C6 Ranked — {season_name}" if season_name else "\U0001F3C6 Ranked Stats"
        )
        embed.add_field(
            name=title,
            value=_ranked_stats_block(ranked_summary, rank, rank_info),
            inline=False,
        )

    last_match = (rank or {}).get("last_match") or {}
    if last_match.get("match_id"):
        embed.add_field(
            name="Last Ranked Match",
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

    if overall.total_matches:
        # deadlock-api only has full match history for accounts that have
        # friended one of its Steam bots (Patreon-gated); otherwise it only
        # has whatever matches it happened to observe indirectly, which can
        # be well below the account's true in-game total.
        embed.set_footer(
            text="Match totals reflect what deadlock-api has recorded, which "
            "may be less than your true in-game total."
        )
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
        if total > 1:
            embed.set_footer(text=f"Page {idx}/{total}")
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
    *, rows: List[Dict[str, Any]], sort: str, title: Optional[str] = None
) -> List[discord.Embed]:
    lines = []
    for i, r in enumerate(rows, start=1):
        lines.append(
            f"**{i}. {r['item_name']}** — {r['win_rate']:.1%} WR "
            f"({r['wins']}/{r['matches']} matches)"
        )
    title = title or f"Item Win Rates (sorted by {sort})"
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


def build_hero_info_embed(
    *, hero: Dict[str, Any], abilities: List[Dict[str, Any]]
) -> discord.Embed:
    description = hero.get("description") or {}
    images = hero.get("images") or {}
    embed = discord.Embed(
        title=hero.get("name", "Unknown Hero"),
        description=description.get("role"),
        color=EMBED_COLOR,
    )
    icon = images.get("icon_hero_card") or images.get("icon_image_small")
    if icon:
        embed.set_thumbnail(url=icon)
    background = images.get("background_image")
    if background:
        embed.set_image(url=background)
    playstyle = description.get("playstyle")
    if playstyle:
        embed.add_field(name="Playstyle", value=playstyle, inline=False)
    lore = description.get("lore")
    if lore:
        if len(lore) > 500:
            lore = lore[:500].rsplit(" ", 1)[0] + "…"
        embed.add_field(name="Lore", value=lore, inline=False)
    if abilities:
        lines = []
        for a in abilities:
            quip = (a.get("description") or {}).get("quip")
            label = f"**{a.get('name', 'Unknown')}**"
            lines.append(f"{label} — {quip}" if quip else label)
        embed.add_field(name="Abilities", value="\n".join(lines), inline=False)
    tags = hero.get("tags") or []
    if tags:
        embed.add_field(name="Tags", value=", ".join(tags), inline=True)
    return embed


def build_item_info_embed(*, item: Dict[str, Any]) -> discord.Embed:
    embed = discord.Embed(title=item.get("name", "Unknown Item"), color=EMBED_COLOR)
    image = item.get("shop_image") or item.get("image")
    if image:
        embed.set_thumbnail(url=image)
    desc_text = _strip_html((item.get("description") or {}).get("desc"))
    if desc_text:
        embed.description = desc_text
    tier = item.get("item_tier")
    if tier is not None:
        embed.add_field(name="Tier", value=str(tier), inline=True)
    cost = item.get("cost")
    if cost is not None:
        embed.add_field(name="Cost", value=f"{cost:,}", inline=True)
    slot = item.get("item_slot_type")
    if slot:
        embed.add_field(name="Slot", value=str(slot).title(), inline=True)
    return embed


def build_match_detail_embed(
    *,
    match_info: Dict[str, Any],
    hero_names: Dict[int, str],
    player_names: Dict[int, str],
) -> discord.Embed:
    winning_team = match_info.get("winning_team")
    duration_min = (match_info.get("duration_s") or 0) // 60
    embed = discord.Embed(title=f"Match {match_info.get('match_id')}", color=EMBED_COLOR)
    start_time = match_info.get("start_time")
    if start_time:
        embed.timestamp = datetime.datetime.fromtimestamp(
            start_time, tz=datetime.timezone.utc
        )
    embed.add_field(name="Duration", value=f"{duration_min}m", inline=True)
    if winning_team is not None:
        embed.add_field(name="Winner", value=f"Team {winning_team}", inline=True)

    players = match_info.get("players") or []
    teams = sorted({p.get("team") for p in players if p.get("team") is not None})
    for team in teams:
        team_players = [p for p in players if p.get("team") == team]
        lines = []
        for p in team_players:
            account_id = p.get("account_id")
            name = player_names.get(account_id, f"Player {account_id}")
            hero_name = hero_names.get(p.get("hero_id"), f"Hero {p.get('hero_id')}")
            lines.append(
                f"**{name}** ({hero_name}) — "
                f"{p.get('kills', 0)}/{p.get('deaths', 0)}/{p.get('assists', 0)} — "
                f"{p.get('net_worth', 0):,} souls"
            )
        marker = " \U0001F3C6" if team == winning_team else ""
        embed.add_field(
            name=f"Team {team}{marker}", value="\n".join(lines) or "—", inline=False
        )
    return embed


def build_counter_embeds(
    *, hero_name: str, rows: List[Dict[str, Any]]
) -> List[discord.Embed]:
    lines = []
    for i, r in enumerate(rows, start=1):
        lines.append(
            f"**{i}. {r['hero_name']}** — {r['win_rate']:.1%} WR vs {hero_name} "
            f"({r['wins']}/{r['matches']} matches)"
        )
    title = f"Best Counters to {hero_name}"
    return _paginate_rows(title=title, rows=lines, per_page=10)


def build_top_heroes_embeds(
    *, player_label: str, rows: List[Dict[str, Any]]
) -> List[discord.Embed]:
    lines = []
    for i, r in enumerate(rows, start=1):
        lines.append(
            f"**{i}. {r['hero_name']}** — {r['matches_played']} matches, "
            f"{r['win_rate']:.1%} WR, "
            f"{r['kills_per_min']:.2f}/{r['deaths_per_min']:.2f}/{r['assists_per_min']:.2f} "
            f"KDA per min"
        )
    title = f"Top Heroes — {player_label}"
    return _paginate_rows(title=title, rows=lines, per_page=10)


def build_performance_embed(
    *, player_label: str, tags: List[str], summary: Dict[str, str]
) -> discord.Embed:
    embed = discord.Embed(
        title=f"Playstyle — {player_label}",
        description=(
            "Approximate tags derived from your recent stats, not an "
            "official Deadlock metric."
        ),
        color=EMBED_COLOR,
    )
    if tags:
        embed.add_field(name="Tags", value=" • ".join(tags), inline=False)
    for label, value in summary.items():
        embed.add_field(name=label, value=value, inline=True)
    return embed


def build_social_embeds(
    *,
    title: str,
    player_label: str,
    rows: List[Dict[str, Any]],
    matches_analyzed: int,
) -> List[discord.Embed]:
    lines = []
    for i, r in enumerate(rows, start=1):
        win_rate = (r["wins"] / r["matches"]) if r["matches"] else 0.0
        lines.append(
            f"**{i}. {r.get('name', r['account_id'])}** — {r['matches']} matches, "
            f"{win_rate:.1%} WR"
        )
    pages = _paginate_rows(title=f"{title} — {player_label}", rows=lines, per_page=10)
    note = f"Based on your last {matches_analyzed} analyzed match(es)"
    for page in pages:
        existing = page.footer.text if page.footer else None
        page.set_footer(text=f"{existing} • {note}" if existing else note)
    return pages


def build_random_hero_embed(*, hero: Dict[str, Any]) -> discord.Embed:
    description = hero.get("description") or {}
    embed = discord.Embed(
        title=f"\U0001F3B2 {hero.get('name', 'Unknown Hero')}",
        description=description.get("role"),
        color=EMBED_COLOR,
    )
    images = hero.get("images") or {}
    icon = images.get("icon_hero_card") or images.get("icon_image_small")
    if icon:
        embed.set_image(url=icon)
    return embed
