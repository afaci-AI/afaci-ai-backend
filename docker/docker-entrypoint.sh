#!/bin/sh
set -e

# APK-хранилище монтируется как docker volume (инициализируется от root —
# при первом создании, а также на старых volume) — приводим права
# под пользователя приложения. Root активен только на этом bootstrap-шаге,
# далее весь процесс выполняет непривилегированный пользователь afaci.
mkdir -p /app/uploads/apk
chown -R afaci:afaci /app/uploads/apk

# При сбросе привилегий HOME не переключается сам (важно для asyncpg,
# который ищет клиентские сертификаты в ~/.postgresql).
export HOME=/home/afaci

echo "[entrypoint] applying alembic migrations..."
setpriv --reuid=1000 --regid=1000 --init-groups alembic upgrade head

echo "[entrypoint] starting app..."
exec setpriv --reuid=1000 --regid=1000 --init-groups "$@"
