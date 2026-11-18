# Lesson Coach

Lesson Coach helps math teachers of grades 6–9 refresh the math they teach and prepare their lessons. sympy computes and checks every answer; a language model only explains, diagnoses and phrases, and is always given the verified result. Built for Akelius as a take-home assignment; the design is in `docs/PLAN.md`.

## Run it

Needs Python tooling `uv`, Node 22+ with `pnpm`, and Docker for the container.

```sh
make install          # backend and frontend dependencies, Playwright's Chromium
make dev              # API on :8000, app on http://localhost:5173
docker compose up     # the full app on http://localhost:8000
```

`make test`, `make lint`, `make fmt`, `make build` and `make e2e` cover the rest. `make e2e` serves the app on port 8010 (and the dev server on the next port); set `E2E_PORT` (and optionally `E2E_DEV_PORT`) to run it in parallel checkouts. Copy `.env.example` to `.env` for the model settings.

## Accessibility

The target is WCAG 2.2 AA. [`docs/A11Y.md`](docs/A11Y.md) lists what the e2e tests check (axe in every page state at four layouts, keyboard-only flows, reduced motion, print, the accessibility tree) and what hasn't been tested yet: no one has run a real screen reader on it.
