SHELL := /bin/bash

.PHONY: help up down logs ps test migrate sh clean-docker

help:
	@echo "Chally Development Commands:"
	@echo "  make up         - Start all services"
	@echo "  make down       - Stop all services and clean volumes"
	@echo "  make logs       - Show API logs"
	@echo "  make ps         - Show running containers"
	@echo "  make test       - Run all tests"
	@echo "  make migrate    - Run database migrations"
	@echo "  make sh         - Open shell in API container"


up:
	# Inject current Git SHA at build time
	GIT_SHA=$$(git rev-parse --short HEAD) docker compose -f infra/compose.dev.yml --env-file infra/.env.dev up -d --build

down:
	docker compose -f infra/compose.dev.yml --env-file infra/.env.dev down -v

logs:
	docker compose -f infra/compose.dev.yml --env-file infra/.env.dev logs -f api

ps:
	docker compose -f infra/compose.dev.yml --env-file infra/.env.dev ps

test:
	@echo "Running all tests..."
	@./backend/tests/scripts/test_all.sh

migrate:
	docker compose -f infra/compose.dev.yml --env-file infra/.env.dev exec api alembic upgrade head

sh:
	docker compose -f infra/compose.dev.yml --env-file infra/.env.dev exec api bash

clean-docker:
	@echo "Stopping and removing all containers, networks, volumes related to the project..."
	docker compose -f infra/compose.dev.yml --env-file infra/.env.dev down -v
	@echo "Pruning unused Docker objects (containers, networks)..."
	docker system prune -f
	@echo "Docker cleanup completed."