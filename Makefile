# Lesson Coach. Run `make install` once after cloning, then any target below.
.PHONY: install dev test lint fmt build e2e evals zip
SHELL := /bin/bash

BACKEND := cd backend &&
FRONTEND := cd frontend &&

install:
	$(BACKEND) uv sync
	$(FRONTEND) pnpm install --frozen-lockfile
	$(FRONTEND) pnpm exec playwright install chromium

# Backend on :8000 with reload, Vite on :5173 proxying /api to it.
# Ctrl-C stops both, and so does either server exiting (e.g. its port is taken).
# Each server runs in its own process group so the trap can stop all of its children.
dev:
	@set -m; \
	(cd backend && exec uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) & api=$$!; \
	(cd frontend && exec pnpm dev) & web=$$!; \
	trap 'kill -- -$$api -$$web 2>/dev/null' INT TERM EXIT; \
	wait -n

test:
	$(BACKEND) uv run pytest -q
	$(FRONTEND) pnpm test

lint:
	$(BACKEND) uv run ruff check . ../pipeline ../evals && uv run ruff format --check . ../pipeline ../evals && uv run mypy
	$(FRONTEND) pnpm lint

fmt:
	$(BACKEND) uv run ruff check --fix . ../pipeline ../evals && uv run ruff format . ../pipeline ../evals
	$(FRONTEND) pnpm fmt

build:
	$(FRONTEND) pnpm build

# Builds the frontend, then Playwright + axe-core against FastAPI serving it.
e2e:
	$(FRONTEND) pnpm e2e

# Live evals against Azure (needs .env, about $2.90): see evals/README.md.
evals:
	uv run --project backend python evals/run.py run
	uv run --project backend python evals/run.py judge
	uv run --project backend python evals/run.py summarize

# The delivery zip with .git: a fresh clone of the committed branch, written to ../lesson-coach.zip.
zip:
	scripts/zip.sh
