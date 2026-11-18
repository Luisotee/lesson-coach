"""Turn API inputs into the math pipeline's plain data, and its findings into API outputs."""

from __future__ import annotations

from app.api.models import BadLineOut, LineIn, MathIn, StepOut
from app.math.pipeline import BadLine, LineText, MathText
from app.math.problems import Step


def math_text(value: MathIn) -> MathText:
    if value.latex is not None:
        return MathText(value.latex, "latex")
    assert value.text is not None
    return MathText(value.text, "text")


def line_text(line: LineIn) -> LineText:
    if line.left is not None:
        return LineText(left=line.left, right=line.right, op=line.op)
    if line.latex is not None:
        return LineText(op=line.op, math=MathText(line.latex, "latex"))
    assert line.text is not None
    return LineText(op=line.op, math=MathText(line.text, "text"))


def bad_line(found: BadLine | None) -> BadLineOut | None:
    if found is None:
        return None
    return BadLineOut.model_validate({"index": found.index, "reason": found.reason})


def steps_out(steps: list[Step]) -> list[StepOut]:
    return [StepOut(left=s.left, right=s.right, op=s.op) for s in steps]
