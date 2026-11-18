import pytest

from app.math import Problem, Step, check_steps
from app.math.worked import worked_solution


def lines(kind: str, expr: str) -> list[tuple[str, str, str]]:
    return [(s.left, s.right, s.op) for s in worked_solution(Problem(kind, expr))]  # type: ignore[arg-type]


def test_linear_equation_steps() -> None:
    assert lines("solve", "2*x + 6 = 10") == [
        ("2*x + 6", "10", "-6"),
        ("2*x", "4", "/2"),
        ("x", "2", ""),
    ]
    assert lines("solve", "5x + 3 = 2x + 9") == [
        ("5*x + 3", "2*x + 9", "-2*x"),
        ("3*x + 3", "9", "-3"),
        ("3*x", "6", "/3"),
        ("x", "2", ""),
    ]
    assert lines("solve", "x/2 + 3 = 7")[1:] == [("x/2", "4", "*2"), ("x", "8", "")]
    assert lines("solve", "-3x = 12") == [("-3*x", "12", "/(-3)"), ("x", "-4", "")]
    assert lines("solve", "10 = 2x - 4")[-1] == ("x", "7", "")


def test_fraction_steps() -> None:
    assert lines("evaluate", "1/2 + 1/3") == [
        ("1/2 + 1/3", "", ""),
        ("3/6 + 2/6", "", ""),
        ("5/6", "", ""),
    ]
    assert lines("evaluate", "3/4 - 1/4") == [
        ("3/4 - 1/4", "", ""),
        ("2/4", "", ""),
        ("1/2", "", ""),
    ]


def test_minus_negative_steps() -> None:
    assert lines("evaluate", "5 - (-3)") == [("5 - (-3)", "", ""), ("5 + 3", "", ""), ("8", "", "")]


def test_fallback_is_problem_and_answer() -> None:
    assert lines("simplify", "2/4") == [("2/4", "1/2", "")]
    assert lines("evaluate", "2 + 3*4") == [("2 + 3*4", "14", "")]


@pytest.mark.parametrize(
    ("kind", "expr"),
    [
        ("solve", "2*x + 6 = 10"),
        ("solve", "4x - 7 = 13"),
        ("solve", "3(x - 2) = x + 4"),
        ("evaluate", "-1/2 + 1/3"),
        ("evaluate", "2/3 - 5/6"),
        ("simplify", "2x + 3x"),
    ],
)
def test_every_solution_passes_the_step_check(kind: str, expr: str) -> None:
    problem = Problem(kind, expr)  # type: ignore[arg-type]
    steps = worked_solution(problem)
    assert steps and check_steps(problem, steps) == []


def test_no_steps_for_no_solution() -> None:
    assert worked_solution(Problem("solve", "x + 1 = x + 2")) == []
    assert isinstance(Step("x"), Step)


def test_signed_sum_steps() -> None:
    assert lines("evaluate", "-7 + 4") == [("-7 + 4", "", ""), ("-(7 - 4)", "", ""), ("-3", "", "")]
    assert lines("evaluate", "3 - 7") == [("3 - 7", "", ""), ("-(7 - 3)", "", ""), ("-4", "", "")]
    assert lines("evaluate", "-3 + (-4)")[1] == ("-(3 + 4)", "", "")


@pytest.mark.parametrize(("expr", "value"), [("-4 + 4", "0"), ("0 - 7", "-7"), ("-5 + 0", "-5")])
def test_zero_and_opposites_are_shown_as_written(expr: str, value: str) -> None:
    assert lines("evaluate", expr) == [(expr, value, "")]


def test_signed_product_steps() -> None:
    assert lines("evaluate", "(-4)*(-6)") == [
        ("(-4)*(-6)", "", ""),
        ("4*6", "", ""),
        ("24", "", ""),
    ]
    assert lines("evaluate", "-9*3") == [("(-9)*3", "", ""), ("-(9*3)", "", ""), ("-27", "", "")]
    assert lines("evaluate", "-100/(-4)")[1:] == [("100/4", "", ""), ("25", "", "")]


def test_whole_times_fraction_steps() -> None:
    assert lines("evaluate", "3*(2/5)") == [
        ("3*(2/5)", "", ""),
        ("(3*2)/5", "", ""),
        ("6/5", "", ""),
    ]
    assert lines("evaluate", "4*(3/8)")[-2:] == [("12/8", "", ""), ("3/2", "", "")]
    assert lines("evaluate", "(2/5)*3")[1] == ("(2*3)/5", "", "")


def test_fraction_quotient_steps() -> None:
    assert lines("evaluate", "(2/3)/(3/4)") == [
        ("(2/3)/(3/4)", "", ""),
        ("(2/3)*(4/3)", "", ""),
        ("(2*4)/(3*3)", "", ""),
        ("8/9", "", ""),
    ]


def test_bracket_is_divided_first() -> None:
    assert lines("solve", "5*(x + 3) = 35") == [
        ("5*(x + 3)", "35", "/5"),
        ("x + 3", "7", "-3"),
        ("x", "4", ""),
    ]
    # When the division isn't whole, the general method is used.
    assert lines("solve", "5*(x + 3) = 36")[0][2] == "-15"
