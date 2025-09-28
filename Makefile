SHELL := /bin/bash

up:
	docker compose -f infra/compose.dev.yml --env-file infra/.env.dev up -d --build

down:
	docker compose -f infra/compose.dev.yml --env-file infra/.env.dev down -v

logs:
	docker compose -f infra/compose.dev.yml --env-file infra/.env.dev logs -f api

ps:
	docker compose -f infra/compose.dev.yml --env-file infra/.env.dev ps

test:
	docker compose -f infra/compose.dev.yml --env-file infra/.env.dev exec api python -m pytest -q

migrate:
	docker compose -f infra/compose.dev.yml --env-file infra/.env.dev exec api alembic upgrade head

sh:
	docker compose -f infra/compose.dev.yml --env-file infra/.env.dev exec api bash