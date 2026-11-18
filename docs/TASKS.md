# Tasks

Work items for the build. `docs/PLAN.md` has the full design, and `design/*.dc.html` is the visual reference (canvas: https://claude.ai/artifact/2JH48uYkKFRLC1mrJG2NUC).

Rules for every task:
- **No mock features.** Everything visible must work. If something can't be built properly, say so in the PR; don't fake it or drop it.
- **No chat UI, no scores, no stored personal data.**
- **Accessible** (WCAG 2.2 AA) and **translatable** from the start: no hard-coded UI strings, and logical CSS properties for RTL.
- **The LLM never computes math.** sympy does.
- **Tests come with the code.** Run the repo's checks locally before the PR; CI may not run.
- **Commit messages** are plain, short and in full sentences.

Status: `[ ]` todo · `[~]` in progress · `[x]` done.

## Wave 0: foundation (one worker, blocks everything)

- [x] **T0 Scaffold the monorepo**
  - Layout: `backend/` (FastAPI, uv, Python 3.12), `frontend/` (pnpm, Vite, React, TS, Tailwind v4, shadcn/ui, Motion, react-i18next), `pipeline/`, `content/`, `evals/`, `infra/`, `docs/`.
  - A `Makefile` with `dev`, `test`, `lint`, `fmt`, `build`, `e2e`.
  - Python tools: ruff + mypy + pytest. Frontend tools: eslint, prettier, vitest, Playwright.
  - A Dockerfile (multi-stage: build the frontend, serve it from FastAPI) and `docker-compose.yml`.
  - `.env.example`, a `.gitignore` that excludes `.env` and secrets, and a stub `README.md`.
  - **Done when:** `make test lint build` passes on a clean clone, and `docker compose up` serves a hello page with `/api/health`.

## Wave 1: parallel after T0

- [x] **T1 sympy math core** (`backend/app/math/`)
  - Parse plain text and LaTeX (from MathLive) into sympy.
  - Solve a problem, and canonical-form checks.
  - `classify_answer` returns `correct`, `equivalent_not_simplified` or `wrong`.
  - Step check: each step is equivalent to the previous one **and** structurally different from it.
  - `first_line_that_doesnt_follow(lines)`.
  - A registry of misconception rules per topic (for example `add_tops_and_bottoms`, `sign_not_changed`, `divide_one_term`) that reproduce wrong answers.
  - **Done when:** pytest covers each function, including the guards (an identical step is rejected; `2/4` for "simplify 2/4" is not simplified; `x=3` equals `3`; `-2/4` equals `-1/2`).
- [x] **T2 Content**
  - Write 3 English source lessons in `content/source/` (negative numbers, fractions, linear equations), short and teacher-level, CC BY 4.0.
  - Import 8 practice problems per topic from OATutor-Content (CC BY 4.0) into `content/practice/`, with attribution per item.
  - Define 4–6 misconceptions per topic that link to T1 rules.
  - Seed `evals/mistakes.yaml` from MaE (MIT, pinned commit). Check each row with sympy and reword the numbers.
  - Record the Akelius Math deep link per topic (`https://akelius.education/math/en/lesson/22124` for two-step equations; find the others by searching the site, without scraping its content).
  - **Done when:** the files validate against the T5 schemas (or a draft schema), and attribution is complete.
- [x] **T3 Frontend foundation**
  - Akelius tokens as the Tailwind theme (PLAN, "Look and feel"). Fonts: Figtree, Inter, Kalam, and Noto fallbacks per script.
  - App shell and routing (`/`, `/topics/:id`, `/mistake`, `/practice/:topic/:n`), skip links, focus styles, reduced motion.
  - i18n: react-i18next, an English locale, a working language picker, an RTL switch (`dir`), and lazy-loaded locales.
  - **Math renderer components:** `Fraction`, `EquationLine` (aligned on `=` with a margin op), `Notebook` (squared paper), `Pen` variants (pencil, ink, green), and a write-on animation that is off under reduced motion. Each produces spoken text through `aria-label` or MathML.
  - **Done when:** a Storybook-like demo route renders every math component in LTR and RTL, and axe reports no violations.
- [x] **T4 Azure infrastructure** (`infra/`)
  - Scripts (az CLI, idempotent) that create `rg-akelius-coach` in `switzerlandnorth` with:
    - an AI Services account;
    - deployments `gpt-5.5` live (**DataZoneStandard**; `gpt-5.4-mini` has 0 quota there) and `gpt-5.5` offline (GlobalStandard);
    - a Container Apps environment with scale-to-zero;
    - ACR Basic.
  - Write the endpoint and key into the local `.env` only. **Leave `rg-tourlore-ai` untouched.**
  - **Done when:** `infra/up.sh` runs, `infra/smoke.sh` gets a structured-output reply from both deployments, and the deployment SKUs are verified with the CLI.

## Wave 2

- [ ] **T5 Generation and verification pipeline** (needs T1, T2, T4)
  - Pydantic pack schemas (PLAN, "Pack schema").
  - `pipeline/generate.py`:
    - refresher, why it works, 3 worked examples with sympy-computed answers;
    - step explanations (why, another way, visual spec);
    - misconceptions, expected student questions with answers, lesson outline;
    - `ai_generated` markers on generated fields.
  - `pipeline/verify.py`: every check in PLAN, plus a targeted retry and majority vote.
  - Commit `content/generated/en/*.json`.
  - **Done when:** every pack passes verification, and the verify report goes in `evals/verify-report.md`.
- [x] **T6 Backend API** (needs T1, T4)
  - `GET /api/topics`, `GET /api/topics/{id}?lang=`.
  - `POST /api/mistake`: the full pipeline in PLAN, with structured LLM output and abstain paths, in the teacher's language.
  - `POST /api/transcribe`: image in, structured lines with confidence out, never stored.
  - `POST /api/check-working`: sympy only.
  - Supporting pieces:
    - an LLM client interface with one config, prompt-cache layout, token logging (no free-text logs);
    - input limits, in-memory rate limiting, and a 5 MB image limit with MIME checks.
    - sympy work under a wall-clock limit (a process pool or similar). The math core bounds letters (2), degree (20) and digits, but a time limit is the backstop; `MathParseError` and `UnsupportedProblem` map to the abstain path.
  - **Done when:** pytest passes with a mocked LLM, plus one live smoke test per endpoint.
- [x] **T7 Math input components** (needs T3; T6 for live wiring)
  - **Type:** MathLive field with a virtual keyboard on touch and LaTeX output.
  - **Write:** a drawing board (pointer events, `perfect-freehand`, undo/clear/redo, squared paper, export to PNG).
  - **Photo:** camera (`capture="environment"`) or upload, then a crop step (client-side), then a downscale.
  - **Transcription confirm screen:** handwriting rendering, each line editable, uncertain lines highlighted.
  - A shared `MathInput` component with **type / write / photo** tabs.
  - **Done when:** every mode is keyboard- and screen-reader-usable (write and photo always offer the type alternative) and works on touch (tested in a Playwright mobile emulator).
- [ ] **T8 Pages** (needs T3 and T7; uses T5 packs, with fixture packs at first)
  - **Home, Topic, Mistake and Practice, matching the design and fully working:**
    - prev/next and the "refresh first" links;
    - the worked-example notebook with the three explanation modes;
    - the visual mode as an animated balance scale or bar model;
    - the misconception cards and the questions accordion;
    - the lesson outline with a print stylesheet;
    - the mistake result states with the circle and margin-note annotations;
    - practice hints;
    - "check my working" on the drawing board.
  - **Responsive layouts:** phone (step explanation in a Vaul bottom sheet), tablet and desktop.
  - **Done when:** every element in `design/*.dc.html` works, and every page works at 320 px, 768 px and 1440 px.

## Wave 3

- [ ] **T9 Languages** (needs T5 and T8)
  - Extract all UI strings and translate them offline to the PLAN list (Akelius's 13 plus uk, tr, fa, ur, hi, bn, zh-Hans, sw, so, ti, ps, prs).
  - Translate the packs, keeping the math fields identical (verified).
  - Mark languages that are machine-translated and unreviewed. Fill in the font fallbacks per script.
  - **Done when:** a pytest/vitest completeness test passes (every key in every language, every pack in every language), and RTL pages render correctly in Playwright screenshots.
- [ ] **T10 Evals** (needs T6)
  - `evals/run.py` over `mistakes.yaml` and `evals/transcription/`, 3 runs per case.
  - Metrics and the judge with calibration as in PLAN. `evals/results.yaml` with a hash, plus a staleness test.
  - Compare minimal and low `reasoning_effort`.
  - **Done when:** results are committed and summarised in `evals/README.md`.
- [ ] **T11 Accessibility and end-to-end** (needs T8 and T9)
  - Playwright covers every page and state: axe-core, keyboard-only flows, RTL, print, reduced motion, 200% zoom, 320 px.
  - Document a manual screen-reader pass.
  - **Done when:** zero axe violations, and the e2e suite runs green through `make e2e`.
- [ ] **T12 Deploy** (needs T6 and T8)
  - Build and push the image, deploy to Container Apps with secrets, and smoke-test the live URL with the Playwright flow.
  - **Done when:** the live URL works and the scale-to-zero setting is verified.

## Wave 4: wrap-up

- [ ] **T13 Docs and delivery** (needs all)
  - `README.md`, `DATA.md` (including photos), the cost per teacher per month with measured token numbers, and a final `docs/REASONING.md`.
  - Honest time spent, from the commit log and session notes.
  - Make the zip with `.git`.
  - **Done when:** a reviewer can run the app from the README alone, and every brief item is answered.
