.PHONY: lint format typecheck test check-all run install clean

# Linting and formatting
lint:
	uv run ruff check src/

format:
	uv run black src/

format-check:
	uv run black --check src/

typecheck:
	uv run mypy src/

test:
	uv run pytest tests/ -v

check-all: lint format-check typecheck test
	@echo "✅ All checks passed!"

# Development
install:
	uv sync --dev

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
	@echo "  make test        - Run tests with pytest"
	@echo "  make check-all   - Run all checks (lint, format, typecheck, test)"
	@echo "  make run         - Run the application"
	@echo "  make clean       - Clean up cache files"
	@echo "  make help        - Show this help"
