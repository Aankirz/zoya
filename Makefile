.PHONY: start setup check

setup: ## Install and ask for missing keys, without starting
	./start.sh --setup-only

start: ## Set up (asks for missing keys) and run Zoya
	./start.sh

check: ## Lint and tests
	uv run ruff check . && uv run black --check . && uv run isort --check . && uv run pytest -q
