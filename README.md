# AFACI — Backend

FastAPI-бэкенд: каталог продуктов и нутриентов, калькулятор аминокислотного скора
(формулы Липатова), сохранённые рецептуры пользователей, аутентификация (JWT) и
управление пользователями с контролем срока действия учётной записи.

## Стек

- Python 3.10+, FastAPI, SQLAlchemy (async) + asyncpg
- PostgreSQL 15+, Alembic (миграции)
- JWT (PyJWT) + bcrypt для аутентификации

## Архитектура

Слоистая архитектура (см. корневой `CLAUDE.md` для подробностей):

| Слой | Назначение |
|---|---|
| `domain/` | доменная логика и формулы (напр. `domain/calculator/formulas.py`) без зависимостей |
| `application/` | use-case'ы, зависят только от `domain/` |
| `infrastructure/` | БД (`infrastructure/db/`), auth (`infrastructure/auth.py`) |
| `api/` | роутеры FastAPI (`api/v1/*.py`), валидация запросов |

Простой CRUD без доменной логики (например, `api/v1/products.py`) обращается к моделям
напрямую, без отдельного `application/`-слоя.

## Установка и запуск

### 1. Предварительные требования

- Python 3.10+
- PostgreSQL 15+ (БД создаётся с `LC_CTYPE=C` — см. примечание про кириллицу ниже)

### 2. Виртуальное окружение

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Настройка окружения

Скопируйте `.env.example` в `.env` и заполните:

```bash
cp .env.example .env
```

```env
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@localhost/DATA_BASE_NAME

# Аутентификация (JWT)
JWT_SECRET=change-me-to-a-long-random-string
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
```

### 4. Миграции

```bash
alembic upgrade head
```

### 5. Запуск

```bash
uvicorn main:app --reload
```

- API документация (Swagger): http://127.0.0.1:8000/docs
- Базовый префикс API: `/api/v1`

## Основные разделы API

| Роутер | Префикс | Назначение |
|---|---|---|
| `api/v1/auth.py` | `/api/v1/auth` | регистрация, вход, `/me`, смена пароля |
| `api/v1/users.py` | `/api/v1/users` | управление пользователями (только для роли `admin`) |
| `api/v1/products.py` | `/api/v1` | каталог: категории, регионы, продукты, нутриенты |
| `api/v1/calculator.py` | `/api/v1/calculator` | расчёт аминокислотного скора, эталонные белки |
| `api/v1/saved.py` | `/api/v1/saved` | группы и сохранённые рецептуры пользователя |
| `api/v1/table.py` | `/api/v1/table` | табличные выгрузки продуктов |

## Аутентификация и роли

- JWT-токен в заголовке `Authorization: Bearer <token>`.
- Роли: `admin`, `editor`, `viewer`.
- У каждого пользователя есть `access_expires_at` (nullable = безлимитный доступ).
  Срок действия проверяется на **каждом запросе** в `get_current_user`
  (`infrastructure/auth.py`) — при истечении сервер сразу отдаёт `401`, фронтенд
  принудительно разлогинивает пользователя.
- Эндпоинты `/api/v1/users/*` защищены зависимостью `require_admin`.

### Тестовый администратор (локальная БД разработки)

Создан локально командой `POST /api/v1/auth/register` + промоушен роли в БД.
**Это учётные данные только для локальной разработки** — при развёртывании на
общий/прод-контур обязательно смените пароль (через UI: раздел «Пользователи» →
редактирование, либо `POST /api/v1/auth/change-password`).

```
Email:  admin@afaci.local
Пароль: zTxUR78xQGRzsK
Роль:   admin
```

## Примечания по данным

- **Кириллица и ILIKE**: БД создана с `LC_CTYPE=C`, поэтому `ILIKE` не сворачивает
  регистр кириллицы. Все кириллические поиски выполняются в `infrastructure/db/`
  через `lower(name) = lower(:val)` или `pg_trgm`.
- **Аминокислоты**: в БД хранятся в мг/100г продукта; конвертация в г/100г белка
  происходит в `domain/calculator/formulas.py`.

## Полезные команды

```bash
# создать новую миграцию
alembic revision -m "описание"

# применить миграции
alembic upgrade head

# посмотреть текущую версию схемы в БД
alembic current
```
