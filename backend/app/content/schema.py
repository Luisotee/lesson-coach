"""Draft pack schema (PLAN, "Pack schema").

These models are structural: shapes, enums, counts and lengths. The math checks
(every expression parses, every answer is sympy's answer) live in
`tests/test_content.py` for now and move to `pipeline/verify.py` in T5.

Math is always plain sympy-parsable text such as `2*x + 6 = 10`, never LaTeX.
Prose may carry inline math in backticks, and each backtick span must parse.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal, Self, get_args

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.math import RULES

TopicId = Literal["negative-numbers", "fractions", "linear-equations"]
TOPIC_IDS: tuple[TopicId, ...] = get_args(TopicId)

# Misconception rule ids, keyed by topic, from T1's rule registry.
RULE_IDS: dict[TopicId, frozenset[str]] = {t: frozenset(RULES.get(t, {})) for t in TOPIC_IDS}

Id = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]*$", max_length=64)]
Math = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
OptMath = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Op = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]
Long = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Url = Annotated[str, StringConstraints(pattern=r"^https://\S+$", max_length=300)]
Sha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]


NUMBER = re.compile(r"\d+(?:\.\d+)?")


def check_prompt(prompt: str, expr: str) -> None:
    """A prompt is an instruction ("Solve:"); any number it mentions must be in `expr`, so a
    prompt can't carry stale or translated math."""
    stray = set(NUMBER.findall(prompt)) - set(NUMBER.findall(expr))
    if stray:
        raise ValueError(f"prompt numbers not in the problem: {sorted(stray)}")


def unique_ids(kind: str, ids: list[str]) -> None:
    if len(set(ids)) != len(ids):
        raise ValueError(f"{kind} ids must be unique")


def check_rules(topic: TopicId, misconceptions: list[Misconception]) -> None:
    for m in misconceptions:
        if m.rule_sympy is not None and m.rule_sympy not in RULE_IDS[topic]:
            raise ValueError(f"unknown rule id for {topic}: {m.rule_sympy}")


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AiMarked(Model):
    """A model whose `ai_generated` lists the names of its own fields that AI wrote."""

    ai_generated: list[str] = []

    @model_validator(mode="after")
    def _ai_fields(self) -> Self:
        unknown = set(self.ai_generated) - set(type(self).model_fields)
        if unknown:
            raise ValueError(f"ai_generated names unknown fields: {sorted(unknown)}")
        return self


class Problem(Model):
    """A math task. `expr` is sympy-parsable; a `solve` problem has exactly one `=`."""

    kind: Literal["evaluate", "simplify", "solve"]
    expr: Math

    @model_validator(mode="after")
    def _equals_sign(self) -> Self:
        has_one = self.expr.count("=") == 1
        if (self.kind == "solve") != has_one:
            raise ValueError("a solve problem has exactly one '='; other kinds have none")
        return self


class Step(Model):
    """One written line. `op` is the margin operation applied to this line to get the next
    (`3*x + 5 = 20 | -5`), empty on the last line. `right` is empty for an expression step."""

    left: Math
    right: OptMath = ""
    op: Op = ""


class StepExplanations(AiMarked):
    """The three explanation modes of a step. `visual` is a one-sentence caption: the frontend
    draws the picture (balance scale, bar model, counters) from the step's own math."""

    why: Text
    another_way: Text
    visual: Short


class ExplainedStep(Step):
    explanations: StepExplanations | None = None


class WorkedExample(AiMarked):
    problem: Problem
    prompt: Short
    steps: list[ExplainedStep] = Field(min_length=2, max_length=12)
    answer: Math

    @model_validator(mode="after")
    def _prompt(self) -> Self:
        check_prompt(self.prompt, self.problem.expr)
        return self


class WhatToSay(Model):
    probe: Text
    nudge: Text
    tell: Text


class CheckQuestion(Model):
    problem: Problem
    prompt: Short
    answer: Math

    @model_validator(mode="after")
    def _prompt(self) -> Self:
        check_prompt(self.prompt, self.problem.expr)
        return self


class Misconception(AiMarked):
    id: Id
    belief: Text
    rule_sympy: Id | None = None
    example_problem: Problem
    example_wrong_answer: Math
    why_it_feels_right: Text
    what_to_say: WhatToSay
    check_question: CheckQuestion
    source_quote: Text

    @model_validator(mode="after")
    def _rule_matches_id(self) -> Self:
        if self.rule_sympy is not None and self.rule_sympy != self.id:
            raise ValueError("a misconception linked to a rule uses the rule id as its id")
        return self


class MisconceptionSet(Model):
    topic: TopicId
    license: Literal["CC-BY-4.0"]
    misconceptions: list[Misconception] = Field(min_length=4, max_length=6)

    @model_validator(mode="after")
    def _ids(self) -> Self:
        unique_ids("misconception", [m.id for m in self.misconceptions])
        check_rules(self.topic, self.misconceptions)
        return self


HintRung = Literal["goal", "information", "computation", "answer"]
HINT_RUNGS: tuple[HintRung, ...] = get_args(HintRung)


class Hint(Model):
    rung: HintRung
    text: Text


class PracticeSource(Model):
    repo: Url
    commit: Sha
    path: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    url: Url
    oer: Short
    license: Literal["CC-BY-4.0"]
    changes: Text


class PracticeItem(AiMarked):
    id: Id
    problem: Problem
    prompt: Short
    hints: list[Hint] = Field(min_length=4, max_length=4)
    answer: Math
    source: PracticeSource
    license: Literal["CC-BY-4.0"]

    @model_validator(mode="after")
    def _rungs(self) -> Self:
        if tuple(h.rung for h in self.hints) != HINT_RUNGS:
            raise ValueError(f"hints must be the rungs {HINT_RUNGS} in order")
        check_prompt(self.prompt, self.problem.expr)
        return self


class PracticeSet(Model):
    topic: TopicId
    items: list[PracticeItem] = Field(min_length=8, max_length=8)

    @model_validator(mode="after")
    def _ids(self) -> Self:
        unique_ids("practice item", [i.id for i in self.items])
        return self


class AkeliusLesson(Model):
    url: Annotated[
        str,
        StringConstraints(
            pattern=r"^https://akelius\.education/math/[a-z]{2,3}(-[A-Za-z]{2,4})?/lesson/\d+$"
        ),
    ]
    title: Short
    grade: int = Field(ge=1, le=12)


class LessonMeta(Model):
    """YAML front matter of `content/source/<topic>.md`."""

    id: TopicId
    title: Short
    grades: list[int] = Field(min_length=1)
    prerequisites: list[TopicId] = []
    akelius_lessons: list[AkeliusLesson] = Field(min_length=1)
    license: Literal["CC-BY-4.0"]
    authors: Short


class StudentQuestion(Model):
    question: Short
    answer: Text


class OutlineStep(Model):
    minutes: int = Field(ge=1, le=60)
    title: Short
    activity: Text


class Pack(AiMarked):
    """A generated pack (`content/generated/<lang>/<topic>.json`), built by pipeline/generate.py
    and checked by pipeline/verify.py. A prose field that failed verification is `None` (shown
    as "unavailable") and its path is listed in `unavailable`; it is never shipped unverified."""

    topic: TopicId
    lang: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")]
    title: Short
    grades: list[int] = Field(min_length=1)
    summary: Short | None
    idea: Long | None
    why_it_works: Long | None
    prerequisites: list[TopicId] = []
    worked_examples: list[WorkedExample] = Field(min_length=3, max_length=3)
    misconceptions: list[Misconception] = Field(min_length=4, max_length=6)
    questions: list[StudentQuestion] = []
    outline: list[OutlineStep] = []
    akelius_lessons: list[AkeliusLesson] = Field(min_length=1)
    practice: list[PracticeItem] = []
    machine_translated: bool = False
    unavailable: list[str] = []
    source_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    model: Short

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        unique_ids("misconception", [m.id for m in self.misconceptions])
        unique_ids("practice item", [i.id for i in self.practice])
        check_rules(self.topic, self.misconceptions)
        if self.topic in self.prerequisites:
            raise ValueError("a topic is not its own prerequisite")
        if sum(o.minutes for o in self.outline) > 60:
            raise ValueError("the lesson outline is longer than 60 minutes")
        return self


# Eval cases (`evals/mistakes.yaml`). T10 may extend them.


class Expected(Model):
    classification: Literal["correct", "equivalent_not_simplified", "wrong"]
    status: Literal["diagnosed", "slip", "unclear", "out_of_scope"] | None = None
    misconception_id: Id | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.classification != "wrong":
            if self.status is not None or self.misconception_id is not None:
                raise ValueError("a correct or equivalent answer has no status or misconception")
        elif self.status is None:
            raise ValueError("a wrong answer needs a status")
        elif (self.status == "diagnosed") != (self.misconception_id is not None):
            raise ValueError("misconception_id is set exactly when the status is diagnosed")
        return self


class CaseSource(Model):
    dataset: Literal["MaE", "ours"]
    repo: Url | None = None
    commit: Sha | None = None
    misconception: Annotated[str, StringConstraints(pattern=r"^MaE\d\d$")] | None = None
    example: int | None = None
    license: Literal["MIT", "CC-BY-4.0"]
    changes: Text

    @model_validator(mode="after")
    def _attribution(self) -> Self:
        mae = (self.repo, self.commit, self.misconception, self.example)
        if self.dataset == "MaE":
            if None in mae or self.license != "MIT":
                raise ValueError("an MaE row needs repo, commit, misconception, example and MIT")
        elif any(v is not None for v in mae) or self.license != "CC-BY-4.0":
            raise ValueError("our own rows are CC BY 4.0 and carry no MaE fields")
        return self


class MistakeCase(Model):
    id: Id
    topic: TopicId
    problem: Problem
    student_answer: Math
    student_working: list[Step] = []
    expected: Expected
    source: CaseSource


class MistakeEvalSet(Model):
    cases: list[MistakeCase] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids(self) -> Self:
        ids = [c.id for c in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("case ids must be unique")
        return self
