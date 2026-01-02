.PHONY: help install dev-install start stop restart logs seed reset test clean build

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	pip install -e .

dev-install: ## Install with development dependencies
	pip install -e ".[dev]"

start: ## Start all services with Docker Compose
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 5
	@docker-compose ps
	@echo "\n✓ Services started!"
	@echo "API: http://localhost:8000"
	@echo "Docs: http://localhost:8000/docs"

stop: ## Stop all services
	docker-compose down

restart: stop start ## Restart all services

logs: ## View application logs
	docker-compose logs -f app

logs-all: ## View all service logs
	docker-compose logs -f

seed: ## Seed initial data (menu, inventory, drivers)
	docker-compose exec app python scripts/seed_data.py

reset: ## Reset all state in Redis
	docker-compose exec app python scripts/reset_state.py

test: ## Run tests
	pytest tests/ -v

test-cov: ## Run tests with coverage
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

clean: ## Clean up Python cache files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage

build: ## Build Docker image
	docker-compose build

status: ## Check service health
	@curl -s http://localhost:8000/health | jq .
	@echo ""
	@curl -s http://localhost:8000/api/v1/admin/agents/status | jq .

shell-app: ## Open shell in app container
	docker-compose exec app /bin/bash

shell-redis: ## Open Redis CLI
	docker-compose exec redis redis-cli

shell-postgres: ## Open PostgreSQL CLI
	docker-compose exec postgres psql -U restaurant_user -d restaurant_db

fmt: ## Format code with black
	black src/ tests/ scripts/

lint: ## Lint code with ruff
	ruff check src/ tests/ scripts/

type-check: ## Type check with mypy
	mypy src/

dev: ## Start services and run app locally
	docker-compose up -d redis postgres
	@echo "Infrastructure started. Run app with:"
	@echo "uvicorn src.main:app --reload"

demo: start seed ## Quick demo: start + seed data
	@echo "\n✓ System ready for demo!"
	@echo "\nTry this:"
	@echo 'curl -X POST http://localhost:8000/api/v1/conversations'
