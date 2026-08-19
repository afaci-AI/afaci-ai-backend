"""DI-зависимости для FastAPI роутеров."""

from infrastructure.auth import (  # noqa: F401
    get_current_user,
    get_current_user_optional,
)
from infrastructure.db.session import get_db  # noqa: F401
