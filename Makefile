.PHONY: lint format typecheck test test-integration check-all run install install-hooks clean

# Linting and formatting
lint:
	uv run ruff check src/ --fix

format:
	uv run black src/

typecheck:
	uv run mypy src/

test:
	uv run pytest tests/ -v -m "not integration"

test-integration:
	uv run pytest tests/integration/ -v -m integration

check-all: lint format typecheck test
	@echo "✅ All checks passed!"

# Development
install: install-hooks
	uv sync --dev

install-hooks:
	git config core.hooksPath .githooks

run:
	uv run doubleday

# Cleanup
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +

# Help
help:
	@echo "Available commands:"
	@echo "  make install     - Install dependencies"
	@echo "  make lint        - Run ruff linter"
	@echo "  make format      - Format code with black"
	@echo "  make format-check- Check if code is formatted"
	@echo "  make typecheck   - Run mypy type checker"
	@echo "  make test             - Run unit tests (excludes integration)"
	@echo "  make test-integration - Run integration tests (requires AWS)"
	@echo "  make check-all        - Run all checks (lint, format, typecheck, unit tests)"
	@echo "  make run         - Run the application"
	@echo "  make clean       - Clean up cache files"
	@echo "  make help        - Show this help"
