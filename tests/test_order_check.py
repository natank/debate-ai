"""Feature 002, subtask 1: OrderCheck and the comparison."""
import dataclasses

import pytest

from debate_ai.order_check import OrderCheck, compare_verdicts, not_completed
from debate_ai.run import RunResult
from debate_ai.validation import Verdict


def v(winner):
    return Verdict(winner=winner, reasoning="x")


@pytest.mark.parametrize("winner", ["for", "against"])
def test_the_same_side_winning_in_both_orders_is_stable(winner):
    check = compare_verdicts(v(winner), v(winner))
    assert check.status == "stable"
    assert check.favored is None and check.reason is None
    assert check.swapped == v(winner)


def test_for_then_against_is_sensitive_and_favored_the_argument_read_first():
    check = compare_verdicts(v("for"), v("against"))
    assert (check.status, check.favored) == ("sensitive", "first")
    assert check.swapped == v("against") and check.reason is None


def test_against_then_for_is_sensitive_and_favored_the_argument_read_last():
    check = compare_verdicts(v("against"), v("for"))
    assert (check.status, check.favored) == ("sensitive", "last")
    assert check.swapped == v("for")


def test_not_completed_carries_its_reason_and_no_swapped_verdict():
    check = not_completed("  the swapped verdict was rejected 3 times ")
    assert check == OrderCheck("not_completed", reason="the swapped verdict was rejected 3 times")
    assert check.swapped is None and check.favored is None


@pytest.mark.parametrize("reason", ["", "   ", None])
def test_not_completed_needs_a_reason(reason):
    with pytest.raises(ValueError):
        not_completed(reason)


def test_an_order_check_is_immutable():
    check = compare_verdicts(v("for"), v("for"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        check.status = "sensitive"


def test_a_run_result_without_the_field_still_works_and_has_no_check():
    result = RunResult("success", "m")
    assert result.order_check is None
    with_check = RunResult("success", "m", order_check=compare_verdicts(v("for"), v("against")))
    assert with_check.order_check.status == "sensitive"


def test_comparing_calls_no_model(monkeypatch):
    import debate_ai.run as run

    monkeypatch.setattr(run, "run_debate", lambda *a, **k: pytest.fail("model run"))
    compare_verdicts(v("for"), v("against"))
