"""Единая граница транзакции для сценариев справочников."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from .ports import UnitOfWork


@asynccontextmanager
async def transaction(uow: UnitOfWork) -> AsyncIterator[None]:
    """Фиксирует изменения блока; при любом сбое откатывает и пробрасывает его."""
    try:
        yield
        await uow.commit()
    except BaseException:
        await uow.rollback()
        raise
