"""
Database connection management
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings
from app.database.models.base import BaseModel
import logging

logger = logging.getLogger(__name__)

# Создание async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)

# Создание session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Base для моделей (импортируем из моделей)
Base = BaseModel


async def init_db():
    """Инициализация базы данных"""
    try:
        # Создание таблиц (в production лучше использовать Alembic migrations)
        async with engine.begin() as conn:
            # await conn.run_sync(Base.metadata.create_all)
            pass  # Раскомментировать для разработки
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_db():
    """Закрытие соединения с базой данных"""
    try:
        await engine.dispose()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Failed to close database connection: {e}")


async def get_db() -> AsyncSession:
    """Dependency для получения сессии базы данных"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


_sync_engine = None
_SyncSessionLocal = None


def get_db_sync():
    """
    Получение синхронной сессии БД (для Celery worker и скриптов).
    Внимание: не использовать в async коде!
    """
    global _sync_engine, _SyncSessionLocal
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    if _sync_engine is None:
        url = settings.database_url
        if url.startswith("postgresql+asyncpg"):
            url = url.replace("postgresql+asyncpg", "postgresql", 1)
        _sync_engine = create_engine(url, echo=settings.DEBUG)
        _SyncSessionLocal = sessionmaker(
            _sync_engine,
            autocommit=False,
            autoflush=False,
        )
    return _SyncSessionLocal()
