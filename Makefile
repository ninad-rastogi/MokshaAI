.PHONY: help install lint format test run django streamlit migrate benchmark-model

export UV_PROJECT_ENVIRONMENT := D:/Ninad/Python/.env
PYTHON = D:/Ninad/Python/.env/Scripts/python.exe
STREAMLIT = D:/Ninad/Python/.env/Scripts/streamlit.exe

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync --locked --extra dev --python 3.14.6

lint: ## Run linters
	$(PYTHON) -m black --check .
	$(PYTHON) -m flake8 .

format: ## Format code with black
	$(PYTHON) -m black .

test: ## Run tests
	$(PYTHON) -m pytest --cov=. --cov-report=term-missing

benchmark-model: ## Benchmark local Ollama models against Moksha contracts
	$(PYTHON) scripts/benchmark_ollama.py

migrate: ## Run Django migrations
	$(PYTHON) manage.py migrate

django: ## Start Django development server
	$(PYTHON) manage.py runserver

streamlit: ## Start Streamlit frontend
	$(STREAMLIT) run streamlit_ui/main_app.py

discover: ## Run scripture auto-discovery
	$(PYTHON) manage.py discover_scriptures

migrate-chats: ## Migrate existing JSON chats to database
	$(PYTHON) manage.py migrate_json_chats
