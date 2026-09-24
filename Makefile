.PHONY: install run lint test build

install:
	uv sync --frozen

run:
	uv run database

lint:
	uv run ruff check .

test:
	uv run python tests/run_tests.py

build:
	uv build
