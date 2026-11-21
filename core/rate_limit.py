from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

TOO_MANY = "Слишком много запросов. Попробуйте позже."


async def _handle_rate_limit(_request: Request, _exc: RateLimitExceeded):
    return JSONResponse({"detail": TOO_MANY}, status_code=429)


def register_rate_limit_handler(app: FastAPI) -> None:
    """Превышение лимита — 429 в формате `{"detail": ...}`, а не 500."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _handle_rate_limit)
