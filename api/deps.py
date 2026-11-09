"""DI-зависимости для FastAPI роутеров."""

from core.db.session import get_db  # noqa: F401
from core.security import (  # noqa: F401
    get_current_user,
    get_current_user_optional,
)
