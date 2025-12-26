# FunctionGemma Agent Makefile
# Provides convenient commands for development, testing, and deployment

.PHONY: help install dev test lint format clean build docker-build docker-run helm-lint k8s-deploy k8s-rollback docs notebooks

# Default target
help: ## Show this help message
	@echo "FunctionGemma Agent - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development
install: ## Install dependencies
	pip install -e ".[dev]"

dev: ## Run development server
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Testing
test: ## Run all tests
	pytest --cov=app --cov-report=html --cov-report=term

test-fast: ## Run tests without coverage
	pytest -x

test-watch: ## Run tests in watch mode
	ptw --runner "python -m pytest --cov=app"

# Code Quality
lint: ## Run linting and type checking
	ruff check .
	mypy app/
	black --check .

format: ## Format code
	ruff check . --fix
	black .

# Security
security-scan: ## Run security scan
	trivy fs --format table --exit-code 0 .
	trivy config --exit-code 0 .

# Docker
docker-build: ## Build Docker image
	docker build -f deployment/Dockerfile -t function-gemma-agent:latest .

docker-run: ## Run Docker container
	docker run -p 8000:8000 -v $(PWD)/data:/app/data function-gemma-agent:latest

docker-push: ## Push Docker image to registry
	docker build -f deployment/Dockerfile -t ghcr.io/your-org/function-gemma-agent:$(shell git rev-parse --short HEAD) .
	docker push ghcr.io/your-org/function-gemma-agent:$(shell git rev-parse --short HEAD)

# Kubernetes / Helm
helm-lint: ## Lint Helm chart
	helm lint k8s/chart/

helm-template: ## Render Helm templates
	helm template test-release k8s/chart/

helm-install: ## Install Helm chart to production
	helm upgrade --install function-gemma-agent k8s/chart/ --namespace production --create-namespace

helm-upgrade: ## Upgrade Helm chart
	helm upgrade function-gemma-agent k8s/chart/ --namespace production

k8s-deploy: ## Deploy to Kubernetes (production)
	$(MAKE) docker-push
	$(MAKE) helm-upgrade

k8s-rollback: ## Rollback Kubernetes deployment
	./scripts/rollback.sh

k8s-logs: ## Show Kubernetes logs
	kubectl logs -n production -l app.kubernetes.io/name=function-gemma-agent -f

k8s-status: ## Show Kubernetes status
	kubectl get all -n production -l app.kubernetes.io/name=function-gemma-agent

# Documentation
docs: ## Serve documentation locally
	cd docs && python -m http.server 8080

docs-build: ## Build documentation
	@echo "Documentation is in markdown format, no build required"

# Jupyter Notebooks
notebooks: ## Start Jupyter notebook server
	jupyter notebook notebooks/

notebook-check: ## Check notebooks for errors
	jupyter nbconvert --to notebook --execute notebooks/*.ipynb --inplace

# Data and Models
download-model: ## Download FunctionGemma model
	python scripts/download_model.py

setup-data: ## Set up data directories
	mkdir -p data/chroma data/models data/logs

train-model: ## Train/fine-tune model
	python scripts/fine_tune_gemma.py

# Monitoring
logs: ## Show application logs
	tail -f logs/agent.log

metrics: ## Show Prometheus metrics
	curl http://localhost:8000/api/v1/metrics

health: ## Check health endpoint
	curl http://localhost:8000/api/v1/health

# Database / Storage
init-db: ## Initialize database
	python scripts/init_database.py

backup-db: ## Backup database
	python scripts/backup_database.py

migrate-db: ## Run database migrations
	python scripts/migrate_database.py

# CI/CD
ci-test: ## Run CI tests locally
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) security-scan

ci-build: ## Run CI build locally
	$(MAKE) docker-build
	$(MAKE) helm-lint

# Environment
env-dev: ## Set up development environment
	cp .env.example .env
	$(MAKE) install
	$(MAKE) setup-data

env-prod: ## Set up production environment variables
	@echo "Remember to set:"
	@echo "- ENV=production"
	@echo "- LOG_LEVEL=INFO"
	@echo "- API_KEY_SECRET"
	@echo "- MLFLOW_TRACKING_URI"
	@echo "- DATABASE_URL"

# Cleanup
clean: ## Clean up generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/

clean-docker: ## Clean up Docker resources
	docker system prune -f
	docker volume prune -f

clean-all: clean clean-docker ## Clean everything

# Release
version: ## Show current version
	@python -c "import app; print(app.__version__)"

tag: ## Create git tag for release
	git tag -a v$(shell python -c "import app; print(app.__version__)") -m "Release v$(shell python -c "import app; print(app.__version__)")"
	git push origin v$(shell python -c "import app; print(app.__version__)")

# Quick start commands
quickstart: ## Quick start for development
	@echo "Setting up FunctionGemma Agent for development..."
	$(MAKE) env-dev
	@echo ""
	@echo "Next steps:"
	@echo "1. Edit .env with your configuration"
	@echo "2. Run 'make dev' to start the server"
	@echo "3. Visit http://localhost:8000/docs for API documentation"

quickstart-prod: ## Quick start for production
	@echo "Deploying FunctionGemma Agent to production..."
	$(MAKE) k8s-deploy
	@echo ""
	@echo "Deployment complete!"
	@echo "Check status with: make k8s-status"

# Development utilities
shell: ## Open Python shell with app context
	python -i -c "from app.main import app; from app.domain.agent import agent_service"

db-shell: ## Open database shell
	python scripts/db_shell.py

worker: ## Run background worker
	python scripts/worker.py

scheduler: ## Run task scheduler
	python scripts/scheduler.py

# Performance
load-test: ## Run load tests
	python scripts/load_test.py

benchmark: ## Run performance benchmarks
	python scripts/benchmark.py

profile: ## Profile the application
	python -m cProfile -o profile.stats scripts/profile_app.py

# Utilities
tree: ## Show project tree
	tree -I '__pycache__|*.pyc|.git|node_modules|venv|.venv' -L 3

deps: ## Show dependency tree
	pipdeptree

outdated: ## Show outdated packages
	pip list --outdated

freeze: ## Freeze requirements
	pip freeze > requirements.txt

# Git hooks
install-hooks: ## Install pre-commit hooks
	pre-commit install

check-pre-commit: ## Run pre-commit checks
	pre-commit run --all-files

# Migration helpers
create-migration: ## Create new database migration
	@read -p "Enter migration name: " name; \
	python scripts/create_migration.py $$name

# Backup and restore
backup: ## Backup all data
	./scripts/backup.sh

restore: ## Restore from backup
	@read -p "Enter backup file path: " backup; \
	./scripts/restore.sh $$backup

# Local development with Docker Compose
compose-up: ## Start all services with Docker Compose
	docker-compose up -d

compose-down: ## Stop all services
	docker-compose down

compose-logs: ## Show Docker Compose logs
	docker-compose logs -f

# Monitoring and observability
prometheus-up: ## Start Prometheus locally
	docker run -d -p 9090:9090 --name prometheus prom/prometheus

grafana-up: ## Start Grafana locally
	docker run -d -p 3000:3000 --name grafana grafana/grafana

jaeger-up: ## Start Jaeger locally
	docker run -d -p 16686:16686 -p 14268:14268 --name jaeger jaegertracing/all-in-one:latest

monitoring-stack: ## Start full monitoring stack
	$(MAKE) prometheus-up
	$(MAKE) grafana-up
	$(MAKE) jaeger-up
	@echo ""
	@echo "Monitoring stack started:"
	@echo "- Prometheus: http://localhost:9090"
	@echo "- Grafana: http://localhost:3000 (admin/admin)"
	@echo "- Jaeger: http://localhost:16686"
