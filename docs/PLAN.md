# Plan: math teacher coach

This plan is the source of truth for the build. `docs/TASKS.md` splits it into work items, and `docs/REASONING.md` explains the decisions for reviewers.

## Context

Akelius, a non-profit education foundation that works with UNICEF and runs the free Akelius Math lessons, sent a take-home assignment (`2026-11-17_assignment_…pdf`): build the first part of a coach that helps **math teachers** refresh their knowledge and prepare lessons. The zip, including `.git`, is due **24 Nov 2026**. A 1.5–2 h interview follows, where the team challenges our decisions.

Constraints from the brief:
- Teachers learn alone in a browser.
- They **dislike chatbots**.
- They want **no tests, scores, judgment or certificates**.
- There will be 20k–50k teachers, so **cost per teacher** matters.

The review weighs four things:
- product judgment and communication;
- architecture and extensibility;
- LLM use, answer quality and cost;
- docs and compliance.

The brief says "two hours, commit as you work". We report the real time honestly in `docs/REASONING.md` and the README.

**Akelius Math content** is interactive student slides served by an undocumented API, with no license stated. **Do not scrape it.** We write our own teacher-level lessons, deep-link each topic to the matching Akelius lesson (for example two-step equations at `https://akelius.education/math/en/lesson/22124`), and keep content behind a `Source` adapter so Akelius content can plug in later.

## Guiding rules

1. **The LLM never computes math, and never has to answer.** sympy computes every answer. The LLM explains, diagnoses, phrases and transcribes. Every LLM output has an abstain path.
2. **No chat UI, no scores.** The coach works through buttons, pages and structured results, never a chat box. Nothing is graded and nothing is tracked.
3. **No mock features.** Everything the design shows must work in the real app: every button, link, tab, previous/next, print, topic chip and "refresh first" link. The design (`design/*.dc.html`) shows features; it is not a spec of what may be faked. If a design element can't be built properly, raise it; don't delete it silently.
4. **Generate offline, verify, then serve static.** Everything that is the same for every teacher is generated once, verified, and committed as JSON: packs, step explanations and translations. Only per-teacher input calls a model live.
5. **No accounts, no database, no stored personal data.**

## Product

Three grade 6–9 algebra topics: **negative numbers**, **fractions** (equivalence and operations) and **solving linear equations**.

1. **Home.** Topic cards, three ways in (prepare a lesson, understand a mistake, practise privately), a language picker, and a "no account, nothing saved" note.
2. **Topic page ("prepare a lesson")** has these sections:
   - **The idea** and **why it works**.
   - **Refresh first:** prerequisite chips that link to other topics and sections.
   - **3 worked examples**, shown as a squared-paper notebook. Each step is a handwritten line aligned on `=`, with the operation in a green margin note (`| −5`).
     - Selecting a line shows **Why? / Another way / Picture**, all pre-generated. Picture is an animated balance scale or bar model.
     - A check line at the bottom has a hand-drawn tick.
     - A label reads "written with AI · math checked by a math engine · reviewed".
   - **Common misconceptions:** belief, an example wrong answer, why it feels right, and an "Ask:" line.
   - **Questions students ask:** an accordion.
   - **Lesson outline:** a timeline with a working print view (print stylesheet).
   - **A link to the matching Akelius Math lesson.**
3. **"A student wrote this" mistake explainer.**
   - **Input**, one of three tabs:
     - **type:** MathLive math field, where typing `1/2` shows a stacked fraction, with a virtual math keyboard on touch devices;
     - **write:** a squared-paper drawing board for finger or pen;
     - **photo:** camera or upload, a crop step, then the transcription.
   - **Optional fields:** the student's working (any of the three modes) and the topic.
   - **Transcription confirm step** for "write" and "photo": the vision model's reading is shown in the handwriting style, each line editable, uncertain lines highlighted. The teacher confirms before anything runs.
   - **Pipeline, in order:**
     1. sympy solves the problem.
     2. sympy classifies the student's answer as `correct`, `equivalent_not_simplified` or `wrong`.
     3. If working was given, sympy finds the **first line that doesn't follow** from the one before.
     4. Deterministic misconception rules are tried: a rule that reproduces the student's answer gives a high-confidence diagnosis with no LLM call.
     5. Only then is there one LLM call. It returns structured output: `status` (`diagnosed | slip | unclear | out_of_scope`), up to 2 `misconception_id`s from the topic pack plus `other`, `explanation`, `what_to_say {probe, nudge, tell}` and `follow_up_example_id`, chosen from verified pack items.
   - **Result screen** follows the design:
     - **what they wrote:** pencil on paper, the wrong part circled, a margin note;
     - **the answer, worked out:** green pen, plus a bar model where it helps;
     - **what you could say;**
     - **try next.**

     It also has the "your student is right" and "not sure from one answer" states.
4. **Private practice.**
   - 8 problems per topic (from OATutor-Content, CC BY 4.0, with attribution), with working previous/next.
   - 4 hint rungs revealed one at a time: goal, information, computation, answer.
   - **The working area is a drawing board** (plus type mode). "Check my working" transcribes the lines and sympy reports privately which line first doesn't follow, or that all lines follow. There is no score and nothing is stored or sent beyond that one check.

## Math input and rendering

- **Rendering:** a small React renderer for the structures our topics use: stacked fractions, aligned equation lines, margin operations and mixed numbers. It uses a handwriting font (Kalam for Latin scripts, a fallback per script) on squared paper. Pencil grey is for student work, navy ink for worked examples, green pen for corrections. KaTeX is the fallback for anything outside that set.
- **Data shape:** math is stored as structured steps `{left, right, op}` with sympy-parsable strings, never as LaTeX blobs.
- **Typing:** MathLive (MIT) produces LaTeX, which is converted to sympy with `latex2sympy2` or `sympy.parsing.latex`, and plain text is accepted as a fallback.
- **Drawing board:** pointer-events canvas with pressure-aware strokes (`perfect-freehand`), undo/clear, line guides on squared paper, and keyboard access through the type tab.
- **Recognition** (drawing and photo): the vision model returns `{lines: [{left, right, op, confidence}]}`, followed by mandatory teacher confirmation, then sympy. Images are cropped client-side before upload, processed in memory and never stored.

## Languages (as many as we can do well)

- **UI:** `react-i18next` with ICU messages. Strings are extracted to `frontend/src/locales/<lang>.json` and translated offline by the pipeline, plus a review pass.
- **Target:** Akelius's 13 languages (ar, en, fr, de, el, it, pt, pt-BR, ru, es, sv, pl, kk) plus uk, tr, fa, ur, hi, bn, zh-Hans, sw, so, ti, ps, prs. The last ones cover refugee settings.
- **RTL:** `dir="rtl"` support for ar, fa, ur, ps and prs, using logical CSS properties throughout (Tailwind `ms-/me-/ps-/pe-`). Math lines stay left-to-right inside RTL text.
- **Content packs** are translated per language in the pipeline. The math fields are copied unchanged and verified by sympy after translation; the prose is translated.
- **Live mistake explainer** answers in the teacher's UI language.
- **Fonts:** a handwriting fallback per script (Noto families for Arabic, Devanagari, Bengali, CJK and Ethiopic).
- **Quality:** a language listed as available must have complete UI strings and packs. Mark any language whose translations are unreviewed as "machine-translated".

## Accessibility (WCAG 2.2 AA as the floor)

- Semantic HTML, full keyboard operation and a visible focus ring everywhere. Skip links.
- Every math expression has spoken text (`aria-label`, or MathML generated from the structured steps, for example "one half plus one third") in the active language.
- The drawing board and camera always have a typed alternative. Canvas content is described in text.
- Text contrast is at least 4.5:1 (Akelius green `#00a57c` only for icons; `#007a5c` for text). Touch targets are at least 44 px. The layout reflows at 200% zoom and 320 px width.
- `prefers-reduced-motion` stops all non-essential animation, including the handwriting "write-on" effect.
- `aria-live` announces results. Forms have labels and error text.
- **Tests:** axe-core in Playwright on every page and state, plus a keyboard-only end-to-end flow. Document a manual screen-reader pass (NVDA or VoiceOver) in the README.

## Look and feel

Follow `design/*.dc.html` (published canvas: https://claude.ai/artifact/2JH48uYkKFRLC1mrJG2NUC). It is modern, animated and catchy, with Akelius DNA.
- **Akelius tokens as Tailwind theme colours:**
  - navy `#172b53`: primary, text;
  - pale blue `#d0efff`: selected;
  - blue `#357ca2`: links;
  - yellow `#ffe923`: highlight;
  - green `#00a57c` for icons, `#007a5c` for text;
  - background `#f6f7f9`;
  - greys `#e2e5e8` / `#c4c7ca`.
- **Type:** Figtree headings, Inter body, lowercase small labels.
- **Components:** Tailwind v4, shadcn/ui and Motion (motion.dev). Respect reduced motion.
- **No Akelius logo:** the product is "Lesson Coach", built for Akelius.

## Architecture

```
content/source/<topic>.md        our lessons (CC BY 4.0)
content/practice/<topic>.json    OATutor-Content items (CC BY 4.0, attributed)
  │ pipeline/generate.py          offline; structured output; packs + step explanations + translations
  ▼
content/generated/<lang>/<topic>.json   verified packs, committed
  │ pipeline/verify.py             deterministic checks first, then LLM judge per claim
  ▼
backend/ (FastAPI)
  GET  /api/topics, /api/topics/{id}?lang=        packs, held in memory
  POST /api/mistake                               sympy → rules → LLM if needed; stores nothing
  POST /api/transcribe                            image (drawing/photo) → structured lines; stores nothing
  POST /api/check-working                         structured lines → first line that doesn't follow (sympy only)
  ▼
frontend/ (React + Vite + TS + Tailwind v4 + shadcn/ui + Motion + MathLive + react-i18next)
```

- **Stack:**
  - Python 3.12 with `uv`: FastAPI, sympy, pydantic, `openai` (Azure).
  - Node with `pnpm`.
  - One Dockerfile: the frontend is built and served by FastAPI as static files.
- **Models:** Azure OpenAI in `switzerlandnorth` (the subscription's allowed region).
  - Live calls use `gpt-5.5` on **DataZoneStandard** (deployment `gpt-5.5-live`), which keeps processing in the EU data zone. That covers both text and vision. The planned `gpt-5.4-mini` has 0 DataZoneStandard quota on Azure for Students; the deployment name lives in `MODEL_LIVE`, so swapping back is config only.
  - Offline generation and translation use `gpt-5.5` on GlobalStandard (deployment `gpt-5.5-offline`), acceptable because no personal data is involved. `GlobalBatch` would be cheaper but only works through the Batch API.
  - Model, `reasoning_effort` and token limits live in one config. Use `max_completion_tokens`, and send no `temperature` unless the deployment accepts it.
  - Prompts put fixed instructions and the source lesson first, then teacher input in delimiters. Every prompt includes "Output content only. Do not address the user."
  - Log `cached_tokens` and `reasoning_tokens` per call.
- **Pack schema (Pydantic):**
  - `WorkedExample {problem, steps[{left, right, op, explanations{why, another_way, visual}}], answer (sympy-computed)}`
  - `Misconception {id, belief, rule_sympy?, example_problem, example_wrong_answer, why_it_feels_right, what_to_say{probe, nudge, tell}, check_question, source_quote}`
  - `PracticeItem {problem, hints[4], answer, source, license}`
  - Claims carry `source_quote`. Items carry `ai_generated: [fields]`.
  - Lengths are enforced in validators after parsing.
- **Verification (`pipeline/verify.py`):**
  - Each step is sympy-equivalent to the previous one **and** structurally different from it.
  - Final answers are in canonical form; LaTeX and strings parse.
  - `source_quote` is a verbatim substring of the source lesson.
  - Misconception examples are reproduced by their rule.
  - Every number in an explanation appears in its step.
  - Translations keep the math fields identical.
  - Failures get a targeted retry that includes sympy's finding, then a majority vote of 3–5 samples. Anything that still fails is dropped and shown as unavailable, never shown unverified.
- **Hosting:** resource group `rg-akelius-coach` in `switzerlandnorth`, containing an AI Services account with the deployments above, Azure Container Apps with scale-to-zero, and ACR Basic. Leave `rg-tourlore-ai` untouched. `docker compose up` runs everything locally. Secrets live in Container Apps secrets, never in git or the browser.
- **Extensibility:**
  - a `Source` adapter (markdown now, Akelius API later);
  - a `lang` parameter everywhere;
  - a topic list driven by content files;
  - the LLM client behind an interface.

## Evaluation

- **`evals/mistakes.yaml`** has about 30 cases:
  - about 15 seeded from MaE (`nancyotero-projects/math-misconceptions`, MIT), sympy-checked and reworded;
  - about 5 we write ourselves;
  - about 5 controls where the student is right or equivalent;
  - about 4 slip or abstain cases.
- **`evals/transcription/`** has about 10 photos or drawings: clean, messy and rotated, scored on exact transcription per line.
- **`evals/run.py`** calls the real code paths, runs each case 3 times, and reports:
  - correct-answer rate and false "mistake" rate;
  - `misconception_id` exact match and abstain rate;
  - schema validity and transcription accuracy;
  - median and p90 latency;
  - tokens (including cached and reasoning) and cost per call.
- **LLM judge, for free text only:** dimensions are located / actionable / not revealing / non-judgmental, each scored `yes / to some extent / no`. Calibrate it against our hand labels (Cohen's kappa) before quoting it. Count judge failures.
- **`evals/results.yaml`** stores a hash of prompts, schemas, packs and config. A pytest fails when it is stale.
- **Model choice:** compare `none` and low `reasoning_effort` on the live model (`gpt-5.5`). gpt-5.5 rejects `minimal` with a 400, so `none` is the cheapest setting. The evals chose `none`: accuracy within noise of `low`, steadier over runs (see `evals/README.md`).
- **pytest** covers the sympy core (guards, rules, first line that doesn't follow), the API with a mocked LLM, i18n completeness (every key in every listed language), and that every pack step has its explanations.
- **Playwright** covers every page and state, axe-core, keyboard-only flows, RTL rendering and print.

## Docs

- **`README.md`**, in plain short lines, covers:
  - how to run (local and Azure) and the live URL;
  - design and trade-offs, and what was skipped and why;
  - time spent;
  - how we know answers are good;
  - **cost per teacher per month** as a worked formula: one-off offline cost amortised; mistake calls and photos per teacher × tokens × price; the share settled by sympy with no LLM; the retry rate; hosting; and how to lower it.
- **`DATA.md`** explains in plain language what data goes where:
  - no accounts;
  - typed input, drawings and photos: processed in memory, sent to Azure OpenAI in the EU data zone, never stored or used for training;
  - photos cropped client-side;
  - no free-text logs;
  - practice state stays in the browser;
  - the GDPR basis;
  - the licenses and attribution.
- **`docs/REASONING.md`:** short. What we built, why, and how the human and AI worked together.

## Questions for Mykola (optional)

- Does planning time count toward the two hours?
- May we reuse Akelius Math content?
- Does Akelius Math log students' wrong answers?
- Which grades and languages should come first?
