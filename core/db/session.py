"""Сессия БД. Движок создаётся при первом обращении, а не при импорте модуля,
чтобы импорт слоёв приложения не требовал настроенной переменной DATABASE_URL."""

import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker:
    engine = create_async_engine(os.getenv("DATABASE_URL"), echo=True)
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with _session_factory()() as session:
        try:
            yield session
        finally:
            await session.close()
