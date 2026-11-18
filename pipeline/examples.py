"""The three worked examples per topic, chosen to mirror the topic's misconceptions."""

from app.content.schema import Problem, TopicId

EXAMPLES: dict[TopicId, list[Problem]] = {
    "negative-numbers": [
        Problem(kind="evaluate", expr="5 - (-3)"),
        Problem(kind="evaluate", expr="-7 + 4"),
        Problem(kind="evaluate", expr="(-4)*(-6)"),
    ],
    "fractions": [
        Problem(kind="evaluate", expr="1/2 + 1/3"),
        Problem(kind="evaluate", expr="3*(2/5)"),
        Problem(kind="evaluate", expr="(2/3)/(3/4)"),
    ],
    "linear-equations": [
        Problem(kind="solve", expr="2*x + 6 = 10"),
        Problem(kind="solve", expr="5*(x + 3) = 35"),
        Problem(kind="solve", expr="3*x + 4 = x + 10"),
    ],
}


def prompt_for(problem: Problem) -> str:
    """Instruction-only prompts: the page shows the problem's math beside them."""
    if problem.kind == "evaluate":
        return "Work out:"
    if problem.kind == "simplify":
        return "Simplify:"
    letters = sorted({c for c in problem.expr if c.isalpha()})
    return f"Solve for {letters[0]}:"
