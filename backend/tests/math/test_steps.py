import pytest

from app.math import (
    LineFinding,
    MathParseError,
    Problem,
    Step,
    UnsupportedProblem,
    check_step,
    check_steps,
    first_line_that_doesnt_follow,
)
from app.math.steps import parse_op

EQUATION = Problem("solve", "3x + 5 = 20")
GOOD_EXAMPLE = [Step("3x + 5", "20", "| −5"), Step("3x", "15", "| ÷ 3"), Step("x", "5")]


class TestCheckStep:
    def test_valid_step(self) -> None:
        result = check_step(Step("2x + 6", "10", "-6"), Step("2x", "4"))
        assert (result.equivalent, result.identical, result.op_ok, result.ok) == (
            True,
            False,
            True,
            True,
        )

    def test_identical_step_is_rejected(self) -> None:
        result = check_step(Step("2x + 6", "10"), Step("2*x + 6", "10"))
        assert result.equivalent and result.identical and not result.ok

    def test_redundant_brackets_are_identical(self) -> None:
        assert check_step(Step("(2x) + 6", "10"), Step("2x + 6", "(10)")).identical

    def test_reordering_is_a_real_step(self) -> None:
        result = check_step(Step("6 + 2x", "10"), Step("2x + 6", "10"))
        assert result.ok

    def test_wrong_step(self) -> None:
        result = check_step(Step("2x + 6", "10", "-6"), Step("2x", "16"))
        assert not result.equivalent and result.op_ok is False and not result.ok

    def test_op_that_does_not_produce_the_next_line(self) -> None:
        result = check_step(Step("2x + 6", "10", "/2"), Step("2x", "4"))
        assert result.equivalent and result.op_ok is False and not result.ok

    def test_expression_chain(self) -> None:
        result = check_step(Step("1/2 + 1/3"), Step("3/6 + 2/6"), kind="evaluate")
        assert result.ok
        assert not check_step(Step("1/2 + 1/3"), Step("2/5"), kind="evaluate").equivalent
        assert check_step(Step("1/2 + 1/3"), Step("1/2 + 1/3"), kind="evaluate").identical


class TestParseOp:
    @pytest.mark.parametrize(
        ("op", "sign", "value"),
        [
            ("-6", "-", 6),
            ("| −5", "-", 5),
            ("| –5", "-", 5),
            ("⋅ 2", "*", 2),
            ("÷ 3", "/", 3),
            ("*(-1)", "*", -1),
            (": 2", "/", 2),
            ("+2x", "+", None),
        ],
    )
    def test_ops(self, op: str, sign: str, value: int | None) -> None:
        parsed = parse_op(op)
        assert parsed is not None and parsed[0] == sign
        if value is not None:
            assert parsed[1] == value

    def test_empty(self) -> None:
        assert parse_op("") is None and parse_op(" | ") is None

    @pytest.mark.parametrize("op", ["6", "sqrt", "-x=1", "-" + "1" * 40])
    def test_bad(self, op: str) -> None:
        with pytest.raises(MathParseError):
            parse_op(op)


class TestCheckSteps:
    def test_good_worked_example(self) -> None:
        assert check_steps(EQUATION, GOOD_EXAMPLE) == []

    def test_good_expression_example(self) -> None:
        steps = [Step("1/2 + 1/3"), Step("3/6 + 2/6"), Step("5/6")]
        assert check_steps(Problem("evaluate", "1/2 + 1/3"), steps) == []
        chain = [Step("1/2 + 1/3", "3/6 + 2/6"), Step("", "5/6")]
        assert check_steps(Problem("evaluate", "1/2 + 1/3"), chain) == []

    def test_identical_step(self) -> None:
        steps = [Step("3x + 5", "20"), Step("3x+5", "20", "-5"), *GOOD_EXAMPLE[1:]]
        assert [(i.index, i.reason) for i in check_steps(EQUATION, steps)] == [(1, "identical")]

    def test_wrong_op(self) -> None:
        steps = [Step("3x + 5", "20", "+5"), *GOOD_EXAMPLE[1:]]
        assert [(i.index, i.reason) for i in check_steps(EQUATION, steps)] == [(1, "op_mismatch")]

    def test_not_equivalent(self) -> None:
        steps = [GOOD_EXAMPLE[0], Step("3x", "25", "/3"), Step("x", "25/3")]
        reasons = [(i.index, i.reason) for i in check_steps(EQUATION, steps)]
        assert (1, "not_equivalent") in reasons

    def test_final_answer_not_simplified(self) -> None:
        steps = [*GOOD_EXAMPLE[:2], Step("x", "15/3")]
        assert [(i.index, i.reason) for i in check_steps(EQUATION, steps)] == [
            (2, "not_simplified")
        ]
        steps = [*GOOD_EXAMPLE[:2], Step("x", "5"), Step("3x", "15")]
        reasons = [i.reason for i in check_steps(EQUATION, steps)]
        assert "not_simplified" in reasons

    def test_final_answer_wrong_and_false_equality(self) -> None:
        problem = Problem("evaluate", "1/2 + 1/3")
        issues = check_steps(problem, [Step("1/2 + 1/3", "2/5")])
        assert (issues[0].index, issues[0].reason) == (0, "false_equality")

    def test_no_solution_example_passes(self) -> None:
        problem = Problem("solve", "x + 1 = x + 2")
        assert check_steps(problem, [Step("x + 1", "x + 2", "-x"), Step("1", "2")]) == []
        issues = check_steps(problem, [Step("x + 1", "x + 2", "-x"), Step("x", "1")])
        assert "not_equivalent" in [i.reason for i in issues]

    def test_restating_a_no_solution_problem_does_not_pass(self) -> None:
        issues = check_steps(Problem("solve", "x+1=x+2"), [Step("x+1", "x+2")])
        assert [(i.index, i.reason) for i in issues] == [(0, "wrong_answer")]
        every = Problem("solve", "2(x+1)=2x+2")
        assert [i.reason for i in check_steps(every, [Step("2(x+1)", "2x+2")])] == ["wrong_answer"]
        assert check_steps(every, [Step("2(x+1)", "2x+2", "-2x"), Step("2", "2")]) == []

    def test_out_of_scope_steps_are_issues_not_errors(self) -> None:
        issues = check_steps(Problem("solve", "2x=6"), [Step("2x", "6"), Step("x", "6/x")])
        assert (1, "unsupported") in [(i.index, i.reason) for i in issues]
        issues = check_steps(Problem("solve", "6/x=2"), [Step("6", "2x")])
        assert [(i.index, i.reason) for i in issues] == [(0, "unsupported")]
        result = check_step(Step("6/x", "2", "*x"), Step("6", "2x"))
        assert result.unsupported and not result.ok

    def test_unparsable_step(self) -> None:
        issues = check_steps(EQUATION, [Step("3x + 5", "twenty")])
        assert [(i.index, i.reason) for i in issues] == [(0, "unparsable")]


class TestFirstLineThatDoesntFollow:
    def test_all_lines_follow(self) -> None:
        lines = [Step("2x + 6", "10"), Step("2x", "4"), Step("x", "2")]
        assert first_line_that_doesnt_follow(lines, Problem("solve", "2x + 6 = 10")) is None
        assert first_line_that_doesnt_follow(lines) is None

    def test_finds_the_first_bad_line(self) -> None:
        lines = [Step("2x + 6", "10"), Step("2x", "16"), Step("x", "8")]
        assert first_line_that_doesnt_follow(lines) == LineFinding(1, "not_equivalent")

    def test_compares_line_zero_with_the_problem(self) -> None:
        lines = [Step("x + 6", "5"), Step("x", "-1")]
        found = first_line_that_doesnt_follow(lines, Problem("solve", "2x + 6 = 10"))
        assert found == LineFinding(0, "not_equivalent")

    def test_copied_line_still_follows(self) -> None:
        lines = [Step("2x + 6", "10"), Step("2x + 6", "10"), Step("x", "2")]
        assert first_line_that_doesnt_follow(lines) is None

    def test_bare_answer_line(self) -> None:
        lines = [Step("2x", "4"), Step("2")]
        assert first_line_that_doesnt_follow(lines, Problem("solve", "2x + 6 = 10")) is None
        lines = [Step("2x", "4"), Step("3")]
        assert first_line_that_doesnt_follow(lines, Problem("solve", "2x + 6 = 10")) == LineFinding(
            1, "not_equivalent"
        )

    def test_expression_chain(self) -> None:
        problem = Problem("evaluate", "5 - (-3)")
        assert first_line_that_doesnt_follow([Step("5 + 3"), Step("8")], problem) is None
        assert first_line_that_doesnt_follow([Step("5 - 3"), Step("2")], problem) == LineFinding(
            0, "not_equivalent"
        )
        found = first_line_that_doesnt_follow([Step("5 + 3", "9")], problem)
        assert found == LineFinding(0, "false_equality")

    def test_non_linear_problem_does_not_raise(self) -> None:
        problem = Problem("solve", "x^2 = 4")
        assert first_line_that_doesnt_follow([Step("2x^2", "8")], problem) is None
        found = first_line_that_doesnt_follow([Step("x^2", "8")], problem)
        assert found == LineFinding(0, "not_equivalent")

    def test_equations_typed_in_one_field(self) -> None:
        lines = [Step("2x+6=10"), Step("2x=4"), Step("x=2")]
        assert first_line_that_doesnt_follow(lines) is None
        lines = [Step("2x+6=10"), Step("2x=16"), Step("x=8")]
        assert first_line_that_doesnt_follow(lines) == LineFinding(1, "not_equivalent")

    def test_rational_line_is_unsupported_at_its_index(self) -> None:
        lines = [Step("6/x", "2", "*x"), Step("6", "2x")]
        assert first_line_that_doesnt_follow(lines) == LineFinding(1, "unsupported")

    def test_rational_problem_raises(self) -> None:
        with pytest.raises(UnsupportedProblem):
            first_line_that_doesnt_follow([Step("6", "2x")], Problem("solve", "6/x = 2"))

    def test_student_line_out_of_scope_is_unsupported(self) -> None:
        lines = [Step("2x+6", "10"), Step("a+b+c", "4")]
        found = first_line_that_doesnt_follow(lines, Problem("solve", "2x+6=10"))
        assert found == LineFinding(1, "unsupported")

    def test_number_equations_in_one_field_are_an_expression_chain(self) -> None:
        # Regression: these switched to solve mode, where every false line is "no solution".
        lines = [Step("1/2+1/3=2/5"), Step("2/5=3/7")]
        assert first_line_that_doesnt_follow(lines) == LineFinding(0, "false_equality")
        assert first_line_that_doesnt_follow([Step("1/2+1/3=5/6"), Step("5/6")]) is None
        problem = Problem("evaluate", "1/2 + 1/3")
        assert first_line_that_doesnt_follow([Step("1/2+1/3=2/5")], problem) == LineFinding(
            0, "false_equality"
        )

    def test_unparsable_line(self) -> None:
        lines = [Step("2x + 6", "10"), Step("2x", "4?")]
        assert first_line_that_doesnt_follow(lines) == LineFinding(1, "unparsable")
