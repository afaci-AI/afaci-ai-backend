"""События бизнес-аудита продуктов и форма записи о массовых изменениях."""

from __future__ import annotations

FOOD_CREATED = "FOOD_PRODUCT_CREATED"
FOOD_UPDATED = "FOOD_PRODUCT_UPDATED"
FOOD_DELETED = "FOOD_PRODUCT_DELETED"
FOOD_BULK_CREATED = "FOOD_PRODUCT_BULK_CREATED"

# Одна запись на пачку, а id — не больше этого числа: защита журнала на диске.
_BULK_IDS_LIMIT = 100


def bulk_changes(count: int, ids: list[str], **extra) -> dict:
    return {
        "old": None,
        "new": {
            "count": count,
            "target_ids": ids[:_BULK_IDS_LIMIT],
            **extra,
            "truncated": len(ids) > _BULK_IDS_LIMIT,
        },
    }
