"""Единая граница транзакции для сценариев фич."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol


class Transactional(Protocol):
    """Единица работы: единственное место фиксации и отката."""

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


@asynccontextmanager
async def transaction(uow: Transactional) -> AsyncIterator[None]:
    """Фиксирует изменения блока; при любом сбое откатывает и пробрасывает его."""
    try:
        yield
        await uow.commit()
    except BaseException:
        await uow.rollback()
        raise
