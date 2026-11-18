"""The sympy math core: parse, solve, classify, check steps and match misconception rules.

Everything here is deterministic. User input is parsed by our own parser (never `eval`) with
size guards, and sympy computes every value.
"""

from app.math.canonical import Verdict, classify_answer, is_canonical
from app.math.latex import latex_to_text, parse_latex
from app.math.nodes import (
    MathError,
    MathParseError,
    Node,
    UndefinedValue,
    UnsupportedProblem,
    render,
    to_sympy,
)
from app.math.parse import parse_text
from app.math.problems import (
    Format,
    Kind,
    Problem,
    Solution,
    Step,
    equivalent,
    format_value,
    parse_input,
    solve,
)
from app.math.rules import ALL_RULES, RULES, TOPICS, Rule, reproducing_rules, rule_reproduces
from app.math.steps import (
    LineFinding,
    StepCheck,
    StepIssue,
    check_step,
    check_steps,
    first_line_that_doesnt_follow,
)

__all__ = [
    "ALL_RULES",
    "RULES",
    "TOPICS",
    "Format",
    "Kind",
    "LineFinding",
    "MathError",
    "MathParseError",
    "Node",
    "Problem",
    "Rule",
    "Solution",
    "Step",
    "StepCheck",
    "StepIssue",
    "UndefinedValue",
    "UnsupportedProblem",
    "Verdict",
    "check_step",
    "check_steps",
    "classify_answer",
    "equivalent",
    "first_line_that_doesnt_follow",
    "format_value",
    "is_canonical",
    "latex_to_text",
    "parse_input",
    "parse_latex",
    "parse_text",
    "render",
    "reproducing_rules",
    "rule_reproduces",
    "solve",
    "to_sympy",
]
