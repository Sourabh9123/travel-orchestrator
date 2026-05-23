.PHONY: help build up down restart logs ps shell worker-shell migrate test compile lint format isort black clean

COMPOSE ?= docker compose
API_SERVICE ?= api
WORKER_SERVICE ?= worker
PYTHON_PATHS ?= app tests alembic

help:
	@printf "travel-orchestrator commands\n\n"
	@printf "  make build         Build Docker images\n"
	@printf "  make up            Start the full local stack\n"
	@printf "  make down          Stop the stack\n"
	@printf "  make restart       Restart the stack\n"
	@printf "  make logs          Follow API logs\n"
	@printf "  make ps            Show container status\n"
	@printf "  make shell         Open a shell in the API container\n"
	@printf "  make worker-shell  Open a shell in the worker container\n"
	@printf "  make migrate       Run Alembic migrations\n"
	@printf "  make test          Run pytest in the API container\n"
	@printf "  make compile       Compile Python files locally\n"
	@printf "  make lint          Run local ruff, isort, and black checks\n"
	@printf "  make format        Run local isort and black\n"
	@printf "  make isort         Sort local Python imports\n"
	@printf "  make black         Format local Python files with Black\n"
	@printf "  make clean         Remove Python cache artifacts\n"

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

restart: down up

logs:
	$(COMPOSE) logs -f $(API_SERVICE)

ps:
	$(COMPOSE) ps

shell:
	$(COMPOSE) exec $(API_SERVICE) bash

worker-shell:
	$(COMPOSE) exec $(WORKER_SERVICE) bash

migrate:
	$(COMPOSE) exec $(API_SERVICE) alembic upgrade head

test:
	$(COMPOSE) exec $(API_SERVICE) pytest -q

compile:
	python -m compileall $(PYTHON_PATHS)

lint:
	python -m ruff check .
	python -m isort --check-only $(PYTHON_PATHS)
	python -m black --check $(PYTHON_PATHS)

format: isort black

isort:
	python -m isort $(PYTHON_PATHS)

black:
	python -m black $(PYTHON_PATHS)

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache
