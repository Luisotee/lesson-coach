# Lesson Coach

Lesson Coach helps math teachers of grades 6–9 refresh the math they teach and prepare their lessons, with no chat, no scores and no accounts. sympy computes and checks every answer; a language model only explains, diagnoses and reads handwriting, and is always given the verified result.

**Live:** https://ca-lesson-coach.ashycliff-c7de378e.switzerlandnorth.azurecontainerapps.io. The app scales to zero when idle, so the first request after a quiet spell takes about 20 seconds.

Built for Akelius as a take-home assignment.

## Run it

**With Docker**, the full app on http://localhost:8000:

```sh
cp .env.example .env    # then fill in the Azure OpenAI keys (below), or leave them empty
docker compose up --build
```

**For development**, needs [`uv`](https://docs.astral.sh/uv/), Node 22+ with `pnpm`:

```sh
make install    # Python and Node dependencies, Playwright's Chromium
make dev        # API on :8000, app on http://localhost:5173 (proxies /api)
```

**`.env` keys** (see [`.env.example`](.env.example); `infra/up.sh` writes them for our Azure resource):

| Key | What |
|---|---|
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` | An Azure OpenAI resource |
| `AZURE_OPENAI_API_VERSION` | `2025-04-01-preview` |
| `MODEL_LIVE` | The deployment for live calls (`gpt-5.5-live`) |
| `MODEL_OFFLINE` | The deployment for the content pipeline and eval judge (`gpt-5.5-offline`); not needed to run the app |

**Without keys, almost everything still works:** topic pages, worked examples, misconceptions, practice with hints, "check my working" for typed lines, and the mistake explainer whenever sympy or a misconception rule settles the answer. Only two things need the model, and both say plainly that they couldn't run, never guess: the AI step of a mistake that no rule explains, and reading a photo or drawing.

### Tests and checks

```sh
make test     # pytest (math core, API, content, packs, evals pinning) and vitest
make lint     # ruff, ruff format, mypy, tsc, eslint, prettier
make e2e      # build, then Playwright with axe-core against FastAPI serving the build
make evals    # live evals against Azure, about $2.50 (needs .env)
make zip      # the delivery zip with .git, from a fresh clone: ../lesson-coach.zip
```

`make e2e` serves the app on port 8010 (and the dev server on that port + 1000); set `E2E_PORT` (and optionally `E2E_DEV_PORT`) to run it in parallel checkouts.

Single tests: `cd backend && uv run pytest tests/test_math.py::test_name -q`, or `cd frontend && pnpm vitest run path/to/file.test.ts -t "name"`. E2E against the live app: `cd frontend && BASE_URL=<live-url> pnpm exec playwright test`. Deploying: [`infra/README.md`](infra/README.md).

## Accessibility

The target is WCAG 2.2 AA. [`docs/A11Y.md`](docs/A11Y.md) lists what the e2e tests check (axe in every page state at five layouts, keyboard-only flows, reduced motion, print, the accessibility tree, and in other languages: Arabic, Chinese and Hindi pages, right to left at 320 px, 200% zoom and in print, spoken math in all 19 languages, and a web font for every script) and what hasn't been tested yet: no one has run a real screen reader on it.

## Layout

```
backend/     FastAPI (Python 3.12, uv). app/math/ is the sympy core; app/llm/ is the model client behind one interface
frontend/    React + Vite + TypeScript, Tailwind v4, shadcn/ui, Motion, MathLive, react-i18next
pipeline/    offline: generate.py (packs and explanations), translate*.py, verify.py (sympy checks, then an LLM judge)
content/     source/ (our lessons), practice/ (OATutor-Content, CC BY 4.0), generated/<lang>/ (verified packs, 18 languages)
evals/       mistake diagnosis and transcription evals, results.yaml (pinned to the code by a hash)
infra/       idempotent az CLI scripts: up, smoke, deploy, smoke-app, down
docs/        PLAN.md, TASKS.md, REASONING.md, COST.md, A11Y.md
```

## Docs

- [`docs/PLAN.md`](docs/PLAN.md): the design, and the source of truth for decisions.
- [`docs/REASONING.md`](docs/REASONING.md): the decisions and why, how the human and AI worked, the time spent, and known limits.
- [`docs/TASKS.md`](docs/TASKS.md): the work items and their acceptance criteria.
- [`DATA.md`](DATA.md): what data the coach handles and where it goes, and the licences.
- [`docs/COST.md`](docs/COST.md): the cost per teacher per month, and how to lower it.
- [`docs/A11Y.md`](docs/A11Y.md): accessibility, what is tested and what isn't.
- [`evals/README.md`](evals/README.md): how we know the answers are good. Also [`evals/verify-report.md`](evals/verify-report.md) and [`evals/translation-report.md`](evals/translation-report.md).
- [`pipeline/README.md`](pipeline/README.md), [`infra/README.md`](infra/README.md), [`content/ATTRIBUTION.md`](content/ATTRIBUTION.md).
- [`design/`](design/): the visual design (Claude Design canvas exported as HTML).

## The brief, item by item

### The need, and the teachers

| The brief says | What we did | Where |
|---|---|---|
| Teachers lack confidence in the math they teach; the coach helps them **refresh their knowledge and prepare lessons** | Three topics (negative numbers, fractions, linear equations), each with **three ways in**: a topic page to prepare a lesson (the idea, why it works, worked examples with "Why? / Another way / Picture" on every step, misconceptions, questions students ask, a printable lesson outline, a link to the matching Akelius lesson); "**a student wrote this**", which explains a student's mistake and what to say; and **private practice** with four hint rungs | [PLAN: Product](docs/PLAN.md#product), `frontend/src/pages/` |
| They **learn alone, online, in a browser** | A web app with no accounts and no setup; 18 languages, right to left included; WCAG 2.2 AA as the floor | Live URL; [A11Y.md](docs/A11Y.md) |
| They **dislike chatbots** | No chat box anywhere. Buttons, pages and structured results; each AI output is small and has a fixed place | [REASONING: decisions](docs/REASONING.md#the-decisions-that-matter) |
| **No tests, judgment, exams, scores or certificates** | Nothing is graded or recorded. Practice says "just for you, nothing is recorded"; "check my working" says privately which line first doesn't follow. Nothing is stored | [DATA.md](DATA.md) |
| **Good internet** | Content is served as static JSON; only per-teacher input calls a model | [PLAN: Architecture](docs/PLAN.md#architecture) |
| **20,000–50,000 teachers, so cost per teacher matters** | Content generated once, offline; known mistakes answered by rules, with no model call; one small model call only when needed; scale to zero. About **$0.07 of AI per teacher per month** | [COST.md](docs/COST.md) |

### What we were asked to do

| The brief says | What we did | Where |
|---|---|---|
| **Design and build a working prototype**; choose what it does, the needs and the form, as a product owner, and **explain the choices** | Deployed and tested end to end. The product choices and their reasons are in REASONING | Live URL; [REASONING](docs/REASONING.md) |
| **Course material:** open sources or a few short lessons we write | Our own three lessons (CC BY 4.0); practice problems from OATutor-Content (CC BY 4.0, attributed); Akelius lessons are **linked, not copied** (no licence stated) | [DATA.md: sources](DATA.md#content-sources-and-licences), [ATTRIBUTION](content/ATTRIBUTION.md) |
| **A frontend is optional** | Built, following our own design with Akelius's colours | `frontend/`, `design/` |
| **Use AI for writing code and inside the solution** | Claude Code planned, designed and built it (agent workers, each PR reviewed by another agent). Inside: `gpt-5.5` diagnoses mistakes, reads handwriting, and writes and translates the lesson prose offline, always checked by sympy | [REASONING: how we worked](docs/REASONING.md#how-the-human-and-the-ai-worked-together) |
| **Spend two hours and stop when the time is up** | **Not followed.** We chose to deliver a complete, working product. The real time is reported in full: about 4 h of planning wall clock (about 10 min of Luis's time) and a 6.75 h build by parallel agents | [REASONING: Time](docs/REASONING.md#time) |
| **Any language, tools, frameworks, models and APIs** | Python, FastAPI and sympy; React and TypeScript; Azure OpenAI `gpt-5.5`; Azure Container Apps | [PLAN: Architecture](docs/PLAN.md#architecture) |
| **Commit as you work** | Every task was built on its own branch in small commits and merged by PR. The planning before the build is not in git; the history starts with the plan | `git log`; [REASONING: Time](docs/REASONING.md#time) |
| **Questions: write to the person who sent the assignment** | **Not sent, by choice.** We drafted four questions ([PLAN](docs/PLAN.md#questions-for-mykola-not-sent)) and built on stated assumptions instead: planning time is reported apart from build time; Akelius content is linked, not reused; we assume Akelius Math doesn't share students' wrong answers, so the eval set comes from a public dataset; grades 6–9, three algebra topics, and as many languages as pass our checks | [REASONING: Time](docs/REASONING.md#time), [DATA.md](DATA.md) |
| **Send the repository as a zip with `.git`** | `make zip` writes it from a fresh clone (history included; no `.env`, dependencies or build output) | [`scripts/zip.sh`](scripts/zip.sh) |

### What the delivery explains

| The brief asks | Answer |
|---|---|
| **How to run it** | [Run it](#run-it), above. Azure: [infra/README.md](infra/README.md) |
| **Design and trade-offs** | [REASONING: decisions](docs/REASONING.md#the-decisions-that-matter) and the step log; [PLAN](docs/PLAN.md) |
| **What we skipped, and why** | [Below](#what-we-skipped-and-why) |
| **The time spent** | [REASONING: Time](docs/REASONING.md#time) |
| **How we know the coach gives good answers** | [Below](#how-we-know-the-answers-are-good) |
| **The cost per teacher per month, and how to lower it** | [docs/COST.md](docs/COST.md) |
| **In plain language, what data the coach handles and where it goes** | [DATA.md](DATA.md) |

### The four review criteria

| Criterion | Where to look |
|---|---|
| Product judgment and communication | [REASONING](docs/REASONING.md): the problem as we read it, the decisions table, the session log |
| Architecture and extensibility | [Below](#architecture-and-extensibility); [PLAN: Architecture](docs/PLAN.md#architecture) |
| Language models, answer quality and cost | [evals/README.md](evals/README.md), [COST.md](docs/COST.md), [pipeline/README.md](pipeline/README.md) |
| Documentation and compliance | This README, [DATA.md](DATA.md), [ATTRIBUTION](content/ATTRIBUTION.md), [A11Y.md](docs/A11Y.md) |

## How we know the answers are good

- **The model never computes math.** sympy writes every worked step and answer, and checks every claim in the generated prose. A guard hides any AI text containing a number sympy didn't give it.
- **Every AI output may abstain** ("unclear", "slip", "out of scope", "explanation unavailable"). Unverified math is never shown.
- **Offline content:** each piece of prose passes sympy-based checks and a majority LLM judge, or ships as unavailable; the English packs dropped nothing ([verify-report](evals/verify-report.md)). Translations keep every math field identical, checked character for character ([translation-report](evals/translation-report.md)).
- **Live evals** on 30 mistake cases (16 adapted from the MaE misconception dataset) and 11 drawn images, 3 runs each ([evals/README.md](evals/README.md)):
  - the right/wrong verdict was right in 90 of 90 runs;
  - no false "mistake" on the 15 control runs where the student was right;
  - the misconception is named right in 100% of the cases a rule answers, and in 50% of the 8 the model answers;
  - transcription read 45 of 45 lines right;
  - the results are pinned to the code by a hash, so a test fails when they go stale.
- **Tests:** about 490 pytest and 280 vitest tests, and Playwright with axe-core on every page and state, run locally and against the live URL.

## What we skipped, and why

- **Accounts, history and a database.** Teachers asked for nothing that judges them, and nothing stored means no personal data to protect.
- **Reusing Akelius Math content.** It states no licence, so we link to it instead. Content loads through one loader (`pipeline/sources.py`), so licensed Akelius content could replace our lessons later.
- **More topics.** Three topics done well, rather than many unchecked.
- **Six languages:** uk and sw failed their quality checks and were dropped; so, ti, ps and prs weren't reached.
- **A human screen-reader pass, native-speaker review, and teacher-labelled evals.** These need people we didn't have. See [REASONING: known limits](docs/REASONING.md#known-limits-and-next-steps).
- **`gpt-5.4-mini`** for live calls: it has no quota on this subscription, so we use `gpt-5.5`.
- **The Batch API** for offline generation (half price): interactive calls made retries and smoke tests simple.
- **More than one replica:** the rate limit lives in memory. Fine for a prototype, but not for 20,000 teachers.

## Architecture and extensibility

```
content/source + content/practice  →  pipeline/generate.py, translate.py  →  pipeline/verify.py
  →  content/generated/<lang>/<topic>.json (committed)  →  FastAPI (packs in memory)  →  React app
POST /api/mistake:        sympy solves → sympy classifies the answer → first line that doesn't follow → rules → one LLM call
POST /api/transcribe:     image in memory → vision model → lines the teacher confirms
POST /api/check-working:  sympy only
```

- **One model interface** (`backend/app/llm/client.py`) and one config (`backend/app/config.py`): changing model, region or reasoning effort is configuration.
- **Content is data:** a topic is a lesson, a misconceptions file and practice items; the pipeline makes, checks and translates its pack.
- **A `lang` parameter everywhere**, and right-to-left from the start.
- **Misconception rules** are small sympy functions; every new rule makes diagnoses more certain and cheaper.
