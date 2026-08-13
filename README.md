# Deadlock Cog

A [Red-DiscordBot](https://docs.discord.red/) V3 cog for the game
[Deadlock](https://playdeadlock.com/). Provides:

- Player profile/rank lookup, match history, hero and item win-rate
  analytics, and regional leaderboards, backed by the community API at
  [deadlock-api.com](https://deadlock-api.com/).
- A per-server configurable poller for Valve's Steam news feed
  (`ISteamNews/GetNewsForApp`) that posts new patch notes (or all Deadlock
  news, if configured) to a channel of your choice.

Both features can be independently enabled/disabled per server, with
per-server configuration for the news channel, poll interval, and filter
mode.

This cog is not endorsed by Valve and does not reflect the views or opinions
of Valve or anyone officially involved in producing or managing Valve
properties. Stat data is provided by the third-party
[deadlock-api.com](https://deadlock-api.com/) project, not Valve.

## Installation

```
[p]repo add deadlock-cog https://github.com/zachmak/deadlock-cog
[p]cog install deadlock-cog deadlock
[p]load deadlock
```

Optionally, if you have a deadlock-api.com API key (obtained via
[Patreon](https://www.patreon.com/c/user?u=68961896) or
[GitHub Sponsors](https://github.com/sponsors/raimannma)) for higher rate
limits:

```
[p]set api deadlockapi api_key,<your-key>
```

This is optional — the cog works without a key, subject to deadlock-api.com's
public unauthenticated rate limits.

## Commands

### Player stats (`[p]deadlock`, alias `[p]dl`)

| Command | Description |
|---|---|
| `deadlock link <player>` | Link your Discord account to a Deadlock/Steam account. |
| `deadlock unlink` | Remove your linked account. |
| `deadlock whoami` | Show your linked account and current rank. |
| `deadlock profile [player]` | Show a player's profile and rank (defaults to your linked account). |
| `deadlock matches [player] [count]` | Show a player's recent match history. |
| `deadlock heroes [sort] [min_matches]` | Global hero win-rate leaderboard. |
| `deadlock items [sort] [min_matches]` | Global item win-rate leaderboard. |
| `deadlock leaderboard <region> [hero]` | Regional ranked player leaderboard. |

`<player>` accepts a Steam64 ID, a numeric deadlock-api `account_id`, a
`steamcommunity.com/profiles/<id>` URL, or a display name (resolved via
deadlock-api's player search). Vanity Steam URLs
(`steamcommunity.com/id/<name>`) are not supported.

### Server configuration (`[p]deadlockset`, admin-only)

| Command | Description |
|---|---|
| `deadlockset stats <true/false>` | Enable/disable stat commands in this server. |
| `deadlockset news enable` / `disable` | Enable/disable the news poller in this server. |
| `deadlockset news channel <#channel>` | Set the channel news is posted to. |
| `deadlockset news interval <minutes>` | Set the poll interval (minimum 5 minutes). |
| `deadlockset news filter <patchnotes\|all>` | Post only patch notes, or all Deadlock news. |
| `deadlockset showsettings` | Show the current configuration for this server. |

## End-user data

This cog stores the Discord user ID and linked Deadlock/Steam account ID for
users who opt in via `deadlock link`, and per-server configuration (channels,
feature toggles, news watermarks) for server administrators. No message
content is stored.
