.PHONY: help install lint format test run django migrate benchmark-model frontend-format frontend-lint frontend-test frontend-typecheck

export UV_PROJECT_ENVIRONMENT := D:/Ninad/Python/.env
UV = uv run --active --no-cache
PYTHON = D:/Ninad/Python/.env/Scripts/python.exe

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync --locked --extra dev --python 3.14.6

lint: ## Run linters
	$(UV) python -m black --check .
	$(UV) python manage.py check

format: ## Format code with black
	$(UV) python -m black .

test: ## Run tests
	$(UV) python -m pytest --cov=. --cov-report=term-missing

frontend-format: ## Check frontend formatting
	$(UV) python scripts/run_frontend_gate.py format

frontend-lint: ## Run frontend lint
	$(UV) python scripts/run_frontend_gate.py lint

frontend-test: ## Run frontend tests
	$(UV) python scripts/run_frontend_gate.py test

frontend-typecheck: ## Run frontend typecheck
	$(UV) python scripts/run_frontend_gate.py typecheck

benchmark-model: ## Benchmark local Ollama models against Moksha contracts
	$(PYTHON) scripts/benchmark_ollama.py

migrate: ## Run Django migrations
	$(UV) python manage.py migrate

django: ## Start Django development server
	$(UV) python manage.py runserver

discover: ## Run scripture auto-discovery
	$(UV) python manage.py discover_scriptures

migrate-chats: ## Migrate existing JSON chats to database
	$(UV) python manage.py migrate_json_chats
