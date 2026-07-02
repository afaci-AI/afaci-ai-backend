# Автоматическая инициализация БД

Файлы, положенные в эту директорию (`*.sql`, `*.sql.gz`, `*.sh`), выполняются
контейнером `postgres` через `/docker-entrypoint-initdb.d` **один раз** —
только когда volume `afaci-pgdata` ещё пустой (первый запуск `docker compose up`).
Порядок выполнения — по алфавиту, поэтому файлы стоит именовать с префиксом
`01_`, `02_` и т.д.

## Как загрузить дамп/сиды при первом запуске

```bash
cp ../../backups/afaci_backup_20260618_124841.sql docker/db/init/01_dump.sql
cp ../../seed_calculator.sql docker/db/init/02_seed_calculator.sql
docker compose -f docker/docker-compose.yml up -d
```

После первого успешного запуска volume больше не пустой — эти скрипты
повторно не выполнятся, даже если положить сюда новые файлы.

## Как загрузить данные в уже работающую БД

Через `make` (см. `docker/Makefile`):

```bash
make seed          # прогоняет seed_calculator.sql через psql внутри контейнера db
make restore FILE=../backups/afaci_backup_20260618_124841.sql
```

Или вручную через `docker exec`:

```bash
docker compose -f docker/docker-compose.yml exec -T db \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < ../seed_calculator.sql
```

## Применение alembic-миграций

Миграции — это не "данные", а схема, и накатываются автоматически при
каждом старте контейнера `backend` (см. `docker-entrypoint.sh` в afaci/).
Прогнать миграции вручную, не перезапуская контейнер:

```bash
docker compose -f docker/docker-compose.yml exec backend alembic upgrade head
```
