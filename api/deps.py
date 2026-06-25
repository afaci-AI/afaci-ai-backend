"""DI-зависимости для FastAPI роутеров."""
from infrastructure.db.session import get_db  # noqa: F401
from infrastructure.auth import get_current_user, get_current_user_optional  # noqa: F401
