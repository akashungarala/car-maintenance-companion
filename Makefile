# Car Maintenance Companion — developer entrypoints.
# `make check` runs exactly what CI runs. If it passes here, CI passes.

.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: setup
setup: ## Install all toolchains and dependencies
	uv sync --all-packages
	pnpm install --frozen-lockfile
	uv run pre-commit install

.PHONY: check
check: lint typecheck test ## Run every gate CI runs

.PHONY: lint
lint: ## Lint Python and JS/TS
	uv run ruff check .
	uv run ruff format --check .
	pnpm run format:check
	pnpm run lint

.PHONY: fmt
fmt: ## Auto-format everything
	uv run ruff format .
	uv run ruff check --fix .
	pnpm exec prettier --write .

.PHONY: typecheck
typecheck: ## Static type checks
	uv run mypy apps/api/src
	pnpm run typecheck

.PHONY: test
test: ## Run all test suites with coverage
	uv run pytest --cov --cov-report=term-missing --cov-report=xml
	pnpm run test

.PHONY: clean
clean: ## Remove build and cache artifacts
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \
		-o -name .mypy_cache -o -name .next \) -prune -exec rm -rf {} +
	rm -rf coverage.xml .coverage htmlcov
