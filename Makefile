.PHONY: dev down logs db-migrate psql lint fmt test test-integration smoke backup openapi

dev:            ## bring the whole stack up (postgres, migrate, api, worker)
	docker compose up --build -d
	docker compose ps

down:
	docker compose down

logs:
	docker compose logs -f api worker

db-migrate:
	docker compose run --rm migrate

psql:
	docker compose exec postgres psql -U octo -d octo

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

test:
	uv run pytest tests/unit -q

test-integration:
	uv run pytest tests/integration -q

smoke:          ## end-to-end sanity against a running stack
	curl -sf http://localhost:8000/healthz | python3 -m json.tool

openapi:        ## regenerate the committed OpenAPI spec (docs/api/openapi.json)
	mkdir -p docs/api
	uv run python -c "import json; from octo.api.main import app; \
	print(json.dumps(app.openapi(), indent=2))" > docs/api/openapi.json
	@echo "wrote docs/api/openapi.json — interactive docs: http://localhost:8000/docs"

backup:         ## dump the spine DB (stateful volumes: pgdata + openwebui-data)
	mkdir -p backups
	docker compose exec -T postgres pg_dump -U octo octo > backups/octo-$$(date +%Y%m%d-%H%M).sql
	@ls -lh backups/ | tail -3
