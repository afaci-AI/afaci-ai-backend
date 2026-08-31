from fastapi import FastAPI

from api.v1 import (
    app_version,
    audit_demo,
    auth,
    calculator,
    products,
    saved,
    table,
    users,
)


def register_routers(app: FastAPI) -> None:
    app.include_router(table.router)
    app.include_router(products.router)
    app.include_router(calculator.router)
    app.include_router(auth.router)
    app.include_router(saved.router)
    app.include_router(users.router)
    app.include_router(audit_demo.router)
    app.include_router(app_version.router)
