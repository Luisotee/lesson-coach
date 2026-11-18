# How we built this, and why

A short record for reviewers. `docs/PLAN.md` has the full plan.

## The problem as we read it

Teachers who doubt their own math need two things: to feel sure of a topic, and to know what to say when a student goes wrong.

They work alone, dislike chatbots, and want nothing that grades them. With 20k–50k of them, the coach must be cheap per teacher. In a coach, a wrong math answer is the worst possible failure.

## The decisions that matter

| Decision | Why |
|---|---|
| **No chat.** Pages, buttons and structured results | The brief says teachers dislike chatbots. Buttons ("Why?", "Another way", "Picture") also keep each AI output small and checkable |
| **The LLM never computes math. sympy does** | Peer research found LLM tutors got wrong answers *and* wrong steps (32% of problems in OATutor's study). sympy computes the answers, and the LLM only explains and diagnoses with the answer given |
| **Every AI answer may say "I can't tell"** | One wrong answer is weak evidence. Forced labels made other projects invent misconceptions |
| **Known mistakes are matched by rules, without AI** | If "adds tops and bottoms" reproduces the student's 2/5, the diagnosis is certain and costs nothing |
| **Content generated once, verified, served as static JSON** | Every teacher sees the same explanations. Generating them once makes them free per teacher and lets every one be checked before anyone sees it. No database is needed |
| **No accounts, nothing stored** | Fits "no judgment" and makes the data story short: there is no personal data to protect |
| **Math looks hand-written on squared paper** | The product owner's feedback: typed math felt like a computer, not like school |
| **Type, write or photograph the math** | Teachers write math by hand. A photo of a student's work also gives the full working, which makes the diagnosis far better. The teacher always confirms the transcription first |
| **Modern design with Akelius DNA** | Their colours, lesson conventions (balance scale, operation shown on both sides) and openness about AI, in a new and faster-feeling product |
| **Many languages, accessible from day one** | Akelius serves refugees in 13+ languages, so language and accessibility can't be added later |

## How the human and the AI worked together

I (Luis) acted as product owner. Claude Code researched, planned and designed, and Claude Code workers build. The session, step by step:

1. **Me:** "Here is the assignment; let's talk about it first." **Claude:** read the brief, the email and Akelius's site, then proposed four product ideas. Its recommendation was a lesson-prep page without chat.
2. **Me:** "I like all of them. Build the whole app with a frontend, on my Azure credits." **Claude:** checked the subscription. The allowed region `switzerlandnorth` offers `gpt-5.4-mini` on DataZoneStandard, so live AI stays in the EU data zone.
3. **Claude:** checked whether Akelius Math content could be reused. It is served by an undocumented API with no license, so we don't scrape it: we write our own lessons and deep-link to theirs.
4. **Me:** "Before building, see how similar apps are built." **Claude:** found 5 open-source peers and had an agent read each codebase against our plan. It checked their 13 findings, and these changed the plan:
   - sympy computes the answer first;
   - "I can't tell" is always an option;
   - known mistakes are matched by rules;
   - the eval set comes from a published misconception dataset.
5. **Me:** "Why JSON and not a database? Will there be a login?" **Claude:** explained why neither is needed. That led to one more change: step explanations are generated offline too, so there's no runtime cache to lose.
6. **Claude:** designed seven screens on a Claude Design canvas (desktop, tablet and phone).
7. **Me:** "Look at Akelius's own website." **Claude:** extracted their design tokens and studied a real lesson. **Me:** "Keep it modern, but it should feel like Akelius." **Claude:** rethemed the design with their colours and lesson conventions (balance scale, operation shown on both sides).
8. **Me:** "The math looks like a computer wrote it, not a person." **Claude:** switched to handwriting on squared paper, stacked fractions, steps aligned on `=`, and margin notes like `| −5`.
9. **Me:** "Can teachers write math by hand, or take a photo?" **Claude:** added type, write and photo input. The teacher confirms the transcription before anything runs, and a photo of the working shows the first line that doesn't follow.
10. **Me:** "Add every language you can, strong accessibility, a drawing board in practice, no mock buttons, and a short reasoning doc." **Claude:** wrote the final plan, a task list in waves, and agent instructions (`CLAUDE.md`).
11. **Build:** tasks are handed to Claude Code workers through agent-mesh (`/delegate-claude`). Each works on its own branch, and each PR is reviewed before merge. *(Log continues below as the build runs.)*
12. **T4 infra:** `gpt-5.4-mini` DataZoneStandard quota is 0 on Azure for Students; switched live to `gpt-5.5` DataZoneStandard to keep EU processing. Offline uses `gpt-5.5` on GlobalStandard, because GlobalBatch can't be called interactively or smoke-tested.
13. **T1 math core:** Claude wrote its own small parser instead of sympy's `parse_expr` or `parse_latex`. `parse_expr` runs Python `eval` on its input, and `parse_latex` computes as it reads (`\frac{2}{4}` becomes `1/2`, and `1\frac{1}{2}` loses its whole part). The core must keep what the student wrote, so it can tell `2/4` from `1/2` and match misconception rules. sympy still computes every value. Review found two short inputs that hung the core, so it now accepts at most 2 letters and degree 20, and the API (T6) adds a time limit. Each misconception rule now gives its own diagnosis: `wrong_inverse_order` moved to `(x + b)/a = c`, so it no longer gives the same answer as `divide_one_term`.
14. **T3 frontend:** math is drawn by our own small parser for the sympy step strings (it keeps the author's brackets and `3x` vs `3 · 5`, which a general math library would normalise away), with spoken text from locale messages under `role="math"`. The design's pencil grey (2.55:1) and the link blue on the page background (4.30:1) fail AA, so pencil is `#5b6475` and link text off white surfaces is `#2b6788`. The language picker is a native select. The language choice is the one thing kept, in the viewer's own browser (localStorage), as a convenience with no personal data; the header says so ("Only your language choice is kept, in this browser"), so "nothing stored" stays true for teacher and student data. Fonts per script load only when that language is active; CJK waits for zh-Hans in T9 (about 4.6 MB of subsets).
15. **Content (T2):** the lessons, misconceptions and hint rewrites are our own, drafted with AI and marked `ai_generated`. Practice comes from OATutor-Content and the eval seed from MaE, both at pinned commits. A pytest checks every answer with sympy, and the same check rejects an OATutor item that says `(-3)^5 = 243` (it is -243), so we left that item out. The draft pack schema lives in `backend/app/content/schema.py`, so the API and the pipeline share one set of models. The Akelius lesson links came from the site's own search box, since search engines don't index its lessons; we recorded only titles and URLs.
16. **T6 API:** a wrong answer that a sympy rule reproduces is answered from the pack's misconception card, with no LLM call; only a wrong answer no rule explains gets one LLM call, always told sympy's answer. All sympy work runs in worker processes that are killed after 3 s, because a thread can't be stopped and sympy holds the GIL. The worked-out answer on the result screen comes from a small sympy step generator, never from the LLM. A deterministic guard hides any AI text holding a number sympy didn't give it. It checks numbers only, so a wrong claim built from given numbers can still pass; the evals (T10) measure how often replies are held back as `ai_unverified_math`.
17. **T7 math input:** one `MathInput` with type, write and photo tabs gives the page the API's own shapes (`{latex}`/`{text}` or a list of `{left, right, op}` lines); written and photographed math reaches the page only after the teacher confirms each line, and an edit takes the confirmation back. MathLive (MIT) is loaded only when a field opens, so it stays out of the main bundle, and its fonts come from our build with sounds off. The drawing is sent as black ink on white without the grid, which a vision model could misread as minus signs. Photos are decoded with their EXIF rotation, cropped, turned if needed, and re-encoded as JPEG through a canvas, which drops EXIF and GPS data and keeps them under 4 MB. A line that our drawing parser can't read is still sent as written: the frontend never judges the math.
18. **T5 pipeline:** sympy writes every worked step and answer, and the LLM writes only prose: the pack text and each step's explanations. Every piece of prose must pass the sympy-based checks (claims true, a claim about the unknown true at the worked solution, numbers from its step) and a majority LLM judge, or it ships as unavailable; a part that fails a check is dropped on its own and the rest is still judged, and if the judge gives no verdict nothing ships. Misconceptions and practice are copied from the sources rather than generated. Prompts come from a fixed list per kind and language ("Work out:", "Solve for x:"), so a translation can't change their math. The English run after review made 18 generation and 22 judge calls, about $1.06, and dropped nothing. A claim about the unknown passes only as an identity or at the solution of the example it names.
19. **T12 deploy:** the app runs on Container Apps with 0–1 replicas: it scales to zero when idle (the first request after idle waits about 20 s), and one replica at most keeps the in-memory rate limit to one bucket per client. Azure for Students blocks ACR Tasks, so `infra/deploy.sh` builds the image with local Docker from `git archive` of the commit, which keeps `.env` and local changes out of the image. The az CLI now creates environments in an "Express" mode by default, and that mode can't pull from ACR with the app's managed identity, so the environment is pinned to WorkloadProfiles. A second client, a temporary Container Apps job, confirmed that clients get separate rate-limit buckets and that a forged `X-Forwarded-For` doesn't give a new one.

Every factual claim (licenses, dataset contents, model availability) was checked before it went into the plan.

## Time

Human time and AI time are counted separately. Both are active working time; the session sat idle in between.

| Phase | My active time | Claude's active time |
|---|---|---|
| Understanding, research, plan, peer review, design | ~10 min | ~30 min (peer agents also ran in parallel in the background) |
| Build (agents) | to be filled | to be filled from the commit log |
| Review and delivery | to be filled | to be filled |

The brief asks for two hours. I chose to deliver a complete, working product, and I report the real timeline. The git history starts when the build starts. Planning happened before the first commit.
