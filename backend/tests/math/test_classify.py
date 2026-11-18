import pytest
import sympy

from app.math import (
    MathParseError,
    Problem,
    UnsupportedProblem,
    classify_answer,
    equivalent,
    is_canonical,
    parse_text,
    solve,
)


class TestSolve:
    def test_evaluate(self) -> None:
        assert solve(Problem("evaluate", "-5 - (-3)")).value == -2
        solution = solve(Problem("evaluate", "1/2 + 1/3"))
        assert solution.value == sympy.Rational(5, 6)
        assert solution.answer_text == "5/6"

    def test_simplify(self) -> None:
        assert solve(Problem("simplify", "2/4")).answer_text == "1/2"
        assert solve(Problem("simplify", "-2/4")).answer_text == "-1/2"
        assert solve(Problem("simplify", "2x + 3x - 1")).answer_text == "5*x - 1"

    def test_solve_linear(self) -> None:
        solution = solve(Problem("solve", "2*x + 6 = 10"))
        assert (solution.kind, solution.value, solution.variable) == ("value", 2, "x")
        assert solution.answer_text == "x = 2"
        assert solve(Problem("solve", "5y + 3 = 2y + 9")).answer_text == "y = 2"
        assert solve(Problem("solve", "x/2 = 3/4")).answer_text == "x = 3/2"

    def test_no_solution_and_every_value(self) -> None:
        assert solve(Problem("solve", "x + 1 = x + 2")).kind == "none"
        assert solve(Problem("solve", "2(x + 1) = 2x + 2")).kind == "all"

    @pytest.mark.parametrize(
        "problem",
        [
            Problem("solve", "x^2 = 4"),
            Problem("solve", "x + y = 2"),
            Problem("solve", "1/x = 2"),
            Problem("solve", "2 = 2"),
            Problem("solve", "2x + 1"),
            Problem("evaluate", "x = 2"),
            Problem("evaluate", "1/0"),
        ],
    )
    def test_unsupported(self, problem: Problem) -> None:
        with pytest.raises((UnsupportedProblem, ValueError)):
            solve(problem)

    def test_from_dict(self) -> None:
        assert Problem.from_dict({"kind": "solve", "expr": "x = 1"}) == Problem("solve", "x = 1")
        with pytest.raises(UnsupportedProblem):
            Problem.from_dict({"kind": "integrate", "expr": "x"})


class TestCanonical:
    @pytest.mark.parametrize(
        "text",
        [
            "3",
            "-3",
            "0",
            "1/2",
            "-1/2",
            "-(1/2)",
            "3/2",
            "1 1/2",
            "5x",
            "5x - 1",
            "x/2 + 3",
            "x^2 - 1",
            "-x + 2",
        ],
    )
    def test_canonical(self, text: str) -> None:
        assert is_canonical(parse_text(text))

    @pytest.mark.parametrize(
        "text",
        [
            "2/4",
            "-2/4",
            "1/-2",
            "4/2",
            "0/3",
            "-0",
            "3 3/2",
            "1 2/4",
            "0.5",
            "1/2 + 1/3",
            "2x + 3x",
            "2(x+1)",
            "1x",
            "x + -1",
            "5 - (-3)",
            "x = 1",
        ],
    )
    def test_not_canonical(self, text: str) -> None:
        assert not is_canonical(parse_text(text))

    def test_decimals_allowed_when_asked(self) -> None:
        assert is_canonical(parse_text("0.5"), allow_decimals=True)


class TestClassify:
    def test_simplify_guard(self) -> None:
        problem = Problem("simplify", "2/4")
        assert classify_answer(problem, "2/4") == "equivalent_not_simplified"
        assert classify_answer(problem, "1/2") == "correct"
        assert classify_answer(problem, "2/3") == "wrong"
        assert classify_answer(problem, "0.5") == "equivalent_not_simplified"
        assert classify_answer(problem, r"\frac{1}{2}", fmt="latex") == "correct"
        assert classify_answer(problem, r"\frac{2}{4}", fmt="latex") == "equivalent_not_simplified"

    def test_negative_fraction_guard(self) -> None:
        assert equivalent(parse_text("-2/4"), parse_text("-1/2"))
        assert classify_answer(Problem("simplify", "-2/4"), "-1/2") == "correct"
        assert (
            classify_answer(Problem("evaluate", "-1/4 - 1/4"), "-2/4")
            == "equivalent_not_simplified"
        )

    def test_solve_guard_x_equals_3_is_3(self) -> None:
        assert equivalent(parse_text("x = 3"), parse_text("3"))
        problem = Problem("solve", "2x + 6 = 12")
        for answer in ["x = 3", "3", "3 = x", "x=3"]:
            assert classify_answer(problem, answer) == "correct"

    def test_solve_unfinished_or_wrong(self) -> None:
        problem = Problem("solve", "2x + 6 = 12")
        assert classify_answer(problem, "2x = 6") == "equivalent_not_simplified"
        assert classify_answer(problem, "x = 6/2") == "equivalent_not_simplified"
        assert classify_answer(problem, "x = 4") == "wrong"
        assert classify_answer(problem, "2x = 8") == "wrong"
        assert classify_answer(problem, "y = 3") == "wrong"
        assert classify_answer(problem, "x") == "wrong"
        assert classify_answer(problem, "x^2 = 9") == "wrong"

    def test_evaluate(self) -> None:
        problem = Problem("evaluate", "1/2 + 1/3")
        assert classify_answer(problem, "5/6") == "correct"
        assert classify_answer(problem, "10/12") == "equivalent_not_simplified"
        assert classify_answer(problem, "= 5/6") == "correct"
        assert classify_answer(problem, "1/2 + 1/3 = 5/6") == "correct"
        assert classify_answer(problem, "2/5") == "wrong"
        assert classify_answer(Problem("evaluate", "-5 - (-3)"), "-2") == "correct"
        assert classify_answer(Problem("evaluate", "0.5 + 0.25"), "0.75") == "correct"

    def test_unreadable_answer_raises(self) -> None:
        with pytest.raises(MathParseError):
            classify_answer(Problem("simplify", "2/4"), "one half")

    def test_division_by_zero_is_wrong(self) -> None:
        assert classify_answer(Problem("simplify", "2/4"), "1/0") == "wrong"


class TestEquivalent:
    def test_expressions(self) -> None:
        assert equivalent(parse_text("2(x + 3)"), parse_text("2x + 6"))
        assert not equivalent(parse_text("2(x + 3)"), parse_text("2x + 3"))

    def test_equations(self) -> None:
        assert equivalent(parse_text("2x + 6 = 10"), parse_text("x = 2"))
        assert equivalent(parse_text("x = 2"), parse_text("2 = x"))
        assert not equivalent(parse_text("x = 2"), parse_text("y = 2"))
        assert not equivalent(parse_text("2x + 6 = 10"), parse_text("2x = 16"))
        assert equivalent(parse_text("x + 1 = x + 2"), parse_text("0 = 1"))

    def test_non_linear_equations_by_factor(self) -> None:
        assert equivalent(parse_text("x^2 = 4"), parse_text("2x^2 = 8"))
        assert not equivalent(parse_text("x^2 = 4"), parse_text("x = 2"))

    def test_undefined_is_not_equivalent(self) -> None:
        assert not equivalent(parse_text("1/0"), parse_text("1"))
