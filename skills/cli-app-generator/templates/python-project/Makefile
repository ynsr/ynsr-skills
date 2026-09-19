CMD ?= .venv/bin/mycli

.PHONY: check
check:
	uv sync -q
	uv run ruff check .
	uv run pytest -q
	./scripts/verify-cli $(CMD) "list widgets" "profile remove demo"
