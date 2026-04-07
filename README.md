# 1. Настройка и запуск проекта
## Предварительные требования

- Установленный **Python 3.10+**
- Установленный **PostgreSQL 15+**

## Шаги по установке и запуску

### 1. Клонируйте репозиторий
```
git clone <ссылка-на-репозиторий>
cd <название-папки-проекта>
```
### 2. Создайте и активируйте виртуальное окружение
***macOS / Linux:***
```
python3 -m venv venv
source venv/bin/activate
```
***Windows:***
```
python -m venv venv
venv\Scripts\activate
```
### 3. Установите зависимости
```
pip install -r requirements.txt
```
### 4. Настройте подключение к базе данных
1) Создайте БД в PostgreSQL (например, food_db).
2) Скопируйте файл .env.example в .env:
```
cp .env.example .env
```
Откройте файл .env и укажите свои данные для подключения к БД (логин, пароль, название базы).
### 5. Примените миграции (создайте таблицы в БД)
```
alembic upgrade head
```
### 6. Запустите сервер
```
uvicorn main:app --reload
```
### 7. Откройте в браузере
```
Интерфейс: http://127.0.0.1:8000

API документация: http://127.0.0.1:8000/docs (swagger)
```
# 2. SQL БД (Если нужно)
```
-- Расширение для генерации UUID (если не включено)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Справочники
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE subcategories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE regions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE nutrients_types (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE nutrients_names (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE units (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE
);

-- 2. Таблица Продуктов
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    category_id UUID NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    subcategory_id UUID REFERENCES subcategories(id) ON DELETE SET NULL,
    region_id UUID NOT NULL REFERENCES regions(id) ON DELETE RESTRICT
);

-- 3. Таблица Нутриентов
CREATE TABLE nutrients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_product UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    id_name_component UUID NOT NULL REFERENCES nutrients_names(id),
    id_type_component UUID NOT NULL REFERENCES nutrients_types(id),
    unit_id UUID NOT NULL REFERENCES units(id),
    quantity DOUBLE PRECISION,
    
    -- Уникальность: в одном продукте не может быть дубликатов по названию нутриента
    CONSTRAINT uq_product_nutrient UNIQUE (id_product, id_name_component)
);
```