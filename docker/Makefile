COMPOSE = docker compose -f docker-compose.yml --env-file .env

.PHONY: up down build logs ps seed restore clean

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

# Прогоняет seed_calculator.sql в уже работающем контейнере db,
# без пересборки и без потери накопленных данных.
# $POSTGRES_USER/$POSTGRES_DB разворачиваются ВНУТРИ контейнера (там они уже
# заданы через docker-compose.yml), поэтому используем sh -c, а не host-shell.
seed:
	$(COMPOSE) exec -T db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"' < ../seed_calculator.sql

# make restore FILE=../backups/afaci_backup_20260618_124841.sql
restore:
	@test -n "$(FILE)" || (echo "Использование: make restore FILE=path/to/dump.sql" && exit 1)
	$(COMPOSE) exec -T db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"' < $(FILE)

# Полная очистка: контейнеры + volume с данными БД (необратимо).
clean:
	$(COMPOSE) down -v
