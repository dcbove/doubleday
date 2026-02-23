.PHONY: lint format typecheck test test-integration check-all run install install-hooks clean \
	frontend-install frontend-build frontend-dev frontend-ios frontend-deploy frontend-clean

# Linting and formatting
lint:
	uv run ruff check src/ tests/ --fix

format:
	uv run black src/ tests/

typecheck:
	uv run mypy src/ tests/

test:
	uv run pytest tests/unit/ -v -m "not integration"

test-integration:
	uv run pytest tests/integration/ -v -m integration

check-all: lint format typecheck test
	@echo "✅ All checks passed!"

# Development
install: install-hooks frontend-install
	uv sync --dev

install-hooks:
	git config core.hooksPath .githooks

run:
	uv run doubleday

# Frontend
frontend-install:
	cd frontend && npm install

frontend-build: frontend-install
	cd frontend && npm run build

frontend-dev:
	cd frontend && npm run dev

frontend-ios:
	cd frontend && npx expo run:ios

frontend-deploy: frontend-install
	$(eval ENV ?= dev)
	$(eval TF_DIR := terraform/environments/$(ENV))
	$(eval POOL_ID := $(shell cd $(TF_DIR) && terraform output -raw cognito_user_pool_id))
	$(eval CLIENT_ID := $(shell cd $(TF_DIR) && terraform output -raw cognito_client_id))
	$(eval BUCKET := $(shell cd $(TF_DIR) && terraform output -raw frontend_bucket_name))
	$(eval DIST_ID := $(shell cd $(TF_DIR) && terraform output -raw cloudfront_distribution_id))
	$(eval DOMAIN := $(shell grep frontend_domain_name $(TF_DIR)/terraform.tfvars | sed 's/.*"\(.*\)"/\1/'))
	$(eval COGNITO_DOMAIN := $(shell echo doubleday-$(ENV)))
	cd frontend && \
		EXPO_PUBLIC_COGNITO_USER_POOL_ID=$(POOL_ID) \
		EXPO_PUBLIC_COGNITO_CLIENT_ID=$(CLIENT_ID) \
		EXPO_PUBLIC_COGNITO_DOMAIN=$(COGNITO_DOMAIN) \
		EXPO_PUBLIC_COGNITO_REGION=us-east-1 \
		EXPO_PUBLIC_REDIRECT_SIGN_IN=https://$(DOMAIN)/callback \
		EXPO_PUBLIC_REDIRECT_SIGN_OUT=https://$(DOMAIN) \
		npm run build
	aws s3 sync frontend/dist "s3://$(BUCKET)" --delete --exclude "static/catalogs/*"
	aws cloudfront create-invalidation --distribution-id "$(DIST_ID)" --paths "/*"

frontend-clean:
	rm -rf frontend/node_modules frontend/dist

# Cleanup
clean: frontend-clean
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +

# Help
help:
	@echo "Available commands:"
	@echo "  make install            - Install all dependencies (Python + frontend)"
	@echo "  make lint               - Run ruff linter"
	@echo "  make format             - Format code with black"
	@echo "  make typecheck          - Run mypy type checker"
	@echo "  make test               - Run unit tests (excludes integration)"
	@echo "  make test-integration   - Run integration tests (requires AWS)"
	@echo "  make check-all          - Run all checks (lint, format, typecheck, unit tests)"
	@echo "  make run                - Run the application"
	@echo "  make frontend-install   - Install frontend dependencies"
	@echo "  make frontend-build     - Build frontend for production"
	@echo "  make frontend-deploy    - Build and deploy frontend (ENV=dev|prod)"
	@echo "  make frontend-dev       - Start frontend web dev server"
	@echo "  make frontend-ios       - Build and run on iOS simulator"
	@echo "  make clean              - Clean up all cache files and build artifacts"
	@echo "  make help               - Show this help"
