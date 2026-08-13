from redbot.core.bot import Red

from .deadlock import Deadlock


async def setup(bot: Red) -> None:
    await bot.add_cog(Deadlock(bot))
