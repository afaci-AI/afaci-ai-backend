# Docker-инфраструктура AFACI

Три сервиса: `db` (PostgreSQL 16), `backend` (FastAPI), `frontend` (Next.js).

## Требуемая структура на диске

Compose ссылается на исходники обоих репозиториев по относительному пути,
поэтому они должны лежать рядом:

```
afaci_project_intelect/
├── afaci/              ← этот репозиторий (backend), Dockerfile в корне
│   └── docker/          ← вы здесь: docker-compose.yml, .env, Makefile
└── afaci-frontend/      ← фронтенд-репозиторий, Dockerfile в корне
```

## Запуск

```bash
cd afaci/docker
cp .env.example .env      # и заполнить реальными значениями
docker compose up --build -d
# или: make up
```

- Backend: http://localhost:8000/docs
- Frontend: http://localhost:80
- Postgres (для локальной отладки, DBeaver/psql): localhost:5432

Порядок старта гарантирован через `depends_on: condition: service_healthy` —
backend не стартует, пока Postgres не пройдёт `pg_isready`, frontend не
стартует, пока backend не ответит на HEALTHCHECK (`/docs`).

## Остановка

```bash
docker compose down       # контейнеры, volume с данными БД сохраняется
# или: make down
```

## Полная очистка (удаляет данные БД!)

```bash
docker compose down -v
# или: make clean
```

## Загрузка данных в БД

См. [db/init/README.md](db/init/README.md):
- при **первом** запуске — положить `*.sql` в `db/init/`, подхватится через
  `/docker-entrypoint-initdb.d` автоматически;
- в **уже работающий** контейнер — `make seed` (сиды калькулятора) или
  `make restore FILE=../backups/<dump>.sql` (полный дамп), без пересборки
  и без остановки остальных сервисов.

## Пересборка одного сервиса

```bash
docker compose build backend && docker compose up -d backend
```
