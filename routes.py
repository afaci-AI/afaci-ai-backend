"""Подключение роутеров всех фич к приложению."""

from fastapi import FastAPI

from features.app_versions.api import router as app_versions_router
from features.audit.api import router as audit_demo_router
from features.auth.api import router as auth_router
from features.calculator.api import router as calculator_router
from features.catalog.api import router as catalog_router
from features.norms.api import documents_router
from features.norms.api import router as norms_router
from features.products.api import router as products_router
from features.recipes.api import router as recipes_router
from features.table.api import router as table_router
from features.users.api import router as users_router


def register_routers(app: FastAPI) -> None:
    # Порядок сохранён: он влияет на сопоставление путей.
    app.include_router(table_router)
    app.include_router(catalog_router)
    app.include_router(products_router)
    app.include_router(calculator_router)
    app.include_router(norms_router)
    app.include_router(documents_router)
    app.include_router(auth_router)
    app.include_router(recipes_router)
    app.include_router(users_router)
    app.include_router(audit_demo_router)
    app.include_router(app_versions_router)
