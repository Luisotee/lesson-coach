# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A take-home assignment for Akelius: **Lesson Coach**, a web app that helps math teachers (grades 6–9) refresh the math they teach and prepare lessons. The brief is `2026-11-17_assignment_Education_AI engineer math teacher coach.pdf`. Read these before changing anything:
- `docs/PLAN.md`: the design, and the source of truth for all decisions.
- `docs/TASKS.md`: the work items, their waves and their acceptance criteria. Update a task's status when you start and when you finish.
- `docs/REASONING.md`: the short record of decisions and of how the human and AI worked. Add to it when you make a decision a reviewer would ask about.
- `design/*.dc.html`: the visual reference, a Claude Design canvas exported as HTML with inline styles (canvas: https://claude.ai/artifact/2JH48uYkKFRLC1mrJG2NUC). Rebuild it with Tailwind and shadcn/ui; don't copy the inline styles.

## Rules that are easy to break

- **No mock features.** Every button, link, tab, previous/next, print and "check" in the design must work. If something can't be built properly, say so; don't fake it or silently drop it.
- **The LLM never computes math.** sympy computes and checks every answer and step. The LLM explains, diagnoses, phrases and transcribes, and is always given the verified answer.
- **Every LLM output has an abstain path** (`unclear`, `slip`, `out_of_scope`, "explanation unavailable"). Never show unverified math.
- **No chat UI, no scores, no accounts, no database, nothing stored.** Drawings and photos are processed in memory only. Don't log free text.
- **Content is generated offline and served as static JSON** (`content/generated/<lang>/`). That includes step explanations and translations. Only per-teacher input (`/api/mistake`, `/api/transcribe`) calls a model live. `/api/check-working` is sympy only.
- **Math is stored as structured steps** `{left, right, op}` with sympy-parsable strings, not LaTeX blobs. It is rendered by our own handwriting components on squared paper. KaTeX is only a fallback.
- **i18n and RTL from the start.** No hard-coded UI strings (react-i18next). Use logical CSS properties (`ms-/me-/ps-/pe-`). Math lines stay left-to-right inside RTL text. Translations never change the math fields.
- **Accessibility is WCAG 2.2 AA.** Every math expression has spoken text in the active language. The drawing board and camera always have a typed alternative (MathLive). Respect `prefers-reduced-motion`, including the write-on animation.
- **Akelius colour tokens:**
  - navy `#172b53`: primary and text;
  - pale blue `#d0efff`: selected states;
  - blue `#357ca2`: links;
  - yellow `#ffe923`: highlight;
  - green `#00a57c` for icons only, `#007a5c` for text (contrast);
  - background `#f6f7f9`.

  Don't use the Akelius logo.
- **Don't scrape Akelius content.** It states no license. Deep-link to their lessons instead.

## Layout

```
backend/     FastAPI (Python 3.12, uv). app/math/ = sympy core; LLM client behind one interface + one config
frontend/    React + Vite + TS (pnpm), Tailwind v4, shadcn/ui, Motion, MathLive, react-i18next
pipeline/    generate.py (offline packs, explanations, translations) + verify.py (deterministic checks first, then LLM judge)
content/     source/ (our lessons), practice/ (OATutor-Content, CC BY 4.0, attributed), generated/<lang>/ (verified packs)
evals/       mistakes.yaml, transcription/, run.py, results.yaml (hash-pinned; a test fails when stale)
infra/       idempotent az CLI scripts for rg-akelius-coach in switzerlandnorth
```

The data flow is source lesson → `generate.py` → `verify.py` → committed packs → API (held in memory) → frontend. `/api/mistake` runs in a fixed order: sympy solves the problem, then sympy classifies the student's answer, then finds the first line that doesn't follow, then tries the misconception rules, and only then makes one LLM call with structured output.

## Commands

The `Makefile` is the authority.
- `make install` once after cloning: `uv sync`, `pnpm install`, and Playwright's Chromium.
- `make dev` runs the API on :8000 and Vite on :5173 (proxying `/api`). `docker compose up` runs the full app on :8000.
- `make test` runs pytest and vitest. `make lint` runs ruff, ruff format, mypy, tsc, eslint and prettier. `make fmt` fixes formatting. `make build` builds `frontend/dist`. `make e2e` builds the frontend, then runs Playwright with axe-core against FastAPI serving it.
- Single tests: `cd backend && uv run pytest tests/test_math.py::test_name -q`, or `cd frontend && pnpm vitest run path/to/file.test.ts -t "name"`.
- Pipeline: `uv run python pipeline/generate.py --topic <id> --lang <code>`, then `uv run python pipeline/verify.py`.
- Evals: `make evals` (live, about $3.50; needs `.env`), or one step at a time: `uv run --project backend python evals/run.py run|judge|summarize` (see `evals/README.md`).

Use `uv` for Python and `pnpm` for Node. CI may not run because GitHub Actions is unpaid, so run `make test lint` locally before every PR.

## Azure

- Subscription "Azure for Students". Allowed regions are `switzerlandnorth` and `belgiumcentral` among others.
- Live model: `gpt-5.5` on **DataZoneStandard** (deployment `gpt-5.5-live`), which keeps processing in the EU data zone. `gpt-5.4-mini` DataZoneStandard has 0 quota on this subscription; swapping back is config only (`MODEL_LIVE`). Offline generation uses `gpt-5.5` on GlobalStandard (`gpt-5.5-offline`), since no personal data is involved.
- Secrets go only in the local `.env` and in Container Apps secrets.
- **Never touch `rg-tourlore-ai`**, which belongs to another project.
