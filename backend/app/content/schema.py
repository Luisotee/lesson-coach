"""Draft pack schema (PLAN, "Pack schema").

These models are structural: shapes, enums, counts and lengths. The math checks
(every expression parses, every answer is sympy's answer) live in
`tests/test_content.py` for now and move to `pipeline/verify.py` in T5.

Math is always plain sympy-parsable text such as `2*x + 6 = 10`, never LaTeX.
Prose may carry inline math in backticks, and each backtick span must parse.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

TopicId = Literal["negative-numbers", "fractions", "linear-equations"]
TOPIC_IDS: tuple[TopicId, ...] = ("negative-numbers", "fractions", "linear-equations")

# Misconception rule ids agreed with T1 (backend/app/math/), keyed by topic.
RULE_IDS: dict[TopicId, frozenset[str]] = {
    "negative-numbers": frozenset(
        {
            "minus_negative_stays_minus",
            "neg_times_neg_is_neg",
            "add_magnitudes_keep_sign",
            "subtract_smaller_from_larger",
        }
    ),
    "fractions": frozenset(
        {
            "add_tops_and_bottoms",
            "multiply_both_by_whole",
            "flip_first_when_dividing",
            "cancel_across_addition",
        }
    ),
    "linear-equations": frozenset(
        {
            "sign_not_changed",
            "divide_one_term",
            "subtract_instead_of_divide",
            "wrong_inverse_order",
        }
    ),
}

Id = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]*$", max_length=64)]
Math = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
OptMath = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Op = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]
Long = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Url = Annotated[str, StringConstraints(pattern=r"^https://\S+$", max_length=300)]
Sha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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


class StepExplanations(Model):
    why: Text
    another_way: Text
    visual: Text


class ExplainedStep(Step):
    explanations: StepExplanations | None = None


class WorkedExample(Model):
    problem: Problem
    steps: list[ExplainedStep] = Field(min_length=2, max_length=12)
    answer: Math
    ai_generated: list[str] = []


class WhatToSay(Model):
    probe: Text
    nudge: Text
    tell: Text


class CheckQuestion(Model):
    problem: Problem
    prompt: Short
    answer: Math


class Misconception(Model):
    id: Id
    belief: Text
    rule_sympy: Id | None = None
    example_problem: Problem
    example_wrong_answer: Math
    why_it_feels_right: Text
    what_to_say: WhatToSay
    check_question: CheckQuestion
    source_quote: Text
    ai_generated: list[str] = []

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
        ids = [m.id for m in self.misconceptions]
        if len(set(ids)) != len(ids):
            raise ValueError("misconception ids must be unique")
        for m in self.misconceptions:
            if m.rule_sympy is not None and m.rule_sympy not in RULE_IDS[self.topic]:
                raise ValueError(f"unknown rule id for {self.topic}: {m.rule_sympy}")
        return self


HINT_RUNGS = ("goal", "information", "computation", "answer")


class Hint(Model):
    rung: Literal["goal", "information", "computation", "answer"]
    text: Text


class PracticeSource(Model):
    repo: Url
    commit: Sha
    path: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    url: Url
    oer: Short
    license: Literal["CC-BY-4.0"]
    changes: Text


class PracticeItem(Model):
    id: Id
    problem: Problem
    prompt: Short
    hints: list[Hint] = Field(min_length=4, max_length=4)
    answer: Math
    source: PracticeSource
    license: Literal["CC-BY-4.0"]
    ai_generated: list[str] = []

    @model_validator(mode="after")
    def _rungs(self) -> Self:
        if tuple(h.rung for h in self.hints) != HINT_RUNGS:
            raise ValueError(f"hints must be the rungs {HINT_RUNGS} in order")
        return self


class PracticeSet(Model):
    topic: TopicId
    items: list[PracticeItem] = Field(min_length=8, max_length=8)

    @model_validator(mode="after")
    def _ids(self) -> Self:
        ids = [i.id for i in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("practice item ids must be unique")
        return self


class AkeliusLesson(Model):
    url: Annotated[str, StringConstraints(pattern=r"^https://akelius\.education/math/en/lesson/\d+$")]
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


class Pack(Model):
    """Draft of a generated pack (`content/generated/<lang>/<topic>.json`). T5 owns it."""

    topic: TopicId
    lang: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")]
    title: Short
    idea: Long
    why_it_works: Long
    prerequisites: list[TopicId] = []
    worked_examples: list[WorkedExample] = Field(min_length=3, max_length=3)
    misconceptions: list[Misconception] = Field(min_length=4, max_length=6)
    questions: list[StudentQuestion] = []
    outline: list[OutlineStep] = []
    akelius_lessons: list[AkeliusLesson] = Field(min_length=1)
    practice: list[PracticeItem] = []
    machine_translated: bool = False


# Eval cases (`evals/mistakes.yaml`). T10 may extend them.


class Expected(Model):
    classification: Literal["correct", "equivalent_not_simplified", "wrong"]
    status: Literal["diagnosed", "slip", "unclear", "out_of_scope"] | None = None
    misconception_id: Id | None = None


class CaseSource(Model):
    dataset: Literal["MaE", "ours"]
    repo: Url | None = None
    commit: Sha | None = None
    misconception: Annotated[str, StringConstraints(pattern=r"^MaE\d\d$")] | None = None
    example: int | None = None
    license: Literal["MIT", "CC-BY-4.0"]
    changes: Text


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
