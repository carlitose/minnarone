.PHONY: quality test

quality:
	uv run --extra dev ruff format --check src tests
	uv run --extra dev ruff check src tests
	uv run --extra dev vulture
	uv run --extra dev deptry . --no-ansi
	# duplicate-code (R0801) solo su `src`: sui test la ripetizione di setup è
	# fisiologica (vedi .pre-commit-config.yaml).
	uv run --extra dev pylint src

test:
	uv run --extra dev pytest
