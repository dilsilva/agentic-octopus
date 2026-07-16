.PHONY: dev down logs db-migrate psql lint fmt test test-integration smoke

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
