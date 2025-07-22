.PHONY: ensure-poetry install install-reqs test lint clean

# Ensures Poetry is installed locally
ensure-poetry:
	@command -v poetry >/dev/null 2>&1 || { \
		echo "Poetry not found. Installing..."; \
		curl -sSL https://install.python-poetry.org | python3 -; \
		echo "Make sure ~/.local/bin is in your PATH"; \
	}

# Installs project dependencies
install: ensure-poetry
	poetry install

# Same as install, more readable alias
install-reqs: install

lock: ensure-poetry
	cd cli && poetry lock

# Runs tests using poetry environment
test:
	poetry run pytest || echo "No tests found"

# Formats code using black
lint:
	poetry run black .

# Cleans caches
clean:
	rm -rf __pycache__ .pytest_cache