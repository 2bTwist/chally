SHELL := /bin/bash

up:
	docker compose -f infra/compose.dev.yml up -d --build

down:
	docker compose -f infra/compose.dev.yml down -v

logs:
	docker compose -f infra/compose.dev.yml logs -f api

ps:
	docker compose -f infra/compose.dev.yml ps

test:
	docker compose -f infra/compose.dev.yml exec api -m python pytest -q

sh:
	docker compose -f infra/compose.dev.yml exec api bash