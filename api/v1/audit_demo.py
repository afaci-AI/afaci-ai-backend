"""
Демо-эндпоинты для проверки системы аудита.

GET  /api/v1/demo/ping          — проверка INFO лога (2xx)
POST /api/v1/demo/items         — мутация с log_audit_change (Target ID + Changed fields)
PUT  /api/v1/demo/items/{id}    — мутация с декоратором @audit_log
GET  /api/v1/demo/error         — проверка WARNING (4xx) и ERROR (5xx)
"""

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from infrastructure.audit.helpers import audit_log, log_audit_change

router = APIRouter(prefix="/api/v1/demo", tags=["Audit Demo"])

# In-memory хранилище для демо (без БД)
_demo_store: dict[str, dict] = {}


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    role: str | None = None


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    role: str | None = None


@router.get("/ping", summary="[AUDIT DEMO] GET — проверка INFO лога")
async def demo_ping() -> dict:
    """Простой GET — должен попасть в audit.log с level=INFO, status=200."""
    return {"pong": True, "msg": "GET logged as INFO"}


@router.post("/items", status_code=201, summary="[AUDIT DEMO] POST — создание с audit.change")
async def demo_create_item(data: ItemCreate) -> dict:
    """POST — демонстрирует явный вызов log_audit_change."""
    item_id = str(uuid4())
    item = {"id": item_id, "name": data.name, "description": data.description, "role": data.role}
    _demo_store[item_id] = item

    # Логирование деталей изменения (ТЗ п.4)
    log_audit_change(
        action="create_item",
        target_type="DemoItem",
        target_id=item_id,
        changed_fields=data.model_dump(exclude_unset=True),
        actor="demo",  # в реальном роутере — str(current_user.id)
        extra={"store_size": len(_demo_store)},
    )

    return item


@router.put("/items/{id}", summary="[AUDIT DEMO] PUT — обновление с декоратором @audit_log")
@audit_log("update_item", "DemoItem", target_id_arg="id", changed_fields_arg="data")
async def demo_update_item(id: UUID, data: ItemUpdate) -> dict:
    """PUT — демонстрирует декоратор @audit_log.

    Декоратор автоматически извлечёт id и changed_fields из аргументов.
    """
    key = str(id)
    if key not in _demo_store:
        raise HTTPException(status_code=404, detail="Item not found")
    stored = _demo_store[key]
    updates = data.model_dump(exclude_unset=True)
    stored.update(updates)
    return stored


@router.patch("/items/{id}", summary="[AUDIT DEMO] PATCH — обновление с декоратором")
@audit_log("patch_item", "DemoItem", target_id_arg="id", changed_fields_arg="data")
async def demo_patch_item(id: UUID, data: ItemUpdate) -> dict:
    key = str(id)
    if key not in _demo_store:
        raise HTTPException(status_code=404, detail="Item not found")
    stored = _demo_store[key]
    updates = data.model_dump(exclude_unset=True)
    stored.update(updates)
    return stored


@router.delete("/items/{id}", summary="[AUDIT DEMO] DELETE — удаление с log_audit_change")
async def demo_delete_item(id: UUID) -> dict:
    key = str(id)
    if key not in _demo_store:
        raise HTTPException(status_code=404, detail="Item not found")
    del _demo_store[key]

    log_audit_change(
        action="delete_item",
        target_type="DemoItem",
        target_id=str(id),
        changed_fields=None,
        actor="demo",
    )
    return {"status": "deleted", "id": str(id)}


@router.get("/items", summary="[AUDIT DEMO] Список items")
async def demo_list_items() -> list[dict]:
    return list(_demo_store.values())


@router.get("/error-4xx", summary="[AUDIT DEMO] Проверка WARNING (4xx)")
async def demo_4xx() -> dict:
    """Возвращает 400 — middleware должен залогировать с level=WARNING."""
    raise HTTPException(status_code=400, detail="Demo 400 error — should be WARNING")


@router.get("/error-5xx", summary="[AUDIT DEMO] Проверка ERROR (5xx)")
async def demo_5xx() -> dict:
    """Бросает необработанное исключение — middleware логирует с level=ERROR, status 500."""
    raise RuntimeError("Demo 500 error — should be ERROR")
