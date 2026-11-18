# What data the coach handles, and where it goes

In short: there are no accounts and no database, and the coach stores nothing about teachers or students. The only live AI calls send math (and, for a photo or drawing, the image) to Azure OpenAI in Microsoft's EU data zone. Nothing is used to train models.

## What is stored

**Nothing**, apart from three things that hold no personal data:

- **The content:** lessons and practice problems, the same for every teacher, committed to the repository as JSON (`content/generated/<lang>/`). The server keeps them in memory.
- **The language choice**, in the teacher's own browser (`localStorage`). The header says so: "Only your language choice is kept, in this browser."
- **Container images** in our Azure container registry (`rg-akelius-coach`, Switzerland North), holding the app code only.

There are no accounts, no cookies for tracking, no analytics, no practice history and no scores. Practice progress lives only in the open page and is gone when it closes.

## What a teacher sends, and what happens to it

| What the teacher does | What leaves the browser | Who sees it | Kept? |
|---|---|---|---|
| Opens a topic, practises, checks typed working | The topic and language; the math lines for "check my working" | Our server only. sympy checks the lines; **no AI call** | No |
| "A student wrote this": types a problem, an answer and optional working | The problem, the answer and the working, as math (at most 2 letters per expression, so no names or sentences) | Our server. sympy solves and checks it, and known mistakes are matched by rules. A wrong answer goes to the AI model, as math, with sympy's verified answer: to diagnose it when no rule explains it, or, when a rule does, only to word what to say for this problem | No |
| Draws math (a mistake or practice working), or takes a photo of a student's work | The image: cropped, re-encoded and stripped of EXIF/GPS **in the browser** before upload, at most 5 MB | Our server, which passes it once to the AI model to read the lines, then drops it. The teacher confirms every line before anything else runs | No |

- **Photos and drawings** are read into memory, sent once to the model and dropped. They are never written to disk, stored or logged. The browser re-encodes a photo as JPEG through a canvas, which removes EXIF metadata (camera, time, GPS location) before it is sent. The drawing board sends black ink on white, without the grid. The crop step lets a teacher cut away anything but the math. The mistake page asks teachers not to type students' names; the photo screen doesn't yet ask them to keep names and faces out of the picture, which a launch should add.
- **No free text** is ever logged. Each AI call logs one line of numbers: task, model, latency, attempts, outcome and token counts (`backend/app/llm/azure.py`). The web server's access log prints the method, path, status and client IP of each request to the console. There is no log workspace, so nothing is kept: the console can only be watched live.
- **IP addresses** are held in memory for up to a minute by the rate limiter (20 mistake checks, 10 images and 60 working checks per minute per client), then forgotten. They go nowhere else.

## Where the AI runs

- **Live calls** (the mistake diagnosis and reading a photo or drawing) go to Azure OpenAI `gpt-5.5`, deployment `gpt-5.5-live`, type **Data Zone Standard**, in our resource in **Switzerland North**. Microsoft processes Data Zone requests only inside the data zone: for this resource, the **EU data zone**, which follows the EU Data Boundary (EU member states, plus EFTA countries such as Switzerland). Data at rest stays in the resource's geography, Switzerland. The app's server runs in Azure Container Apps in Switzerland North.
- **Microsoft's terms for Azure OpenAI:** prompts and outputs are not used to train models and are not shared with OpenAI. Microsoft's abuse monitoring may keep prompts and outputs that its classifiers flag (text and images) in the same geography, for review by authorised Microsoft staff located in the EEA. We have not applied for modified abuse monitoring, which would turn that storage off. Microsoft's current pages give no retention period. Sources, read 2026-11-18: [deployment types](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/concepts/deployment-types), [data privacy](https://learn.microsoft.com/en-us/azure/ai-foundry/responsible-ai/openai/data-privacy), [abuse monitoring](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/abuse-monitoring).
- **Offline generation** (lesson prose, step explanations, translations, and the eval judge) uses `gpt-5.5` on **Global Standard** (`gpt-5.5-offline`). Global Standard may process anywhere Microsoft runs the model. That is acceptable here because offline work sends only our own lessons, never anything from a teacher.
- **Secrets:** the Azure OpenAI key lives only in the local `.env` (never committed) and in a Container Apps secret. The browser never sees it.

## Legal basis (GDPR)

The coach is built to process as little personal data as possible: no accounts and nothing stored. What it does handle is the request itself, which may carry an IP address, and an image of student work if the teacher sends one. Those are processed only to give the teacher the answer they asked for (legitimate interest, or a task carried out for the teacher), are not kept, and stay in the EU data zone. A production launch by Akelius would still need its own privacy notice, a data processing agreement with Microsoft (part of Azure's standard terms), and guidance for teachers on photographing student work without names or faces.

## Content sources and licences

| Source | Licence | How we use it |
|---|---|---|
| Our own lessons and misconceptions (`content/source/`) | CC BY 4.0 (ours) | Written for this project, drafted with AI and marked `ai_generated` field by field; every answer and claim is checked by sympy |
| [OATutor-Content](https://github.com/CAHLR/OATutor-Content), problems from OpenStax *Elementary Algebra 2e* and *Intermediate Algebra 2e* | CC BY 4.0, attributed | 24 practice problem steps, adapted, at a pinned commit; each item names its source, licence and what we changed |
| [MaE math misconceptions dataset](https://github.com/nancyotero-projects/math-misconceptions) | MIT | 16 eval cases, numbers changed and reworded; licence text included |
| [Akelius Math](https://akelius.education/math/en) | No licence stated | **Links only.** Each topic deep-links to the matching Akelius lesson. We copied titles and URLs, never content, and did not scrape the site |

Full attribution: [`content/ATTRIBUTION.md`](content/ATTRIBUTION.md).

## What is generated offline, and how it is checked

Everything that is the same for every teacher is generated once, checked, and committed. No teacher's request generates content.

- **Worked steps and answers:** computed by **sympy**, not by a model.
- **Lesson prose and the "Why? / Another way / Picture" explanations:** written by `gpt-5.5` (Global Standard). Each piece must pass deterministic sympy-based checks (every claim true, every number taken from its step), then a majority vote of an LLM judge. What still fails ships as "explanation unavailable", never unchecked ([`pipeline/README.md`](pipeline/README.md), [`evals/verify-report.md`](evals/verify-report.md)).
- **Translations (18 languages):** translated from the English packs by `gpt-5.5`. Every math field and every math span in the prose is copied character for character and verified identical; an LLM judge reviews meaning, math terms and grammar. Every language except English is marked machine-translated in the app ([`evals/translation-report.md`](evals/translation-report.md)).
