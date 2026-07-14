import asyncio

from sqlalchemy import select

from trading.config import get_settings
from trading.db.models import Watchlist
from trading.db.session import async_session


async def seed_watchlist():
    settings = get_settings()
    async with async_session() as session:
        for item in settings.watchlist:
            existing = await session.execute(
                select(Watchlist).where(Watchlist.ticker == item.ticker)
            )
            if existing.scalar_one_or_none() is None:
                session.add(Watchlist(ticker=item.ticker, sector=item.sector))
        await session.commit()


def run_seed():
    asyncio.run(seed_watchlist())
