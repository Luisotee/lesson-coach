"""Request and response models of the API: the contract with the frontend.

Math is plain sympy-parsable text in responses (`2*x + 6 = 10`). In requests it may be plain
text or LaTeX from MathLive. `GET /api/topics/{id}` returns the `Pack` model itself
(`app.content.schema`), so the pack's fields are defined in one place only.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.content.schema import Problem as PackProblem
from app.content.schema import TopicId
from app.math.canonical import Verdict
from app.math.problems import Kind

Lang = Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")]
PlainMath = Annotated[str, StringConstraints(max_length=200)]
Op = Annotated[str, StringConstraints(max_length=30)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Inputs


class MathIn(Model):
    """Exactly one of `text` (plain, e.g. `1/2 + 1/3`) or `latex` (from MathLive)."""

    text: PlainMath | None = None
    latex: Annotated[str, StringConstraints(max_length=400)] | None = None

    @model_validator(mode="after")
    def _one_form(self) -> Self:
        if (self.text is None) == (self.latex is None):
            raise ValueError("give exactly one of text or latex")
        return self


class ProblemIn(MathIn):
    """A problem as typed. Without `kind`, an equation is solved and anything else is
    evaluated. Pack problems are sent as `{kind, text: expr}`."""

    kind: Kind | None = None


class LineIn(Model):
    """A line of working: `{left, right?, op?}` in plain text (the step contract), or one
    field of math `{text | latex, op?}` that may contain `=`. `op` is the margin operation
    on this line (`-6`, `/2`), which gives the next line."""

    left: PlainMath | None = None
    right: PlainMath = ""
    op: Op = ""
    text: PlainMath | None = None
    latex: Annotated[str, StringConstraints(max_length=400)] | None = None

    @model_validator(mode="after")
    def _one_form(self) -> Self:
        forms = [self.left is not None, self.text is not None, self.latex is not None]
        if sum(forms) != 1:
            raise ValueError("give exactly one of left, text or latex")
        if self.left is None and self.right:
            raise ValueError("right goes with left")
        return self


Working = Annotated[list[LineIn], Field(max_length=20)]


class MistakeRequest(Model):
    problem: ProblemIn
    answer: MathIn
    working: Working = []
    topic: TopicId | None = None
    lang: Lang = "en"


class CheckWorkingRequest(Model):
    problem: ProblemIn | None = None
    lines: Annotated[list[LineIn], Field(min_length=1, max_length=20)]


# Outputs


class StepOut(Model):
    left: str
    right: str = ""
    op: str = ""


class WorkingLineOut(Model):
    """A line the student sent, normalised (`2*x = 4` as left `2*x`, right `4`), in the order
    sent, so `first_bad_line.index` points into this list. A line that can't be read comes
    back as sent in `left`, with `right` and `op` null."""

    left: str
    right: str | None
    op: str | None


class BadLineOut(Model):
    """The first line (0-based, in the order sent) that doesn't follow from the one before."""

    index: int
    reason: Literal["unparsable", "false_equality", "not_equivalent", "unsupported"]


class ProblemOut(Model):
    kind: Kind
    expr: str


class MisconceptionOut(Model):
    """A misconception card. `id` is "other" when the AI found one the pack doesn't list;
    then `belief` and `why_it_feels_right` are null and `explanation` says what it is."""

    id: str
    belief: str | None = None
    why_it_feels_right: str | None = None


class WhatToSayOut(Model):
    probe: str
    nudge: str
    tell: str


class TryNextOut(Model):
    problem: PackProblem
    prompt: str


class Diagnosis(Model):
    """Why the student probably wrote this, and what the teacher could say.

    `source` is "rule" when a sympy rule reproduces the answer exactly (`rule_checked`);
    then the misconception comes from the pack's card, and `what_to_say` is the card's moves
    rephrased by one AI call for this problem (numbers checked like any AI text). When that
    call is unavailable, abstains or fails the check, `what_to_say` is the card's own moves,
    written for the card's example problem, and `say_example` names that problem. `lang` is
    the language of `explanation`, `margin_note` and `what_to_say`; `cards_lang` that of
    `misconceptions` and `try_next` (the pack served, which falls back to English).
    """

    source: Literal["rule", "ai"]
    rule_checked: bool
    misconceptions: list[MisconceptionOut]
    explanation: str
    margin_note: str | None
    what_to_say: WhatToSayOut
    say_example: PackProblem | None = None
    try_next: TryNextOut | None
    lang: str
    cards_lang: str | None
    machine_translated: bool


MistakeStatus = Literal["correct", "not_simplified", "diagnosed", "slip", "unclear", "out_of_scope"]
AbstainReason = Literal[
    "problem_unreadable",  # the problem can't be read
    "answer_unreadable",  # the student's answer can't be read
    "unsupported",  # math outside what the coach handles (non-linear, too large...)
    "timeout",  # the math took longer than the limit
    "math_error",  # the math engine failed unexpectedly
    "ai_unavailable",  # no AI reply (no credentials, network, invalid reply)
    "ai_unclear",  # the AI found one answer not enough to tell
    "ai_out_of_scope",  # the AI found the input isn't a grade 6-9 problem and answer
    "ai_unverified_math",  # the AI's text had math sympy didn't give it, so it isn't shown
]


class MistakeResult(Model):
    """`correct` and `not_simplified` mean the student is right. `diagnosed` and `slip` come
    with a diagnosis. `unclear` and `out_of_scope` are abstains: `reason` says why, and any
    diagnosis is only a suggestion of what to ask."""

    status: MistakeStatus
    reason: AbstainReason | None = None
    problem: ProblemOut | None = None
    student_answer: str | None = None
    correct_answer: str | None = None
    verdict: Verdict | None = None
    worked_solution: list[StepOut] = []
    working: list[WorkingLineOut] = []
    first_bad_line: BadLineOut | None = None
    diagnosis: Diagnosis | None = None


class TopicOut(Model):
    """A topic card. `lang` is the pack served (English when `lang` has none); `langs` are
    the languages it exists in. `grades` and `summary` are empty until T5 adds them."""

    id: str
    title: str
    lang: str
    langs: list[str]
    machine_translated: bool
    prerequisites: list[str]
    grades: list[int] = []
    summary: str | None = None


class TranscribedLine(Model):
    """`uncertain` when the model wasn't sure (confidence < 0.7) or our parser can't read
    the line: the confirm screen highlights it."""

    left: str
    right: str
    op: str
    confidence: float
    uncertain: bool


class TranscribeResult(Model):
    status: Literal["ok", "unclear"]
    reason: Literal["no_math", "ai_unavailable"] | None = None
    lines: list[TranscribedLine] = []


class CheckWorkingResult(Model):
    """`final` grades the last line against the problem when every line follows."""

    status: Literal["all_follow", "line_doesnt_follow", "unclear", "out_of_scope"]
    reason: AbstainReason | None = None
    lines: list[WorkingLineOut] = []
    first_bad_line: BadLineOut | None = None
    final: Verdict | None = None
