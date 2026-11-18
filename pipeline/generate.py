"""Builds a topic's pack: sympy writes the steps and answers, the LLM writes the prose.

    uv run --project backend python pipeline/generate.py --topic all --lang en

Each piece of LLM prose (the pack text, and each worked example's step explanations) goes
through the same loop: deterministic checks, then an LLM judge (a majority of 3 when it flags
anything) over every part that passed the checks; on failure one targeted retry that quotes
the findings, then up to 3 fresh samples. What still fails is dropped: its field is null and
listed in `unavailable`. If the judge gives no verdict after retries, its unit is dropped too:
nothing ships unjudged. Misconceptions and
practice are copied from the source files, which are already written and tested.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make `pipeline` and `app` importable
    sys.path[:0] = [str(Path(__file__).resolve().parents[1] / p) for p in ("", "backend")]

from app.content.schema import (
    TOPIC_IDS,
    ExplainedStep,
    OutlineStep,
    Pack,
    StepExplanations,
    StudentQuestion,
    TopicId,
    WorkedExample,
)
from app.math import solve
from pydantic import BaseModel

from pipeline.checks import (
    Finding,
    Known,
    dropped_paths,
    explanation_findings,
    math_problem,
    pack_findings,
    prose,
    solutions,
    step_numbers,
)
from pipeline.core import LLM, StepsFor, Task, offline_llm, worked_steps
from pipeline.examples import EXAMPLES, prompt_for
from pipeline.prompts import (
    JudgeOut,
    PackProseOut,
    StepsOut,
    example_facts,
    judge_messages,
    pack_messages,
    prose_texts,
    retry_message,
    steps_messages,
    steps_texts,
    strict_schema,
)
from pipeline.sources import Sources, load, write_pack

SAMPLES = 3  # fresh samples after the targeted retry
JUDGES = 3  # judge samples when the first judge flags something; the majority decides
JUDGE_ATTEMPTS = 3  # calls per judge sample before the judge counts as unavailable
CONCURRENCY = 8  # LLM calls in flight at once, across all topics
LIMITS = {"summary": 200, "idea": 2000, "why_it_works": 2000, "title": 200, "text": 600}
PACK_AI_FIELDS = ["summary", "idea", "why_it_works", "questions", "outline"]
STEP_AI_FIELDS = ["why", "another_way", "visual"]


@dataclass
class Stats:
    calls: Counter[str] = field(default_factory=Counter)
    failed_calls: int = 0
    prompt_tokens: int = 0
    cached_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    retries: int = 0
    samples: int = 0
    judge_flags: Counter[str] = field(default_factory=Counter)
    dropped: list[str] = field(default_factory=list)


Failing = dict[str, list[str]]  # path -> findings


class PackError(Exception):
    """A built pack fails the deterministic checks: a bug in this file, not in the LLM output."""


def score(failing: Failing) -> float:
    """How bad a candidate is: a whole-unit failure is worse than any number of failing parts."""
    return float("inf") if "*" in failing else len(failing)


def judged_key(name: str, texts: dict[str, str]) -> str:
    """The `texts` key a judge's field name is about: the longest key it starts with
    (`questions[0].answer` -> `questions[0]`), else the whole unit `*`."""
    keys = [k for k in texts if name == k or (name.startswith(k) and not name[len(k)].isalnum())]
    return max(keys, key=len) if keys else "*"


def skipped(key: str, failing: Failing) -> bool:
    """`key` (such as `outline[2]`) is already failing, on its own or as part of its list."""
    return key in failing or key.split("[")[0] in failing


class Runner:
    def __init__(self, llm: LLM, stats: Stats, concurrency: int = CONCURRENCY) -> None:
        self.llm = llm
        self.stats = stats
        self.slots = asyncio.Semaphore(concurrency)

    async def call[T: BaseModel](
        self, task: Task, messages: list[dict[str, object]], out: type[T]
    ) -> T | None:
        self.stats.calls[task] += 1
        async with self.slots:
            result = await self.llm.structured(
                task=task,
                messages=messages,
                schema_name=out.__name__,
                schema=strict_schema(out),
                output=out,
            )
        usage = result.usage
        self.stats.prompt_tokens += usage.prompt_tokens
        self.stats.cached_tokens += usage.cached_tokens
        self.stats.completion_tokens += usage.completion_tokens
        self.stats.reasoning_tokens += usage.reasoning_tokens
        if result.value is None:
            self.stats.failed_calls += 1
        value: T | None = result.value
        return value

    async def judge(self, lesson: str, facts: str, texts: dict[str, str]) -> Failing | None:
        """Fields with an unsupported claim, by majority when the first judge flags any. None
        when the judge gives no verdict, even after retrying: then nothing may ship."""
        if not texts:
            return {}

        async def once() -> Failing | None:
            for _ in range(JUDGE_ATTEMPTS):
                out = await self.call("judge", judge_messages(lesson, facts, texts), JudgeOut)
                if out is not None:
                    break
            else:
                return None
            flagged: Failing = {}
            for claim in out.claims:
                if claim.verdict == "unsupported":
                    key = judged_key(claim.field, texts)
                    flagged.setdefault(key, []).append(f"judge: {claim.claim} ({claim.reason})")
            return flagged

        first = await once()
        if not first:
            return first
        more = await asyncio.gather(*(once() for _ in range(JUDGES - 1)))
        runs = [first, *more]
        if any(run is None for run in runs):
            return None
        votes: Counter[str] = Counter()
        reasons: Failing = {}
        for run in runs:
            for key, why in (run or {}).items():
                votes[key] += 1
                reasons.setdefault(key, why)
        majority = {k: reasons[k] for k, n in votes.items() if n * 2 > len(runs)}
        for key in majority:
            self.stats.judge_flags[key] += 1
        return majority

    async def unit[T: BaseModel](
        self,
        messages: list[dict[str, object]],
        out: type[T],
        check: Callable[[T], Failing],
        verdict: Callable[[T, Failing], Awaitable[Failing | None]],
    ) -> tuple[T | None, Failing]:
        """Sample, check, retry with the findings, then vote over fresh samples.

        Every candidate is judged on the parts that passed the deterministic checks, so no
        part ships unjudged. If the judge gives no verdict, the unit stops: the best judged
        candidate so far is returned, or nothing."""
        best: tuple[T | None, Failing] = (None, {"*": ["no output"]})

        async def evaluate(candidate: T | None) -> Failing | None:
            if candidate is None:
                return {"*": ["no output"]}
            failing = check(candidate)
            if "*" in failing:
                return failing
            judged = await verdict(candidate, failing)
            if judged is None:
                return None
            return {**judged, **failing}

        def keep(candidate: T | None, failing: Failing) -> None:
            nonlocal best
            if candidate is not None and (best[0] is None or score(failing) < score(best[1])):
                best = (candidate, failing)

        def no_judge() -> tuple[T | None, Failing]:
            return best if best[0] is not None else (None, {"*": ["the judge gave no verdict"]})

        first = await self.call("generate", messages, out)
        failing = await evaluate(first)
        if failing is None:
            return no_judge()
        keep(first, failing)
        if not failing:
            return first, {}
        if first is not None:
            self.stats.retries += 1
            findings = [f"{path}: {f}" for path, fs in failing.items() for f in fs]
            again: list[dict[str, object]] = [
                *messages,
                {"role": "assistant", "content": first.model_dump_json()},
                retry_message(findings),
            ]
            second = await self.call("generate", again, out)
            failing = await evaluate(second)
            if failing is None:
                return no_judge()
            keep(second, failing)
            if not failing:
                return second, {}
        for _ in range(SAMPLES):
            self.stats.samples += 1
            sample = await self.call("generate", messages, out)
            failing = await evaluate(sample)
            if failing is None:
                return no_judge()
            keep(sample, failing)
            if not failing:
                return sample, {}
        return best


def _length(path: str, text: str, limit: int) -> list[Finding]:
    if not text.strip():
        return [Finding(path, "empty", "")]
    if len(text) > limit:
        return [Finding(path, "too_long", f"{len(text)} > {limit} characters")]
    return []


def _group(findings: list[Finding], depth: int = 1) -> Failing:
    """Findings by the unit path they drop: `questions[2].answer` -> `questions[2]`."""
    out: Failing = {}
    for f in findings:
        key = ".".join(f.path.split(".")[:depth])
        out.setdefault(key, []).append(f"{f.check}: {f.detail}")
    return out


def check_prose(c: PackProseOut, known: Sequence[Known]) -> Failing:
    """The checks pack_findings runs on the pack text, with the same worked solutions."""
    found: list[Finding] = []
    for name in ("summary", "idea", "why_it_works"):
        text = getattr(c, name)
        found += _length(name, text, LIMITS[name]) + prose(name, text, known=known)
    for i, q in enumerate(c.questions):
        found += _length(f"questions[{i}].question", q.question, LIMITS["title"])
        found += _length(f"questions[{i}].answer", q.answer, LIMITS["text"])
        found += prose(f"questions[{i}].question", q.question, known=known)
        found += prose(f"questions[{i}].answer", q.answer, known=known)
    for i, o in enumerate(c.outline):
        found += _length(f"outline[{i}].title", o.title, LIMITS["title"])
        found += _length(f"outline[{i}].activity", o.activity, LIMITS["text"])
        found += prose(f"outline[{i}].activity", o.activity, known=known)
        if not 1 <= o.minutes <= 60:
            found.append(Finding(f"outline[{i}]", "minutes", str(o.minutes)))
    if not 4 <= len(c.questions) <= 6:
        found.append(Finding("questions", "count", f"{len(c.questions)} questions, want 4-6"))
    if not 4 <= len(c.outline) <= 6 or sum(o.minutes for o in c.outline) > 60:
        found.append(Finding("outline", "shape", "want 4-6 parts and at most 60 minutes"))
    return _group(found)


def check_steps_out(c: StepsOut, example: WorkedExample) -> Failing:
    """The checks example_findings runs on the explanations, with the example's solution."""
    known = solutions(example.problem)
    if len(c.steps) != len(example.steps):
        return {"*": [f"{len(c.steps)} explanations for {len(example.steps)} lines"]}
    found: list[Finding] = []
    for i, s in enumerate(c.steps):
        path = f"steps[{i}]"
        found += _length(f"{path}.why", s.why, LIMITS["text"])
        found += _length(f"{path}.another_way", s.another_way, LIMITS["text"])
        found += _length(f"{path}.visual", s.visual, LIMITS["summary"])
        ex = StepExplanations.model_construct(why=s.why, another_way=s.another_way, visual=s.visual)
        found += explanation_findings(path, ex, step_numbers(example, i), known)
    return _group(found)


def skeleton(topic: TopicId, steps_for: StepsFor) -> list[WorkedExample]:
    """The worked examples with sympy's steps and answers, before any prose."""
    examples = []
    for problem in EXAMPLES[topic]:
        mp = math_problem(problem)
        steps = steps_for(mp)
        if len(steps) < 3:
            raise PackError(f"{topic}: no real worked steps for {problem.expr}")
        examples.append(
            WorkedExample(
                problem=problem,
                prompt=prompt_for(problem),
                steps=[ExplainedStep(left=s.left, right=s.right, op=s.op) for s in steps],
                answer=solve(mp).answer_text,
            )
        )
    return examples


async def build_pack(
    sources: Sources, runner: Runner, steps_for: StepsFor, model: str, lang: str = "en"
) -> Pack:
    topic, lesson = sources.topic, sources.lesson
    examples = skeleton(topic, steps_for)
    facts = "\n\n".join(example_facts(e) for e in examples)

    async def pack_verdict(c: PackProseOut, failing: Failing) -> Failing | None:
        texts = {k: v for k, v in prose_texts(c).items() if not skipped(k, failing)}
        return await runner.judge(lesson, facts, texts)

    async def explain(example: WorkedExample) -> tuple[StepsOut | None, Failing]:
        async def verdict(c: StepsOut, failing: Failing) -> Failing | None:
            texts = {k: v for k, v in steps_texts(c.steps).items() if not skipped(k, failing)}
            return await runner.judge(lesson, example_facts(example), texts)

        return await runner.unit(
            steps_messages(lesson, example),
            StepsOut,
            lambda c: check_steps_out(c, example),
            verdict,
        )

    prose_job = runner.unit(
        pack_messages(lesson, examples),
        PackProseOut,
        lambda c: check_prose(c, solutions(*EXAMPLES[topic])),
        pack_verdict,
    )
    (prose_out, prose_failing), explained = await asyncio.gather(
        prose_job, asyncio.gather(*(explain(e) for e in examples))
    )

    whole = "*" in prose_failing or prose_out is None

    def keep(name: str) -> str | None:
        if whole or name in prose_failing or prose_out is None:
            return None
        text: str = getattr(prose_out, name)
        return text.strip()

    questions: list[StudentQuestion] = []
    outline: list[OutlineStep] = []
    dropped_questions: list[str] = []
    if not whole and prose_out is not None and "questions" not in prose_failing:
        for i, q in enumerate(prose_out.questions):
            if f"questions[{i}]" in prose_failing:
                dropped_questions.append(f"questions[{i}]")
            else:
                questions.append(
                    StudentQuestion(question=q.question.strip(), answer=q.answer.strip())
                )
    if (
        not whole
        and prose_out is not None
        and not any(k.split("[")[0] == "outline" for k in prose_failing)  # all parts or none
    ):
        outline = [
            OutlineStep(minutes=o.minutes, title=o.title.strip(), activity=o.activity.strip())
            for o in prose_out.outline
        ]

    worked = []
    for example, (out, failing) in zip(examples, explained, strict=True):
        steps = []
        for i, step in enumerate(example.steps):
            explanation = None
            if out is not None and "*" not in failing and f"steps[{i}]" not in failing:
                s = out.steps[i]
                explanation = StepExplanations(
                    why=s.why.strip(),
                    another_way=s.another_way.strip(),
                    visual=s.visual.strip(),
                    ai_generated=STEP_AI_FIELDS,
                )
            steps.append(step.model_copy(update={"explanations": explanation}))
        worked.append(example.model_copy(update={"steps": steps}))

    meta = sources.meta
    pack = Pack(
        topic=topic,
        lang=lang,
        title=meta.title,
        grades=meta.grades,
        summary=keep("summary"),
        idea=keep("idea"),
        why_it_works=keep("why_it_works"),
        prerequisites=meta.prerequisites,
        worked_examples=worked,
        misconceptions=sources.misconceptions.misconceptions,
        questions=questions,
        outline=outline,
        akelius_lessons=meta.akelius_lessons,
        practice=sources.practice.items,
        ai_generated=PACK_AI_FIELDS,
        unavailable=[],
        source_hash=sources.hash,
        model=model,
    )
    unavailable = sorted(dropped_paths(pack) | set(dropped_questions))
    pack = pack.model_copy(update={"unavailable": unavailable})
    runner.stats.dropped += [f"{topic}: {p}" for p in pack.unavailable]
    return pack


async def generate(
    topics: list[TopicId],
    llm: LLM,
    model: str,
    steps_for: StepsFor = worked_steps,
    on_pack: Callable[[Pack], object] = lambda pack: None,
) -> tuple[list[Pack], Stats]:
    """Builds the topics concurrently. Each pack goes to `on_pack` as soon as it passes the
    checks, so one failing topic doesn't lose the others' paid output."""
    stats = Stats()
    runner = Runner(llm, stats)

    async def one(topic: TopicId) -> Pack:
        sources = load(topic)
        pack = await build_pack(sources, runner, steps_for, model)
        problems = pack_findings(pack, sources, steps_for)
        if problems:  # never write such a pack
            raise PackError("\n".join(f"{topic}: {p}" for p in problems))
        on_pack(pack)
        return pack

    results = await asyncio.gather(*(one(t) for t in topics), return_exceptions=True)
    errors = [r for r in results if isinstance(r, BaseException)]
    if errors:
        raise PackError("\n".join(str(e) for e in errors)) from errors[0]
    return [r for r in results if isinstance(r, Pack)], stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--topic", default="all", choices=["all", *TOPIC_IDS])
    parser.add_argument("--lang", default="en", choices=["en"])
    parser.add_argument("--report", default="evals/verify-report.md")
    args = parser.parse_args()
    topics: list[TopicId] = list(TOPIC_IDS) if args.topic == "all" else [args.topic]
    llm, model = offline_llm()

    def write(pack: Pack) -> None:
        print(f"wrote {write_pack(pack)} (unavailable: {pack.unavailable or 'none'})")

    try:
        packs, stats = asyncio.run(generate(topics, llm, model, on_pack=write))
    except PackError as err:
        raise SystemExit(str(err)) from err
    from pipeline.verify import write_report

    judged: dict[TopicId, dict[str, list[str]]] = {p.topic: {} for p in packs}
    write_report(Path(args.report), args.lang, stats=stats, model=model, judged=judged)
    print(json.dumps({"calls": dict(stats.calls), "dropped": stats.dropped}))


if __name__ == "__main__":
    main()
