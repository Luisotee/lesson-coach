"""`POST /api/check-working`: which line of the working first doesn't follow. sympy only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.convert import bad_line, line_text, math_text
from app.api.limits import rate_limit
from app.api.models import CheckWorkingRequest, CheckWorkingResult
from app.math.pipeline import check_working
from app.mathpool import MathPool, MathTimeout

router = APIRouter(prefix="/api", tags=["check-working"])


@router.post(
    "/check-working",
    response_model=CheckWorkingResult,
    dependencies=[Depends(rate_limit("check_working"))],
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
    if found.error == "unsupported":
        return CheckWorkingResult(status="out_of_scope", reason="unsupported")
    if found.error is not None:
        return CheckWorkingResult(status="unclear", reason=found.error)
    if found.first_bad_line is not None:
        return CheckWorkingResult(
            status="line_doesnt_follow", first_bad_line=bad_line(found.first_bad_line)
        )
    return CheckWorkingResult(status="all_follow", final=found.final)
