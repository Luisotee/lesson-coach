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

Every factual claim (licenses, dataset contents, model availability) was checked before it went into the plan.

## Time

Human time and AI time are counted separately. Both are active working time; the session sat idle in between.

| Phase | My active time | Claude's active time |
|---|---|---|
| Understanding, research, plan, peer review, design | ~10 min | ~30 min (peer agents also ran in parallel in the background) |
| Build (agents) | to be filled | to be filled from the commit log |
| Review and delivery | to be filled | to be filled |

The brief asks for two hours. I chose to deliver a complete, working product, and I report the real timeline. The git history starts when the build starts. Planning happened before the first commit.
