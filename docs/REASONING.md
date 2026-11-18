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

- **The product owner (Luis)** set the direction and made the calls: the scope ("all of the suggestions"), "no database? no login?", the design taste, "it should still feel like Akelius", "math should feel human", photos and drawing, languages, accessibility, and "no mock buttons".
- **Claude Code, as planner and researcher,** did the following:
  - read the brief and the email, researched Akelius (website, design tokens, a real lesson's structure), and checked the Azure subscription's regions and models;
  - wrote the plan;
  - ran **peer research**: it found 5 open-source projects with similar mechanisms (Oak's Aila, OATutor, llm-math-education, MathTutorBench, AITutor-EvalKit), had an agent read each codebase against our plan, and checked their 13 findings before adopting them;
  - designed the UI on a Claude Design canvas and revised it three times from feedback.
- **The build** is split into the tasks in `docs/TASKS.md` and given to Claude Code workers through agent-mesh (`/delegate-claude`). Each worker builds in its own branch, and each PR is reviewed before merge.
- Every factual claim (licenses, dataset contents, model availability) was checked before it went into the plan.

## Time

Human time and AI time are counted separately, because most of the work ran unattended.

| Phase | My active time | Elapsed, with AI working |
|---|---|---|
| Understanding, research, plan, peer review, design | ~20 min | ~3 h 45 min |
| Build (agents) | to be filled | to be filled from the commit log |
| Review and delivery | to be filled | to be filled |

The brief asks for two hours. I chose to deliver a complete, working product, and I report the real timeline. The git history starts when the build starts. Planning happened before the first commit.
