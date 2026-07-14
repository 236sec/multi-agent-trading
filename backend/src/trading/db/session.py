from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from trading.config import get_settings

settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={
        "server_settings": {"timezone": "UTC"},
    },
)
async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
