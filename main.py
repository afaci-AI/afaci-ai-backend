import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware
from starlette.staticfiles import StaticFiles

from api.openapi import OPENAPI_TAGS
from api.rate_limit import limiter
from api.router import register_routers
from infrastructure.audit.logger import setup_audit_logging
from infrastructure.audit.middleware import AuditLogMiddleware

load_dotenv()

# Инициализируем аудит-логгер до создания app (создаст logs/, настроит ротацию)
setup_audit_logging()

app = FastAPI(title="AFACI API", openapi_tags=OPENAPI_TAGS)
app.state.limiter = limiter

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

# SlowAPI должен быть добавлен последним, чтобы быть наиболее внешним
# и ловить запросы до остальных middleware.
app.add_middleware(SlowAPIMiddleware)

# Статическая раздача APK-файлов (папка примонтирована через docker volume)
# Относительный путь работает и локально, и в контейнере (workdir=/app).
apk_path = os.getenv("APK_STORAGE_PATH", "uploads/apk")
os.makedirs(apk_path, exist_ok=True)
app.mount("/static/apk", StaticFiles(directory=apk_path), name="apk")

register_routers(app)
