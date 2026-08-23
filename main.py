from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.openapi import OPENAPI_TAGS
from api.router import register_routers
from infrastructure.audit.logger import setup_audit_logging
from infrastructure.audit.middleware import AuditLogMiddleware

# Инициализируем аудит-логгер до создания app (создаст logs/, настроит ротацию)
setup_audit_logging()

app = FastAPI(title="AFACI API", openapi_tags=OPENAPI_TAGS)

# ВАЖНО: порядок add_middleware — LIFO (последний добавленный — внешний).
# Добавляем AuditLogMiddleware ПЕРВЫМ, затем CORS, чтобы Audit был внешним
# и логировал все запросы включая CORS preflight.
app.add_middleware(AuditLogMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routers(app)
