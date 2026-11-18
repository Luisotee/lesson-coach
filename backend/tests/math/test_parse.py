import pytest
import sympy

from app.math import MathParseError, UndefinedValue, parse_latex, parse_text, render, to_sympy
from app.math.latex import latex_to_text
from app.math.nodes import Bin, Eq, Mixed, Neg, Num, Pow, Var
from app.math.parse import MAX_DEPTH, MAX_DIGITS, MAX_EXPONENT, MAX_LENGTH


def test_keeps_the_written_form() -> None:
    assert parse_text("2/4") == Bin("/", Num("2"), Num("4"))
    assert parse_text("2/4") != parse_text("1/2")
    assert parse_text("1/2 + 1/3") != parse_text("5/6")
    assert parse_text("5 - (-3)") == Bin("-", Num("5"), Neg(Num("3")))
    assert parse_text("5 - (-3)") != parse_text("5 + 3")


def test_equations_and_implicit_multiplication() -> None:
    assert parse_text("2x + 6 = 10") == parse_text("2*x+6=10")
    assert parse_text("2(x+1)") == Bin("*", Num("2"), Bin("+", Var("x"), Num("1")))
    assert isinstance(parse_text("x = 3"), Eq)
    assert to_sympy(parse_text("xy")) == sympy.Symbol("x") * sympy.Symbol("y")


def test_unicode_operators_and_decimal_comma() -> None:
    assert parse_text("6 ÷ 2 × 3 − 1") == parse_text("6 / 2 * 3 - 1")
    assert parse_text("2·x") == parse_text("2*x")
    assert to_sympy(parse_text("0,5")) == sympy.Rational(1, 2)
    assert parse_text("x**2") == Pow(Var("x"), 2)


def test_precedence() -> None:
    assert to_sympy(parse_text("-2^2")) == -4
    assert to_sympy(parse_text("(-2)^2")) == 4
    assert to_sympy(parse_text("2*-3")) == -6
    assert to_sympy(parse_text("8/4/2")) == 1
    assert to_sympy(parse_text("1 - 2 - 3")) == -4
    assert parse_text("(-2)*(-3)") == Bin("*", Neg(Num("2")), Neg(Num("3")))


def test_mixed_numbers() -> None:
    assert parse_text("1 1/2") == Mixed(1, 1, 2)
    assert to_sympy(parse_text("2 3/4")) == sympy.Rational(11, 4)
    assert parse_text("1/2") == Bin("/", Num("1"), Num("2"))


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        "2 +",
        "(2",
        "2)",
        "1 = 2 = 3",
        "x_1",
        "__import__('os')",
        "2 3",
        "x^y",
        "2^1.5",
        "a.b",
        "[1]",
    ],
)
def test_rejects_bad_input(bad: str) -> None:
    with pytest.raises(MathParseError):
        parse_text(bad)


def test_size_guards() -> None:
    with pytest.raises(MathParseError):
        parse_text("1+" * MAX_LENGTH)
    with pytest.raises(MathParseError):
        parse_text("(" * (MAX_DEPTH + 1) + "1" + ")" * (MAX_DEPTH + 1))
    with pytest.raises(MathParseError):
        parse_text("-" * (MAX_DEPTH + 1) + "1")
    with pytest.raises(MathParseError):
        parse_text("1" * (MAX_DIGITS + 1))
    with pytest.raises(MathParseError):
        parse_text(f"9^{MAX_EXPONENT + 1}")
    with pytest.raises(MathParseError):
        parse_text("((2^10)^10)^10")
    with pytest.raises(MathParseError):
        parse_text("(x^2 + 1)^2")
    assert to_sympy(parse_text(f"2^{MAX_EXPONENT}")) == 2**MAX_EXPONENT
    assert to_sympy(parse_text("2^(-1)")) == sympy.Rational(1, 2)


def test_division_by_zero_is_undefined() -> None:
    with pytest.raises(UndefinedValue):
        to_sympy(parse_text("1/0"))
    with pytest.raises(UndefinedValue):
        to_sympy(parse_text("0^(-1)"))


def test_render_round_trips() -> None:
    for text in [
        "2/4",
        "5 - (-3)",
        "2*x + 6 = 10",
        "(2 + 4)/2",
        "-(1/2)",
        "x^2 - 1",
        "1 1/2",
        "2^(-1)",
    ]:
        node = parse_text(text)
        assert parse_text(render(node)) == node


class TestLatex:
    def test_fractions_stay_unevaluated(self) -> None:
        assert parse_latex(r"\frac{2}{4}") == parse_text("2/4")
        assert parse_latex(r"\frac{1}{2}+\frac{1}{3}") == parse_text("1/2 + 1/3")
        assert parse_latex(r"\frac12") == parse_text("1/2")
        assert parse_latex(r"\dfrac{x+1}{2}") == parse_text("(x+1)/2")

    def test_mixed_number(self) -> None:
        assert parse_latex(r"1\frac{1}{2}") == Mixed(1, 1, 2)
        assert parse_latex(r"2\cdot\frac{1}{2}") == parse_text("2 * (1/2)")
        assert parse_latex(r"x^2\frac{1}{2}") == parse_text("x^2 * (1/2)")

    def test_operators_and_brackets(self) -> None:
        assert parse_latex(r"\frac{3}{4}\div\frac{1}{2}") == parse_text("(3/4)/(1/2)")
        assert parse_latex(r"-5-\left(-3\right)") == parse_text("-5 - (-3)")
        assert parse_latex(r"2\times3") == parse_text("2*3")
        assert parse_latex(r"2x+6=10") == parse_text("2x + 6 = 10")
        assert parse_latex(r"x^{-2}") == Pow(Var("x"), -2)
        assert parse_latex(r"3\,x") == parse_text("3x")

    @pytest.mark.parametrize(
        "bad", [r"\sqrt{2}", r"\placeholder{}", r"\frac{1}", r"{1", r"1}", "\\", r"\mathrm{x}"]
    )
    def test_rejects_unsupported(self, bad: str) -> None:
        with pytest.raises(MathParseError):
            parse_latex(bad)

    def test_length_guard(self) -> None:
        with pytest.raises(MathParseError):
            latex_to_text("1" * 1000)
