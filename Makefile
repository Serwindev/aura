# Unix/CI task runner. On Windows use:  .\make.ps1 <target>
.PHONY: setup test lint secrets-scan server app eval db-reset

setup:
	cd server && uv sync

test:
	cd server && uv run pytest

lint:
	cd server && uv run ruff check .

secrets-scan:
	python scripts/secret_scan.py

server:
	@echo "not built yet (phase 3: FastAPI server)"; exit 1

app:
	@echo "not built yet (phase 4: Flutter app)"; exit 1

eval:
	@echo "not built yet (phase 2: eval harness)"; exit 1

db-reset:
	@echo "not built yet (phase 3: SQLite dev DB)"; exit 1
