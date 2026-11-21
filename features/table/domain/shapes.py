"""Формы ответов таблиц: сводная, карта нутриентов, дерево продуктов, CSV."""

from __future__ import annotations

import csv
import io

NUTRIENT_COLUMNS = frozenset(
    {
        "product_name",
        "category_name",
        "subcategory_name",
        "region_name",
        "nutrient_name",
        "nutrient_type",
        "unit",
        "quantity",
        "error_rate",
    }
)
PRODUCT_COLUMNS = frozenset(
    {"product_name", "category_name", "subcategory_name", "region_name"}
)
CSV_SORT_COLUMNS = frozenset(
    {"product_name", "region_name", "nutrient_name", "quantity"}
)
CSV_FIELDS = ["product_name", "region_name", "nutrient_name", "quantity"]
DEFAULT_SORT = "product_name"


def safe_sort(sort_by: str, allowed: frozenset[str]) -> str:
    """Колонка сортировки только из белого списка (она подставляется в SQL)."""
    return sort_by if sort_by in allowed else DEFAULT_SORT


def pivot_rows(rows) -> list[dict]:
    """Одна строка на продукт, нутриенты — колонками (`<имя>` и `<имя>_err`)."""
    pivot: dict[str, dict] = {}
    for r in rows:
        key = r["product_id"]
        if key not in pivot:
            pivot[key] = {
                "product_id": r["product_id"],
                "product_name": r["product_name"],
                "category_name": r["category_name"],
                "subcategory_name": r["subcategory_name"],
                "region_name": r["region_name"],
            }
        col = r["nutrient_name"]
        pivot[key][col] = r["quantity"]
        if r["error_rate"] is not None:
            pivot[key][f"{col}_err"] = r["error_rate"]
    return list(pivot.values())


def nutrient_map(rows) -> list[dict]:
    """Продукты в порядке выборки; нутриенты — словарём `имя → количество`."""
    index: dict[str, dict] = {}
    order: list[str] = []
    for r in rows:
        pid = r["product_id"]
        if pid not in index:
            index[pid] = {
                "product_id": pid,
                "product_name": r["product_name"],
                "category_name": r["category_name"],
                "subcategory_name": r["subcategory_name"],
                "region_name": r["region_name"],
                "nutrients": {},
            }
            order.append(pid)
        index[pid]["nutrients"][r["nutrient_name"]] = r["quantity"]
    return [index[pid] for pid in order]


def product_tree(rows) -> dict:
    """Категория → регион → список продуктов."""
    out: dict = {}
    for r in rows:
        cat = r["category_name"]
        reg = r["region_name"]
        if cat not in out:
            out[cat] = {}
        if reg not in out[cat]:
            out[cat][reg] = []
        out[cat][reg].append(
            {
                "product_id": r["product_id"],
                "product_name": r["product_name"],
                "subcategory_name": r["subcategory_name"],
            }
        )
    return out


def nutrients_csv(rows) -> bytes:
    """CSV в utf-8-sig (с BOM): Excel и редакторы корректно читают кириллицу."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
    writer.writeheader()
    writer.writerows([dict(r) for r in rows])
    return buf.getvalue().encode("utf-8-sig")
