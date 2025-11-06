# WebOps Development Makefile
# This Makefile is for DEVELOPMENT tasks only
# For production deployment, use: provisioning/versions/v1.0.0/bin/webops

.PHONY: help install dev test lint clean format check-security docs validate

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Paths
CONTROL_PANEL_DIR := control-panel
VENV := $(CONTROL_PANEL_DIR)/venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
MANAGE := $(PYTHON) $(CONTROL_PANEL_DIR)/manage.py

#=============================================================================
# Help
#=============================================================================

help: ## Show this help message
	@echo "$(BLUE)WebOps Development Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Usage:$(NC) make [target]"
	@echo ""
	@echo "$(YELLOW)Development:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Production:$(NC)"
	@echo "  For production operations, use: $(BLUE)provisioning/versions/v1.0.0/bin/webops$(NC)"
	@echo ""

#=============================================================================
# Installation & Setup
#=============================================================================

install: ## Install development environment (full setup)
	@echo "$(BLUE)Installing WebOps development environment...$(NC)"
	cd $(CONTROL_PANEL_DIR) && ./quickstart.sh
	@echo "$(GREEN)✓ Development environment ready!$(NC)"

install-deps: $(VENV) ## Install Python dependencies only
	@echo "$(BLUE)Installing Python dependencies...$(NC)"
	$(PIP) install -r $(CONTROL_PANEL_DIR)/requirements.txt
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

$(VENV): ## Create virtual environment
	@echo "$(BLUE)Creating virtual environment...$(NC)"
	cd $(CONTROL_PANEL_DIR) && python3 -m venv venv
	$(PIP) install --upgrade pip
	@echo "$(GREEN)✓ Virtual environment created$(NC)"

#=============================================================================
# Development Server
#=============================================================================

dev: ## Start development server (Django + Celery + Beat)
	@echo "$(BLUE)Starting development server...$(NC)"
	cd $(CONTROL_PANEL_DIR) && ./start_dev.sh

dev-web: ## Start Django development server only
	@echo "$(BLUE)Starting Django development server...$(NC)"
	$(MANAGE) runserver

dev-worker: ## Start Celery worker only
	@echo "$(BLUE)Starting Celery worker...$(NC)"
	cd $(CONTROL_PANEL_DIR) && $(VENV)/bin/celery -A config.celery_app worker --loglevel=info

dev-beat: ## Start Celery beat scheduler only
	@echo "$(BLUE)Starting Celery beat...$(NC)"
	cd $(CONTROL_PANEL_DIR) && $(VENV)/bin/celery -A config.celery_app beat --loglevel=info

#=============================================================================
# Database
#=============================================================================

migrate: ## Run database migrations
	@echo "$(BLUE)Running migrations...$(NC)"
	$(MANAGE) migrate
	@echo "$(GREEN)✓ Migrations complete$(NC)"

makemigrations: ## Create new database migrations
	@echo "$(BLUE)Creating migrations...$(NC)"
	$(MANAGE) makemigrations
	@echo "$(GREEN)✓ Migrations created$(NC)"

db-reset: ## Reset database (WARNING: deletes all data)
	@echo "$(RED)⚠️  WARNING: This will delete all data!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -f $(CONTROL_PANEL_DIR)/db.sqlite3; \
		$(MANAGE) migrate; \
		echo "$(GREEN)✓ Database reset complete$(NC)"; \
	else \
		echo "$(YELLOW)Cancelled$(NC)"; \
	fi

db-shell: ## Open database shell
	$(MANAGE) dbshell

superuser: ## Create Django superuser
	$(MANAGE) createsuperuser

#=============================================================================
# Testing
#=============================================================================

test: ## Run all tests
	@echo "$(BLUE)Running tests...$(NC)"
	$(MANAGE) test --keepdb

test-verbose: ## Run tests with verbose output
	@echo "$(BLUE)Running tests (verbose)...$(NC)"
	$(MANAGE) test --keepdb -v 2

test-fast: ## Run tests in parallel
	@echo "$(BLUE)Running tests in parallel...$(NC)"
	$(MANAGE) test --parallel --keepdb

test-app: ## Run tests for specific app (usage: make test-app APP=deployments)
	@if [ -z "$(APP)" ]; then \
		echo "$(RED)Error: APP not specified$(NC)"; \
		echo "Usage: make test-app APP=deployments"; \
		exit 1; \
	fi
	@echo "$(BLUE)Running tests for $(APP)...$(NC)"
	$(MANAGE) test apps.$(APP) --keepdb

test-coverage: ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	$(VENV)/bin/coverage run --source='.' $(CONTROL_PANEL_DIR)/manage.py test --keepdb
	$(VENV)/bin/coverage report
	$(VENV)/bin/coverage html
	@echo "$(GREEN)✓ Coverage report generated: htmlcov/index.html$(NC)"

#=============================================================================
# Code Quality
#=============================================================================

lint: ## Run all linters (bash + python)
	@echo "$(BLUE)Running linters...$(NC)"
	@$(MAKE) lint-bash
	@$(MAKE) lint-python
	@echo "$(GREEN)✓ All linters passed$(NC)"

lint-bash: ## Lint bash scripts
	@echo "$(BLUE)Linting bash scripts...$(NC)"
	@for script in provisioning/versions/v1.0.0/setup/*.sh \
		provisioning/versions/v1.0.0/lifecycle/*.sh \
		provisioning/versions/v1.0.0/bin/webops; do \
		bash -n $$script && echo "$(GREEN)✓$(NC) $$script" || exit 1; \
	done

lint-python: $(VENV) ## Lint Python code
	@echo "$(BLUE)Linting Python code...$(NC)"
	-$(VENV)/bin/flake8 $(CONTROL_PANEL_DIR) --max-line-length=100 --exclude=migrations,venv
	@echo "$(GREEN)✓ Python linting complete$(NC)"

format: ## Format Python code with black
	@echo "$(BLUE)Formatting Python code...$(NC)"
	$(VENV)/bin/black $(CONTROL_PANEL_DIR) --exclude=migrations
	@echo "$(GREEN)✓ Code formatted$(NC)"

type-check: ## Run type checking with pyright
	@echo "$(BLUE)Running type checks...$(NC)"
	@if command -v pyright >/dev/null 2>&1; then \
		pyright $(CONTROL_PANEL_DIR); \
	else \
		echo "$(YELLOW)⚠️  pyright not installed$(NC)"; \
		echo "Install with: npm install -g pyright"; \
	fi

check-security: ## Run security checks
	@echo "$(BLUE)Running security checks...$(NC)"
	$(MANAGE) check --deploy
	@echo "$(GREEN)✓ Security checks passed$(NC)"

#=============================================================================
# Static Files
#=============================================================================

collectstatic: ## Collect static files
	@echo "$(BLUE)Collecting static files...$(NC)"
	$(MANAGE) collectstatic --noinput
	@echo "$(GREEN)✓ Static files collected$(NC)"

#=============================================================================
# Documentation
#=============================================================================

docs: ## Generate documentation
	@echo "$(BLUE)Generating documentation...$(NC)"
	@echo "$(YELLOW)Documentation tasks:$(NC)"
	@echo "  - API docs: $(CONTROL_PANEL_DIR)/docs/"
	@echo "  - Platform docs: provisioning/versions/v1.0.0/README.md"
	@echo "$(GREEN)✓ Documentation available$(NC)"

#=============================================================================
# Validation & CI
#=============================================================================

validate: ## Run pre-installation validation
	@echo "$(BLUE)Running system validation...$(NC)"
	sudo provisioning/versions/v1.0.0/setup/validate.sh

ci: lint test check-security ## Run all CI checks (lint, test, security)
	@echo "$(GREEN)✓ All CI checks passed$(NC)"

pre-commit: lint-bash test-fast ## Run pre-commit checks (fast)
	@echo "$(GREEN)✓ Pre-commit checks passed$(NC)"

#=============================================================================
# Cleanup
#=============================================================================

clean: ## Clean build artifacts and caches
	@echo "$(BLUE)Cleaning build artifacts...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(CONTROL_PANEL_DIR)/htmlcov
	rm -rf $(CONTROL_PANEL_DIR)/.coverage
	@echo "$(GREEN)✓ Cleaned$(NC)"

clean-all: clean ## Clean everything including venv
	@echo "$(BLUE)Cleaning everything...$(NC)"
	rm -rf $(VENV)
	rm -rf $(CONTROL_PANEL_DIR)/staticfiles
	rm -f $(CONTROL_PANEL_DIR)/db.sqlite3
	@echo "$(GREEN)✓ Deep clean complete$(NC)"

#=============================================================================
# Deployment (Production)
#=============================================================================

deploy-install: ## Install WebOps platform (production)
	@echo "$(BLUE)Installing WebOps platform...$(NC)"
	@echo "$(YELLOW)⚠️  This will run the production installer$(NC)"
	sudo provisioning/versions/v1.0.0/lifecycle/install.sh

deploy-validate: ## Validate production deployment
	@echo "$(BLUE)Validating deployment...$(NC)"
	sudo provisioning/versions/v1.0.0/bin/webops validate

deploy-status: ## Show platform status
	@echo "$(BLUE)Platform status:$(NC)"
	provisioning/versions/v1.0.0/bin/webops state

#=============================================================================
# Utilities
#=============================================================================

shell: ## Open Django shell
	$(MANAGE) shell

check: ## Run Django system checks
	$(MANAGE) check

show-urls: ## Show all Django URLs
	$(MANAGE) show_urls || $(MANAGE) shell -c "from django.urls import get_resolver; print('\n'.join(str(p.pattern) for p in get_resolver().url_patterns))"

logs: ## Show recent logs
	@echo "$(BLUE)Recent logs:$(NC)"
	sudo journalctl -u 'webops-*' --since "10 minutes ago" --no-pager | tail -50

ps: ## Show running WebOps processes
	@echo "$(BLUE)WebOps processes:$(NC)"
	ps aux | grep -E 'webops|celery|manage.py' | grep -v grep

#=============================================================================
# Info
#=============================================================================

version: ## Show version information
	@echo "$(BLUE)WebOps Version Information$(NC)"
	@echo "Platform: $$(cat provisioning/versions/v1.0.0/bin/webops | grep 'WEBOPS_VERSION=' | head -1 | cut -d'=' -f2 | tr -d '"')"
	@echo "Python: $$($(PYTHON) --version)"
	@echo "Django: $$($(MANAGE) --version)"

info: ## Show environment information
	@echo "$(BLUE)WebOps Development Environment$(NC)"
	@echo ""
	@echo "$(YELLOW)Paths:$(NC)"
	@echo "  Control Panel: $(CONTROL_PANEL_DIR)"
	@echo "  Virtual Env:   $(VENV)"
	@echo "  Python:        $(PYTHON)"
	@echo ""
	@echo "$(YELLOW)Status:$(NC)"
	@if [ -d "$(VENV)" ]; then \
		echo "  Virtual Env:   $(GREEN)✓ Created$(NC)"; \
	else \
		echo "  Virtual Env:   $(RED)✗ Not found$(NC)"; \
	fi
	@if [ -f "$(CONTROL_PANEL_DIR)/db.sqlite3" ]; then \
		echo "  Database:      $(GREEN)✓ Exists$(NC)"; \
	else \
		echo "  Database:      $(YELLOW)⚠ Not found (run 'make migrate')$(NC)"; \
	fi
	@echo ""
	@echo "Run '$(GREEN)make help$(NC)' for available commands"

#=============================================================================
# Quick Actions
#=============================================================================

.PHONY: quick-start quick-test quick-lint

quick-start: install dev ## Quick start: install and run dev server
	@echo "$(GREEN)✓ WebOps is running!$(NC)"

quick-test: ## Quick test: run fast tests
	@$(MAKE) test-fast

quick-lint: ## Quick lint: check bash scripts only
	@$(MAKE) lint-bash
