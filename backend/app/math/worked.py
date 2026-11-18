"""The correct solution as written lines, built by sympy (never by the LLM).

Shapes our topics use get real steps: a linear equation in one letter (a bracket times a number
is divided first), a sum or difference of two fractions, a whole number times a fraction, a
fraction divided by a fraction, `a - (-b)`, a sum or difference of two signed whole numbers, and
a product or exact quotient of two signed whole numbers. Anything else gets the problem and its
answer. Every list is
checked with `check_steps` before it is returned, so a generator bug falls back instead of
showing wrong math.
"""

from __future__ import annotations

from math import gcd

import sympy

from app.math.nodes import Bin, Eq, MathError, Neg, Node, Num, render, to_sympy
from app.math.problems import Problem, Solution, Step, format_value, linear_form, solve
from app.math.steps import check_steps


def worked_solution(problem: Problem) -> list[Step]:
    """Verified steps from the problem to its answer. Raises MathError if it can't be solved."""
    solution = solve(problem)
    node = problem.node()
    fallback = _fallback(node, solution)
    try:
        steps = _generate(node, solution)
    except MathError:
        steps = None
    if steps and not check_steps(problem, steps):
        return steps
    return fallback if not check_steps(problem, fallback) else []


def _fallback(node: Node, solution: Solution) -> list[Step]:
    if isinstance(node, Eq):
        if solution.variable is None or solution.value is None:
            return []
        return [
            Step(render(node.left), render(node.right)),
            Step(solution.variable, format_value(solution.value)),
        ]
    return [Step(render(node), solution.answer_text)]


def _generate(node: Node, solution: Solution) -> list[Step] | None:
    if isinstance(node, Eq):
        return _linear_steps(node, solution)
    if solution.value is None or solution.value.free_symbols:
        return None
    return (
        _fraction_steps(node)
        or _minus_negative_steps(node)
        or _signed_sum_steps(node)
        or _signed_product_steps(node)
        or _whole_times_fraction_steps(node)
        or _fraction_quotient_steps(node)
    )


def _num(value: sympy.Expr) -> str:
    return format_value(value)


def _term(coeff: sympy.Expr, var: str) -> str:
    """`3*x`, `x`, `-x`, `x/2`, `3*x/2`, as plain text."""
    return format_value(coeff * sympy.Symbol(var))


def _side(coeff: sympy.Expr, const: sympy.Expr, var: str) -> str:
    return format_value(coeff * sympy.Symbol(var) + const)


def _subtract_op(value: sympy.Expr, var: str | None = None) -> str:
    """The margin op that takes `value` (a number, or value·var) away: `-6`, `+4`, `-3*x`."""
    text = _term(abs(value), var) if var else _num(abs(value))
    return f"+{text}" if value < 0 else f"-{text}"


def _divide_op(a: sympy.Expr) -> str:
    if a.is_Integer:
        return f"/{a}" if a > 0 else f"/({a})"
    inverse = 1 / a
    text = _num(inverse)
    return f"*{text}" if inverse.is_Integer and inverse > 0 else f"*({text})"


def _linear_steps(eq: Eq, solution: Solution) -> list[Step] | None:
    if solution.kind != "value" or solution.variable is None:
        return None
    if (bracket := _bracket_steps(eq, solution)) is not None:
        return bracket
    lin = linear_form(eq)
    x = solution.variable
    a_l, b_l, a_r, b_r = lin.a_left, lin.b_left, lin.a_right, lin.b_right
    lines: list[tuple[str, str]] = [(render(eq.left), render(eq.right))]
    ops: list[str] = []
    if a_l != 0 and a_r != 0:
        ops.append(_subtract_op(a_r, x))
        a_l, a_r = a_l - a_r, sympy.Integer(0)
        lines.append((_side(a_l, b_l, x), _side(a_r, b_r, x)))
    # Now x is on one side only: keep track of which.
    x_left = a_l != 0
    a = a_l if x_left else a_r
    b_x = b_l if x_left else b_r  # the constant next to x
    if b_x != 0:
        ops.append(_subtract_op(b_x))
        if x_left:
            b_l, b_r = sympy.Integer(0), b_r - b_x
        else:
            b_r, b_l = sympy.Integer(0), b_l - b_x
        lines.append((_side(a_l, b_l, x), _side(a_r, b_r, x)))
    if a != 1:
        ops.append(_divide_op(a))
        value = solution.value
        assert value is not None
        lines.append((x, _num(value)) if x_left else (_num(value), x))
    if not x_left:
        lines.append((x, _num(solution.value)))  # read `5 = x` as `x = 5`
        ops.append("")
    ops.append("")
    return [Step(left, right, op) for (left, right), op in zip(lines, ops, strict=False)]


def _fraction(node: Node) -> tuple[int, int] | None:
    if isinstance(node, Neg) and (inner := _fraction(node.arg)) is not None:
        return -inner[0], inner[1]
    if isinstance(node, Bin) and node.op == "/":
        top, bottom = node.left, node.right
        if isinstance(top, Neg) and isinstance(top.arg, Num):
            top_value = -int(top.arg.text) if top.arg.is_integer else None
        elif isinstance(top, Num) and top.is_integer:
            top_value = int(top.text)
        else:
            top_value = None
        if top_value is not None and isinstance(bottom, Num) and bottom.is_integer:
            return top_value, int(bottom.text)
    return None


def _fraction_steps(node: Node) -> list[Step] | None:
    """`a/b ± c/d`: rewrite over the common denominator, combine, then simplify."""
    if not (isinstance(node, Bin) and node.op in ("+", "-")):
        return None
    left, right = _fraction(node.left), _fraction(node.right)
    if left is None or right is None or 0 in (left[1], right[1]):
        return None
    (a, b), (c, d) = left, right
    common = b * d // gcd(b, d)
    lines = [render(node)]
    if b != d:
        lines.append(f"{a * common // b}/{common} {node.op} {c * common // d}/{common}")
    top = a * common // b + (c if node.op == "+" else -c) * common // d
    lines.append(f"{top}/{common}")
    value = sympy.Rational(top, common)
    if value.q != common or value.p != top:
        lines.append(_num(value))
    return [Step(line) for line in lines]


def _minus_negative_steps(node: Node) -> list[Step] | None:
    """`a - (-b)` becomes `a + b`."""
    if not (isinstance(node, Bin) and node.op == "-" and isinstance(node.right, Neg)):
        return None
    plus = Bin("+", node.left, node.right.arg)
    return [Step(render(node)), Step(render(plus)), Step(_num(to_sympy(node)))]


def _integer(node: Node) -> int | None:
    """A whole number as written, possibly negative: `7`, `-7`."""
    if isinstance(node, Neg):
        inner = _integer(node.arg)
        return None if inner is None else -inner
    if isinstance(node, Num) and node.is_integer:
        return int(node.text)
    return None


def _signed(value: int) -> str:
    """A whole number as a factor: `4`, `(-4)`."""
    return f"({value})" if value < 0 else str(value)


def _bracket_steps(eq: Eq, solution: Solution) -> list[Step] | None:
    """`a*(x + b) = c` with a whole number a: divide by a first, then solve `x + b = c/a`."""
    left, right = eq.left, eq.right
    if not (isinstance(left, Bin) and left.op == "*" and _integer(right) is not None):
        return None
    a = _integer(left.left)
    if a is None or a in (0, 1, -1) or not isinstance(left.right, Bin):
        return None
    inner = left.right
    if inner.op not in ("+", "-") or _integer(inner.right) is None:
        return None
    c = _integer(right)
    assert c is not None
    if c % a:
        return None  # c/a is not whole: the general method is clearer than fractions here
    following = _linear_steps(Eq(inner, _int_node(c // a)), solution)
    if following is None:
        return None
    first = Step(render(left), render(right), _divide_op(sympy.Integer(a)))
    return [first, *following]


def _int_node(value: int) -> Node:
    return Neg(Num(str(-value))) if value < 0 else Num(str(value))


def _signed_sum_steps(node: Node) -> list[Step] | None:
    """`-7 + 4` becomes `-(7 - 4)`; `3 - 7` becomes `-(7 - 3)`; `-3 + (-4)` becomes `-(3 + 4)`.
    A zero or two opposite numbers (`0 - 7`, `-4 + 4`) need no middle line: the fallback shows
    them as written."""
    if not (isinstance(node, Bin) and node.op in ("+", "-")):
        return None
    a, b = _integer(node.left), _integer(node.right)
    if a is None or b is None:
        return None
    if node.op == "-":
        if isinstance(node.right, Neg):
            return None  # `a - (-b)` has its own steps
        b = -b
    if a >= 0 and b >= 0:
        return None  # nothing signed to explain
    if 0 in (a, b) or a == -b:
        return None
    total = a + b
    big, small = (a, b) if abs(a) >= abs(b) else (b, a)
    if (a < 0) == (b < 0):
        middle = f"-({abs(a)} + {abs(b)})"
    elif big < 0:
        middle = f"-({abs(big)} - {abs(small)})"
    else:
        middle = f"{abs(big)} - {abs(small)}"
    return [Step(render(node)), Step(middle), Step(str(total))]


def _signed_product_steps(node: Node) -> list[Step] | None:
    """`(-4)*(-6)` becomes `4*6`; `-9*3` becomes `-(9*3)`; `-100/(-4)` becomes `100/4`."""
    if not (isinstance(node, Bin) and node.op in ("*", "/")):
        return None
    a, b = _integer(node.left), _integer(node.right)
    if a is None or b is None or b == 0 or (a >= 0 and b >= 0):
        return None
    if node.op == "/" and a % b:
        return None  # not a whole number: a fraction, with its own steps
    value = a * b if node.op == "*" else a // b
    middle = f"{abs(a)}{node.op}{abs(b)}"
    if value < 0:
        middle = f"-({middle})"
    # line 0 as the problem is written: a negative factor keeps its brackets, `(-4)*(-6)`
    return [Step(f"{_signed(a)}{node.op}{_signed(b)}"), Step(middle), Step(str(value))]


def _whole_times_fraction_steps(node: Node) -> list[Step] | None:
    """`3*(2/5)` becomes `(3*2)/5`, and `(2/5)*3` becomes `(2*3)/5`, then `6/5` (then
    simplified when it can be)."""
    if not (isinstance(node, Bin) and node.op == "*"):
        return None
    whole, frac = _integer(node.left), _fraction(node.right)
    whole_first = True
    if whole is None or frac is None:
        whole, frac = _integer(node.right), _fraction(node.left)
        whole_first = False
    if whole is None or frac is None or frac[1] == 0:
        return None
    top, bottom = frac
    factors = (whole, top) if whole_first else (top, whole)
    lines = [render(node), f"({_signed(factors[0])}*{_signed(factors[1])})/{bottom}"]
    lines.append(f"{whole * top}/{bottom}")
    value = sympy.Rational(whole * top, bottom)
    if value.q != bottom or value.p != whole * top:
        lines.append(_num(value))
    return [Step(line) for line in lines]


def _fraction_quotient_steps(node: Node) -> list[Step] | None:
    """`(2/3)/(3/4)` becomes `(2/3)*(4/3)`, then `(2*4)/(3*3)`, then `8/9`."""
    if not (isinstance(node, Bin) and node.op == "/"):
        return None
    left, right = _fraction(node.left), _fraction(node.right)
    if left is None or right is None or 0 in (left[1], right[0], right[1]):
        return None
    (a, b), (c, d) = left, right
    if d < 0 or b < 0 or c <= 0:
        return None
    reciprocal = f"{d}/{c}"
    top, bottom = a * d, b * c
    lines = [
        f"({a}/{b})/({c}/{d})",
        f"({a}/{b})*({reciprocal})",
        f"({_signed(a)}*{d})/({b}*{c})",
        f"{top}/{bottom}",
    ]
    value = sympy.Rational(top, bottom)
    if value.q != bottom or value.p != top:
        lines.append(_num(value))
    return [Step(line) for line in lines]
