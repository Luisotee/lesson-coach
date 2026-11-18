"""Builds a topic's pack: sympy writes the steps and answers, the LLM writes the prose.

    uv run --project backend python pipeline/generate.py --topic all --lang en

Each piece of LLM prose (the pack text, and each worked example's step explanations) goes
through the same loop: deterministic checks, then an LLM judge (a majority of 3 when it flags
anything); on failure one targeted retry that quotes the findings, then up to 3 fresh samples.
What still fails is dropped: its field is null and listed in `unavailable`. Misconceptions and
practice are copied from the source files, which are already written and tested.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from collections.abc import Awaitable, Callable
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
    dropped_paths,
    explanation_findings,
    math_problem,
    pack_findings,
    prose,
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
    retry_message,
    steps_messages,
    strict_schema,
)
from pipeline.sources import Sources, load, write_pack

SAMPLES = 3  # fresh samples after the targeted retry
JUDGES = 3  # judge samples when the first judge flags something; the majority decides
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


class Runner:
    def __init__(self, llm: LLM, stats: Stats) -> None:
        self.llm = llm
        self.stats = stats

    async def call[T: BaseModel](
        self, task: Task, messages: list[dict[str, object]], out: type[T]
    ) -> T | None:
        self.stats.calls[task] += 1
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

    async def judge(self, lesson: str, facts: str, texts: dict[str, str]) -> Failing:
        """Fields with an unsupported claim, by majority when the first judge flags any."""

        async def once() -> Failing | None:
            out = await self.call("judge", judge_messages(lesson, facts, texts), JudgeOut)
            if out is None:
                return None
            flagged: Failing = {}
            for claim in out.claims:
                if claim.verdict == "unsupported":
                    key = claim.field if claim.field in texts else "*"
                    flagged.setdefault(key, []).append(f"judge: {claim.claim} ({claim.reason})")
            return flagged

        first = await once()
        if first is None:
            return {"*": ["the judge gave no verdict"]}
        if not first:
            return {}
        runs = [first, *[r for r in await asyncio.gather(*(once() for _ in range(JUDGES - 1)))]]
        votes: Counter[str] = Counter()
        reasons: Failing = {}
        for run in runs:
            for key, why in (run or {"*": ["the judge gave no verdict"]}).items():
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
        verdict: Callable[[T], Awaitable[Failing]],
    ) -> tuple[T | None, Failing]:
        """Sample, check, retry with the findings, then vote over fresh samples."""
        best: tuple[T | None, Failing] = (None, {"*": ["no output"]})

        async def evaluate(candidate: T | None) -> Failing:
            if candidate is None:
                return {"*": ["no output"]}
            failing = check(candidate)
            if not failing:
                failing = await verdict(candidate)
            return failing

        def keep(candidate: T | None, failing: Failing) -> None:
            nonlocal best
            if candidate is not None and (best[0] is None or len(failing) < len(best[1])):
                best = (candidate, failing)

        first = await self.call("generate", messages, out)
        failing = await evaluate(first)
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
            keep(second, failing)
            if not failing:
                return second, {}
        for _ in range(SAMPLES):
            self.stats.samples += 1
            sample = await self.call("generate", messages, out)
            failing = await evaluate(sample)
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


def check_prose(c: PackProseOut) -> Failing:
    found: list[Finding] = []
    for name in ("summary", "idea", "why_it_works"):
        text = getattr(c, name)
        found += _length(name, text, LIMITS[name]) + prose(name, text)
    for i, q in enumerate(c.questions):
        found += _length(f"questions[{i}].question", q.question, LIMITS["title"])
        found += _length(f"questions[{i}].answer", q.answer, LIMITS["text"])
        found += prose(f"questions[{i}].question", q.question)
        found += prose(f"questions[{i}].answer", q.answer)
    for i, o in enumerate(c.outline):
        found += _length(f"outline[{i}].title", o.title, LIMITS["title"])
        found += _length(f"outline[{i}].activity", o.activity, LIMITS["text"])
        found += prose(f"outline[{i}].activity", o.activity)
        if not 1 <= o.minutes <= 60:
            found.append(Finding(f"outline[{i}]", "minutes", str(o.minutes)))
    if not 4 <= len(c.questions) <= 6:
        found.append(Finding("questions", "count", f"{len(c.questions)} questions, want 4-6"))
    if not 4 <= len(c.outline) <= 6 or sum(o.minutes for o in c.outline) > 60:
        found.append(Finding("outline", "shape", "want 4-6 parts and at most 60 minutes"))
    return _group(found)


def prose_texts(c: PackProseOut) -> dict[str, str]:
    texts = {"summary": c.summary, "idea": c.idea, "why_it_works": c.why_it_works}
    for i, q in enumerate(c.questions):
        texts[f"questions[{i}]"] = f"Q: {q.question}\nA: {q.answer}"
    for i, o in enumerate(c.outline):
        texts[f"outline[{i}]"] = f"{o.title} ({o.minutes} min): {o.activity}"
    return texts


def check_steps_out(c: StepsOut, example: WorkedExample) -> Failing:
    if len(c.steps) != len(example.steps):
        return {"*": [f"{len(c.steps)} explanations for {len(example.steps)} lines"]}
    found: list[Finding] = []
    for i, s in enumerate(c.steps):
        path = f"steps[{i}]"
        found += _length(f"{path}.why", s.why, LIMITS["text"])
        found += _length(f"{path}.another_way", s.another_way, LIMITS["text"])
        found += _length(f"{path}.visual", s.visual, LIMITS["summary"])
        ex = StepExplanations.model_construct(why=s.why, another_way=s.another_way, visual=s.visual)
        found += explanation_findings(path, ex, step_numbers(example, i))
    return _group(found)


def steps_texts(c: StepsOut) -> dict[str, str]:
    return {
        f"steps[{i}]": f"why: {s.why}\nanother way: {s.another_way}\npicture: {s.visual}"
        for i, s in enumerate(c.steps)
    }


def skeleton(topic: TopicId, steps_for: StepsFor) -> list[WorkedExample]:
    """The worked examples with sympy's steps and answers, before any prose."""
    examples = []
    for problem in EXAMPLES[topic]:
        mp = math_problem(problem)
        steps = steps_for(mp)
        if len(steps) < 3:
            raise SystemExit(f"{topic}: no real worked steps for {problem.expr}")
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

    async def pack_verdict(c: PackProseOut) -> Failing:
        return await runner.judge(lesson, facts, prose_texts(c))

    async def explain(example: WorkedExample) -> tuple[StepsOut | None, Failing]:
        async def verdict(c: StepsOut) -> Failing:
            return await runner.judge(lesson, example_facts(example), steps_texts(c))

        return await runner.unit(
            steps_messages(lesson, example),
            StepsOut,
            lambda c: check_steps_out(c, example),
            verdict,
        )

    prose_job = runner.unit(
        pack_messages(lesson, examples), PackProseOut, check_prose, pack_verdict
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
    if not whole and prose_out is not None:
        questions = [
            StudentQuestion(question=q.question.strip(), answer=q.answer.strip())
            for i, q in enumerate(prose_out.questions)
            if f"questions[{i}]" not in prose_failing and "questions" not in prose_failing
        ]
        if "outline" not in prose_failing and not any(
            k.startswith("outline[") for k in prose_failing
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
    pack = pack.model_copy(update={"unavailable": sorted(dropped_paths(pack))})
    runner.stats.dropped += [f"{topic}: {p}" for p in pack.unavailable]
    return pack


async def generate(
    topics: list[TopicId], llm: LLM, model: str, steps_for: StepsFor = worked_steps
) -> tuple[list[Pack], Stats]:
    stats = Stats()
    runner = Runner(llm, stats)
    packs = []
    for topic in topics:
        sources = load(topic)
        pack = await build_pack(sources, runner, steps_for, model)
        problems = pack_findings(pack, sources, steps_for)
        if problems:  # a bug in this file, not in the LLM output: never write such a pack
            raise SystemExit("\n".join(str(p) for p in problems))
        packs.append(pack)
    return packs, stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--topic", default="all", choices=["all", *TOPIC_IDS])
    parser.add_argument("--lang", default="en", choices=["en"])
    parser.add_argument("--report", default="evals/verify-report.md")
    args = parser.parse_args()
    topics: list[TopicId] = list(TOPIC_IDS) if args.topic == "all" else [args.topic]
    llm, model = offline_llm()
    packs, stats = asyncio.run(generate(topics, llm, model))
    for pack in packs:
        print(f"wrote {write_pack(pack)} (unavailable: {pack.unavailable or 'none'})")
    from pipeline.verify import write_report

    judged: dict[TopicId, dict[str, list[str]]] = {p.topic: {} for p in packs}
    write_report(Path(args.report), args.lang, stats=stats, model=model, judged=judged)
    print(json.dumps({"calls": dict(stats.calls), "dropped": stats.dropped}))


if __name__ == "__main__":
    main()
