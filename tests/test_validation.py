from types import SimpleNamespace

import pytest

from debate_ai.validation import argument_guardrail, parse_verdict, verdict_guardrail

REASON = "word " * 60


def out(raw):
    return SimpleNamespace(raw=raw)


@pytest.mark.parametrize("n,ok", [(0, False), (149, False), (150, True), (350, True), (351, False)])
def test_argument_word_bounds(n, ok):
    assert argument_guardrail(out("w " * n))[0] is ok


def test_argument_rejection_tells_the_model_the_count():
    ok, msg = argument_guardrail(out("only three words"))
    assert not ok and "3 words" in msg


def test_verdict_accepts_valid_json_and_code_fences():
    good = '{"winner":"against","reasoning":"%s"}' % REASON
    assert verdict_guardrail(out(good))[0]
    assert verdict_guardrail(out("```json\n" + good + "\n```"))[0]
    assert parse_verdict("```" + good + "```").winner == "against"


@pytest.mark.parametrize("raw", [
    "not json",
    '{"winner":"tie","reasoning":"%s"}' % REASON,
    '{"winner":"for"}',
    '{"winner":"for","reasoning":"too short"}',
    "",
])
def test_verdict_rejects_bad_replies_with_a_reason(raw):
    ok, msg = verdict_guardrail(out(raw))
    assert not ok and msg
