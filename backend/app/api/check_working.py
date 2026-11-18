"""`POST /api/check-working`: which line of the working first doesn't follow. sympy only."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.convert import bad_line, line_text, math_text, working_out
from app.api.models import CheckWorkingRequest, CheckWorkingResult
from app.math.pipeline import check_working
from app.mathpool import MathFailure, MathPool, MathTimeout

router = APIRouter(prefix="/api", tags=["check-working"])


@router.post(
    "/check-working",
    response_model=CheckWorkingResult,
)
async def post_check_working(body: CheckWorkingRequest, request: Request) -> CheckWorkingResult:
    pool: MathPool = request.app.state.pool
    problem = math_text(body.problem) if body.problem is not None else None
    kind = body.problem.kind if body.problem is not None else None
    try:
        found = await pool.run(
            check_working, problem, kind, [line_text(line) for line in body.lines]
        )
    except MathTimeout:
        return CheckWorkingResult(status="out_of_scope", reason="timeout")
    except MathFailure:
        return CheckWorkingResult(status="unclear", reason="math_error")
    lines = working_out(found.lines)
    if found.error == "unsupported":
        return CheckWorkingResult(status="out_of_scope", reason="unsupported", lines=lines)
    if found.error is not None:
        return CheckWorkingResult(status="unclear", reason=found.error, lines=lines)
    if found.first_bad_line is not None:
        return CheckWorkingResult(
            status="line_doesnt_follow", lines=lines, first_bad_line=bad_line(found.first_bad_line)
        )
    return CheckWorkingResult(status="all_follow", lines=lines, final=found.final)
