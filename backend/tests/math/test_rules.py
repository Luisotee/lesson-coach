import time

import pytest
import sympy

from app.math import ALL_RULES, RULES, TOPICS, Problem, reproducing_rules, rule_reproduces
from app.math.nodes import Bin
from app.math.rules import NodeRule

AGREED_IDS = {
    "negative-numbers": {
        "minus_negative_stays_minus",
        "neg_times_neg_is_neg",
        "add_magnitudes_keep_sign",
        "subtract_smaller_from_larger",
    },
    "fractions": {
        "add_tops_and_bottoms",
        "multiply_both_by_whole",
        "flip_first_when_dividing",
        "cancel_across_addition",
    },
    "linear-equations": {
        "sign_not_changed",
        "divide_one_term",
        "subtract_instead_of_divide",
        "wrong_inverse_order",
    },
}

# (rule id, problem, wrong answer): the agreed example first, then another problem of the shape.
EXAMPLES = [
    ("minus_negative_stays_minus", Problem("evaluate", "5 - (-3)"), "2"),
    ("minus_negative_stays_minus", Problem("evaluate", "-2 - (-7) + 1"), "-8"),
    ("neg_times_neg_is_neg", Problem("evaluate", "(-2) * (-3)"), "-6"),
    ("neg_times_neg_is_neg", Problem("evaluate", "(-12) / (-4)"), "-3"),
    ("add_magnitudes_keep_sign", Problem("evaluate", "-5 + 3"), "-8"),
    ("add_magnitudes_keep_sign", Problem("evaluate", "2 - 9"), "-11"),
    ("subtract_smaller_from_larger", Problem("evaluate", "3 - 7"), "4"),
    ("subtract_smaller_from_larger", Problem("evaluate", "-10 + 4"), "6"),
    ("add_tops_and_bottoms", Problem("evaluate", "1/2 + 1/3"), "2/5"),
    ("add_tops_and_bottoms", Problem("evaluate", "3/4 - 1/2"), "2/2"),
    ("multiply_both_by_whole", Problem("evaluate", "3 * 2/5"), "6/15"),
    ("multiply_both_by_whole", Problem("evaluate", "(1/4) * 2"), "1/4"),
    ("flip_first_when_dividing", Problem("evaluate", "(3/4) / (1/2)"), "2/3"),
    ("flip_first_when_dividing", Problem("evaluate", "2 / (1/3)"), "1/6"),
    ("cancel_across_addition", Problem("evaluate", "(2 + 4)/2"), "4"),
    ("cancel_across_addition", Problem("simplify", "(2x + 6)/2"), "x + 6"),
    ("sign_not_changed", Problem("solve", "2*x + 6 = 10"), "x = 8"),
    ("sign_not_changed", Problem("solve", "2*x + 6 = 10"), "2x = 16"),
    ("sign_not_changed", Problem("solve", "5x - 4 = 11"), "x = 7/5"),
    ("divide_one_term", Problem("solve", "2*x + 6 = 10"), "x = -1"),
    ("divide_one_term", Problem("solve", "2*x + 6 = 10"), "x + 6 = 5"),
    ("divide_one_term", Problem("solve", "4x + 8 = 20"), "x = 18"),
    ("subtract_instead_of_divide", Problem("solve", "3*x = 12"), "x = 9"),
    ("subtract_instead_of_divide", Problem("solve", "5x + 1 = 21"), "15"),
    ("wrong_inverse_order", Problem("solve", "(x + 6)/2 = 10"), "x = 8"),
    ("wrong_inverse_order", Problem("solve", "(x + 6)/2 = 10"), "x/2 = 4"),
    ("wrong_inverse_order", Problem("solve", "10 = (2x - 4)/3"), "x = 21"),
    ("wrong_inverse_order", Problem("solve", "(3 + x)/4 = 5"), "8"),
]


def test_registry_holds_exactly_the_agreed_ids() -> None:
    assert set(RULES) == set(TOPICS) == set(AGREED_IDS)
    assert {topic: set(rules) for topic, rules in RULES.items()} == AGREED_IDS
    for topic, rules in RULES.items():
        assert all(rule.topic == topic for rule in rules.values())


@pytest.mark.parametrize("rule_id", sorted(ALL_RULES))
def test_each_rule_reproduces_its_own_example(rule_id: str) -> None:
    rule = ALL_RULES[rule_id]
    assert rule_reproduces(rule_id, rule.example_problem, rule.example_wrong_answer)
    assert rule_id in reproducing_rules(
        rule.example_problem, rule.example_wrong_answer, topic=rule.topic
    )


@pytest.mark.parametrize(("rule_id", "problem", "answer"), EXAMPLES)
def test_rule_reproduces(rule_id: str, problem: Problem, answer: str) -> None:
    assert rule_reproduces(rule_id, problem, answer)


@pytest.mark.parametrize(
    ("problem", "answer"),
    [
        (Problem("evaluate", "5 - (-3)"), "8"),
        (Problem("evaluate", "1/2 + 1/3"), "5/6"),
        (Problem("evaluate", "1/2 + 1/3"), "10/12"),
        (Problem("solve", "2*x + 6 = 10"), "x = 2"),
        (Problem("solve", "2*x + 6 = 10"), "x = 5"),
        (Problem("evaluate", "1/2 + 1/3"), "7"),
    ],
)
def test_no_rule_for_right_or_unexplained_answers(problem: Problem, answer: str) -> None:
    assert reproducing_rules(problem, answer) == []


def test_linear_rules_give_one_diagnosis_each() -> None:
    assert reproducing_rules(Problem("solve", "2*x + 6 = 10"), "x = -1") == ["divide_one_term"]
    assert reproducing_rules(Problem("solve", "(x + 6)/2 = 10"), "x = 8") == ["wrong_inverse_order"]


def test_an_undefined_alternative_does_not_hide_later_ones() -> None:
    # Regression: alternative 0 was undefined everywhere, so alternative 1 was never tried.
    rule = NodeRule(lambda n: isinstance(n, Bin), lambda n, ev: [sympy.zoo, sympy.Integer(42)])
    assert 42 in rule.candidates(Problem("evaluate", "1 + 1"))


def test_long_sum_is_fast() -> None:
    # Regression: the evaluator re-evaluated children, so this took about 2^n time.
    start = time.perf_counter()
    assert reproducing_rules(Problem("evaluate", "+".join(["1"] * 60)), "0") == []
    assert reproducing_rules(Problem("evaluate", "-".join(["1"] * 60)), "0") == []
    assert time.perf_counter() - start < 2


def test_topic_filter() -> None:
    problem, answer = Problem("evaluate", "1/2 + 1/3"), "2/5"
    assert reproducing_rules(problem, answer, topic="negative-numbers") == []
    assert reproducing_rules(problem, answer, topic="fractions") == ["add_tops_and_bottoms"]
    assert reproducing_rules(problem, answer, topic="unknown") == []


def test_rules_ignore_other_problem_kinds_and_bad_input() -> None:
    assert not rule_reproduces("sign_not_changed", Problem("evaluate", "2 + 6"), "4")
    assert not rule_reproduces("add_tops_and_bottoms", Problem("solve", "x/2 + x/3 = 5"), "x = 2")
    assert not rule_reproduces(
        "add_tops_and_bottoms", Problem("evaluate", "1/2 + 1/3"), "two fifths"
    )
    assert reproducing_rules(Problem("evaluate", "1/2 + 1/3"), r"\frac{2}{5}", fmt="latex") == [
        "add_tops_and_bottoms"
    ]


def test_mistake_made_once_in_a_longer_problem() -> None:
    # 5 - (-3) - (-1) is 9. The mistake at the first, the second or both subtractions gives 3, 7, 1.
    problem = Problem("evaluate", "5 - (-3) - (-1)")
    for answer in ["3", "7", "1"]:
        assert rule_reproduces("minus_negative_stays_minus", problem, answer)
    assert not rule_reproduces("minus_negative_stays_minus", problem, "5")
