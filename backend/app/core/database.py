from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Dedicated audit session factory — uses NullPool so each audit write gets
# its own exclusive connection.  asyncpg raises InterfaceError if two
# coroutines share the same connection concurrently; NullPool prevents that
# by never putting connections back into a shared pool.
_audit_engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
audit_session = async_sessionmaker(_audit_engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
