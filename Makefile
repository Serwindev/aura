# Unix/CI task runner. On Windows use:  .\make.ps1 <target>
.PHONY: setup test lint secrets-scan server app eval models db-reset

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
	uv run --project server python eval/harness.py --notes eval/data/notes.yaml --out eval/results/latest/dev
	uv run --project server python eval/harness.py --notes eval/data/notes_holdout.yaml --out eval/results/latest/holdout

models:
	mkdir -p server/models && cd server/models && curl -sSLO https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip && unzip -q vosk-model-small-hi-0.22.zip && rm vosk-model-small-hi-0.22.zip

db-reset:
	@echo "not built yet (phase 3: SQLite dev DB)"; exit 1
