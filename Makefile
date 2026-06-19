.PHONY: help install dev fmt lint typecheck test test-unit test-integration up down logs db-up db-down db-logs db-shell init-db api api-legacy ingest process manifest clean

help:
	@echo "open-data-jalisco — comandos disponibles:"
	@echo ""
	@echo "  install           Instala dependencias (uv sync)"
	@echo "  dev               Instala dependencias + extras de desarrollo"
	@echo "  fmt               Formatea código (ruff format)"
	@echo "  lint              Lint (ruff check)"
	@echo "  typecheck         Type check (mypy)"
	@echo "  test              Corre todos los tests"
	@echo "  test-unit         Solo tests unitarios (sin red, sin DB)"
	@echo "  test-integration  Tests de integración (requieren Postgres)"
	@echo ""
	@echo "  up                Levanta TODO el stack (postgres + api + web) con Docker"
	@echo "  down              Detiene todo el stack"
	@echo "  logs              Sigue los logs de todo el stack"
	@echo ""
	@echo "  db-up             Levanta sólo Postgres+pgvector con Docker"
	@echo "  db-down           Detiene Postgres"
	@echo "  db-logs           Muestra logs de Postgres"
	@echo "  db-shell          Abre psql en el contenedor"
	@echo "  init-db           Crea tablas (idempotente)"
	@echo ""
	@echo "  api               Levanta FastAPI (entry point apps/api/main.py)"
	@echo "  api-legacy        Levanta FastAPI vía open_data_jalisco.api.app:app"
	@echo "  ingest SOURCE=<slug>   Corre el scraper de la fuente"
	@echo "  process            Procesa documentos pendientes (extract + chunk + embed)"
	@echo "  manifest SOURCE=<slug> Genera manifest JSON de auditoría"

install:
	uv sync

dev:
	uv sync --extra dev

fmt:
	uv run ruff format src tests

lint:
	uv run ruff check src tests

typecheck:
	uv run mypy src

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit

test-integration:
	uv run pytest tests/integration -m integration

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

db-logs:
	docker compose logs -f postgres

db-shell:
	docker compose exec postgres psql -U odj -d open_data_jalisco

init-db:
	uv run open-data-jalisco db init

api:
	uv run uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000 --app-dir .

api-legacy:
	uv run uvicorn open_data_jalisco.api.app:app --reload --host 0.0.0.0 --port 8000

ingest:
	uv run open-data-jalisco ingest $(SOURCE)

process:
	uv run open-data-jalisco process

manifest:
	uv run open-data-jalisco manifest $(SOURCE)

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist build
	find . -type d -name __pycache__ -exec rm -rf {} +
