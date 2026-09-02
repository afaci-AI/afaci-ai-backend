import os
import re

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi.middleware import SlowAPIMiddleware

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

# Раздача APK-файлов (папка примонтирована через docker volume).
# Используем кастомный роут вместо StaticFiles, чтобы гарантированно
# отправлять Content-Type: application/vnd.android.package-archive и
# Content-Disposition: attachment — иначе Android Chrome добавляет .zip
# к имени файла (Android игнорирует download-атрибут на <a>).
apk_path = os.getenv("APK_STORAGE_PATH", "uploads/apk")
os.makedirs(apk_path, exist_ok=True)


@app.get("/static/apk/{filename:path}")
async def download_apk(filename: str):
    safe = os.path.normpath(filename)
    if safe.startswith("..") or os.sep in safe or "/" in safe:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    file_path = os.path.join(apk_path, safe)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="APK not found.")

    download_name = re.sub(r"^\d{14}-", "", safe)
    return FileResponse(
        file_path,
        media_type="application/vnd.android.package-archive",
        filename=download_name,
    )


register_routers(app)
