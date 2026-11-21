"""Микросостав и прочие показатели рецептуры: S = Σ(Sᵢ·Xᵢ) / 100 по каждому нутриенту."""

from __future__ import annotations


def composition_rows(items: list[dict], field: str) -> list[dict]:
    """
    Строки «нутриент — содержание на 100 г рецептуры» по полю `field` ингредиентов.

    В список входят только нутриенты, известные хотя бы одному ингредиенту с
    ненулевой массой; нутриент, которого нет ни у кого, не показывается.
    `partial` — значение у части ингредиентов неизвестно, сумма неполная:
    отсутствие данных не означает нулевое содержание.
    """
    used = [it for it in items if it["amount_g"] > 0]
    names = sorted({name for it in used for name in it.get(field, {})})
    rows = []
    for name in names:
        known = [it for it in used if name in it.get(field, {})]
        unit = next((it["units"].get(name) for it in known if it.get("units")), None)
        total = sum(it[field][name] * it["amount_g"] for it in known) / 100.0
        rows.append(
            {
                "key": name,
                "name": name,
                "unit": unit,
                "amount": total,
                "partial": len(known) < len(used),
            }
        )
    return rows
