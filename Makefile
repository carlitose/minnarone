.PHONY: quality test

quality:
	uv run --extra dev ruff check src tests
	uv run --extra dev vulture
	uv run --extra dev deptry . --no-ansi
	uv run --extra dev pylint src tests

test:
	uv run --extra dev pytest
