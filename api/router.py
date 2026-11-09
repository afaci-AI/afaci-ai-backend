from fastapi import FastAPI

from api.v1 import (
    app_version,
    audit_demo,
    auth,
    products,
    table,
    users,
)
from features.calculator.api import router as calculator_router
from features.norms.api import documents_router
from features.norms.api import router as norms_router
from features.recipes.api import router as recipes_router


def register_routers(app: FastAPI) -> None:
    app.include_router(table.router)
    app.include_router(products.router)
    app.include_router(calculator_router)
    app.include_router(norms_router)
    app.include_router(documents_router)
    app.include_router(auth.router)
    app.include_router(recipes_router)
    app.include_router(users.router)
    app.include_router(audit_demo.router)
    app.include_router(app_version.router)
