"""Единица работы поверх сессии SQLAlchemy: единственное место фиксации и отката."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class SqlUnitOfWork:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def commit(self) -> None:
        await self._db.commit()

    async def rollback(self) -> None:
        await self._db.rollback()

    async def refresh(self, row: object) -> None:
        await self._db.refresh(row)
