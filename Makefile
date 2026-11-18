# Lesson Coach. Run `make install` once after cloning, then any target below.
.PHONY: install dev test lint fmt build e2e

BACKEND := cd backend &&
FRONTEND := cd frontend &&

install:
	$(BACKEND) uv sync
	$(FRONTEND) pnpm install --frozen-lockfile
	$(FRONTEND) pnpm exec playwright install chromium

# Backend on :8000 with reload, Vite on :5173 proxying /api to it. Ctrl-C stops both.
dev:
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) & \
	(cd frontend && pnpm dev) & \
	wait

test:
	$(BACKEND) uv run pytest -q
	$(FRONTEND) pnpm test

lint:
	$(BACKEND) uv run ruff check . && uv run ruff format --check . && uv run mypy
	$(FRONTEND) pnpm lint

fmt:
	$(BACKEND) uv run ruff check --fix . && uv run ruff format .
	$(FRONTEND) pnpm fmt

build:
	$(FRONTEND) pnpm build

# Playwright + axe-core against FastAPI serving the built frontend.
e2e:
	$(FRONTEND) pnpm e2e
