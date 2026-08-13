"""Exception hierarchy for Deadlock cog API clients, plus a shared Discord-facing
error handler so every command surfaces failures the same, friendly way.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from redbot.core import commands

from .formatting import error_embed

log = logging.getLogger("red.deadlock.errors")


class DeadlockCogError(Exception):
    """Base class for all errors raised by this cog's API clients."""


class PlayerNotFoundError(DeadlockCogError):
    """Raised when a player-scoped endpoint returns 404."""


class RateLimitedError(DeadlockCogError):
    """Raised on HTTP 429. ``retry_after`` is seconds until retry is safe, if known."""

    def __init__(self, retry_after: Optional[float] = None) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limited (retry_after={retry_after!r})")


class UpstreamUnavailableError(DeadlockCogError):
    """Raised on timeouts, network errors, or 5xx responses."""


@asynccontextmanager
async def api_error_handler(ctx: commands.Context) -> AsyncIterator[None]:
    """Wrap API-calling command bodies; turns known errors into a friendly embed
    reply and logs anything unexpected, without letting it bubble up and hit
    Red's generic on_command_error traceback path.
    """
    try:
        yield
    except PlayerNotFoundError:
        await ctx.send(
            embed=error_embed(
                "Not Found", "No Deadlock profile found for that player."
            )
        )
    except RateLimitedError as e:
        suffix = f" Try again in {int(e.retry_after)}s." if e.retry_after else ""
        await ctx.send(
            embed=error_embed(
                "Rate Limited",
                f"deadlock-api.com is rate-limiting requests right now.{suffix}",
            )
        )
    except UpstreamUnavailableError:
        await ctx.send(
            embed=error_embed(
                "Service Unavailable",
                "Couldn't reach deadlock-api.com right now. Please try again shortly.",
            )
        )
    except DeadlockCogError:
        log.exception("Unexpected Deadlock cog error while handling a command")
        await ctx.send(
            embed=error_embed(
                "Error", "Something went wrong talking to deadlock-api.com."
            )
        )
