"""Feature 006: the crew's behavior must match a baseline recorded before it was refactored.

The baseline (tests/data/crew_baseline.json) was recorded from the hand-built crew,
before the @CrewBase change. It holds, for a debate with the order check off and on:
every prompt sent to the (fake) model, every artifact file, the per-stage stats, and
the result. It contains fake text only.

Regenerate it only when behavior is *meant* to change:  uv run python -m tests.test_crew_parity
"""
import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from debate_ai.run import run_debate
from tests.fakes import make_stage_llm

BASELINE = Path(__file__).parent / "data" / "crew_baseline.json"
P, O, D = "You are proposing", "You are in opposition", "Review the arguments"
FOR_TEXT = "ZX-FOR-MARKER " + "pro " * 200
AGAINST_TEXT = "QW-AGAINST-MARKER " + "con " * 200
REASON = "The two arguments were weighed on their specific points and one was clearly better. " * 4
NOW = datetime(2026, 9, 30, 12, 0, 0)


def _verdict(winner, marker):
    return json.dumps({"winner": winner, "reasoning": f"{marker} {REASON}"})


def capture(check_order: bool, output_dir) -> dict:
    """Run one debate with the fake model and return everything observable about it."""
    llm = make_stage_llm({
        P: [FOR_TEXT], O: [AGAINST_TEXT],
        D: [_verdict("for", "FIRST-VERDICT"), _verdict("against", "SECOND-VERDICT")],
    })
    result = run_debate(
        "Cats make better pets than dogs", output_dir=output_dir, llm_factory=lambda _m: llm,
        write_backoff=0, now=NOW, check_order=check_order,
    )
    folder = Path(output_dir) / result.run_id
    check = result.order_check
    return json.loads(json.dumps({
        "prompts": llm.calls,
        "artifacts": {p.name: p.read_text() for p in sorted(folder.iterdir())},
        "stats": {k: [v.attempts, v.prompt_tokens, v.completion_tokens, v.total_tokens]
                  for k, v in result.stats.items()},
        "result": {
            "outcome": result.outcome,
            "verdict": [result.verdict.winner, result.verdict.reasoning],
            "order_check": None if check is None else {
                "status": check.status, "favored": check.favored, "reason": check.reason,
                "swapped": None if check.swapped is None else check.swapped.winner,
            },
        },
    }))


def record():
    data = {}
    for key, check in (("check_off", False), ("check_on", True)):
        with tempfile.TemporaryDirectory() as tmp:
            data[key] = capture(check, tmp)
    BASELINE.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"recorded {BASELINE}")


@pytest.mark.parametrize("key,check", [("check_off", False), ("check_on", True)])
@pytest.mark.parametrize("part", ["prompts", "artifacts", "stats", "result"])
def test_behavior_matches_the_recorded_baseline(tmp_path, key, check, part):
    expected = json.loads(BASELINE.read_text(encoding="utf-8"))[key][part]
    actual = capture(check, tmp_path)[part]
    assert actual == expected, f"{part} with the order check {'on' if check else 'off'} differ from the baseline"


def test_the_baseline_is_not_empty_and_covers_both_modes():
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert set(data) == {"check_off", "check_on"}
    assert len(data["check_off"]["prompts"]) == 3 and len(data["check_on"]["prompts"]) == 4
    assert "decide_swapped.md" in data["check_on"]["artifacts"]
    assert "decide_swapped.md" not in data["check_off"]["artifacts"]
    assert data["check_off"]["result"]["order_check"] is None
    assert data["check_on"]["result"]["order_check"]["status"] == "sensitive"


def test_the_baseline_holds_fake_data_only():
    text = BASELINE.read_text(encoding="utf-8")
    assert "sk-" not in text and "OPENAI" not in text and "api_key" not in text.lower()


if __name__ == "__main__":
    record()
