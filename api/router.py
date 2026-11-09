from fastapi import FastAPI

from api.v1 import (
    app_version,
    audit_demo,
    auth,
    users,
)
from features.calculator.api import router as calculator_router
from features.catalog.api import router as catalog_router
from features.norms.api import documents_router
from features.norms.api import router as norms_router
from features.products.api import router as products_router
from features.recipes.api import router as recipes_router
from features.table.api import router as table_router


def register_routers(app: FastAPI) -> None:
    app.include_router(table_router)
    app.include_router(catalog_router)
    app.include_router(products_router)
    app.include_router(calculator_router)
    app.include_router(norms_router)
    app.include_router(documents_router)
    app.include_router(auth.router)
    app.include_router(recipes_router)
    app.include_router(users.router)
    app.include_router(audit_demo.router)
    app.include_router(app_version.router)
