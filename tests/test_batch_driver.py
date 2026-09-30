import json
from datetime import datetime

import pytest

from debate_ai import batch as batch_module
from debate_ai.artifacts import WriteFailed
from debate_ai.batch import parse_motions, run_batch
from debate_ai.run import RunResult, StageStats
from debate_ai.validation import Verdict
from tests.fakes import make_stage_llm

NOW = datetime(2026, 9, 30, 10, 15, 0)


def ok(winner="for", tokens=2000):
    return RunResult("success", "m", run_id="r", verdict=Verdict(winner=winner, reasoning="x"),
                     stats={"decide": StageStats(3, tokens - 500, 500, tokens)})


def exhausted(tokens=1400):
    return RunResult("exhausted", "m", run_id="r", stage="oppose", reason="why",
                     stats={"oppose": StageStats(3, tokens - 300, 300, tokens)})


def scripted(*outcomes):
    """A fake `run_debate`: returns the next outcome, and records its calls."""
    calls = []

    def run(motion, *, output_dir, **kw):
        calls.append((motion, output_dir, kw))
        out = outcomes[len(calls) - 1]
        if isinstance(out, BaseException):
            raise out
        return out

    run.calls = calls
    return run


def summary_text(result):
    return result.summary_path.read_text()


def test_three_succeed_in_order_with_progress_and_a_complete_summary(tmp_path):
    entries = parse_motions("A\nB\nC\n")
    run = scripted(ok("for"), ok("against"), ok("for"))
    seen = []
    result = run_batch(entries, output_dir=tmp_path, run=run, now=NOW,
                       on_progress=lambda i, n, e, r: seen.append((i, n, e.motion, r.outcome)))
    assert [c[0] for c in run.calls] == ["A", "B", "C"]
    assert seen == [(1, 3, "A", "success"), (2, 3, "B", "success"), (3, 3, "C", "success")]
    assert result.exit_code == 0 and result.completed == 3 and result.stopped is None
    assert result.summary_path == tmp_path / "batch-20260930-101500" / "summary.md"
    text = summary_text(result)
    assert "Status: complete" in text and "2 of 3 completed runs (67%)." in text
    assert all(c[1] == result.folder for c in run.calls)  # runs write inside the batch folder


def test_an_exhausted_run_is_recorded_and_the_batch_continues(tmp_path):
    entries = parse_motions("A\nB\nC\n")
    run = scripted(ok(), exhausted(), ok())
    result = run_batch(entries, output_dir=tmp_path, run=run, now=NOW)
    assert len(run.calls) == 3 and result.completed == 2 and result.exit_code == 1
    assert "exhausted (oppose)" in summary_text(result)


def test_budget_reached_between_runs_skips_the_rest(tmp_path):
    entries = parse_motions("A\nB\nC\n")
    run = scripted(ok(tokens=2010), ok(tokens=1985), ok())
    result = run_batch(entries, output_dir=tmp_path, run=run, budget=3000, now=NOW)
    assert len(run.calls) == 2  # run 2 started at 2,010 (< 3,000); run 3 never started
    assert result.results[2] is None and result.skipped == 1 and result.exit_code == 1
    assert result.stopped == "3,995 tokens used, over the 3,000 budget. Skipped 1 motion."
    text = summary_text(result)
    assert "| skipped |" in text and "Status: complete" in text


def test_a_budget_met_exactly_still_stops_before_the_next_debate(tmp_path):
    run = scripted(ok(tokens=3000), ok())
    result = run_batch(parse_motions("A\nB\n"), output_dir=tmp_path, run=run, budget=3000, now=NOW)
    assert len(run.calls) == 1 and "at the 3,000 budget" in result.stopped


def test_an_interrupt_during_run_two_leaves_a_valid_in_progress_summary(tmp_path):
    run = scripted(ok("for"), KeyboardInterrupt(), ok())
    with pytest.raises(KeyboardInterrupt):
        run_batch(parse_motions("A\nB\nC\n"), output_dir=tmp_path, run=run, now=NOW)
    text = (tmp_path / "batch-20260930-101500" / "summary.md").read_text()
    assert "Status: in progress (1 of 3 done)" in text
    assert text.count("| pending |") == 2 and "| A | success | For |" in text


def test_two_batches_in_the_same_second_get_separate_folders(tmp_path):
    a = run_batch(parse_motions("A\n"), output_dir=tmp_path, run=scripted(ok()), now=NOW)
    b = run_batch(parse_motions("A\n"), output_dir=tmp_path, run=scripted(ok()), now=NOW)
    assert a.batch_id == "20260930-101500" and b.batch_id == "20260930-101500-2"
    assert a.summary_path.exists() and b.summary_path.exists()


def test_a_summary_that_cannot_be_written_raises_after_retries(tmp_path, monkeypatch):
    def broken(*a, **k):
        raise WriteFailed("disk full")

    monkeypatch.setattr(batch_module, "write_summary_with_retry", broken)
    with pytest.raises(WriteFailed):
        run_batch(parse_motions("A\n"), output_dir=tmp_path, run=scripted(ok()), now=NOW)


def test_extra_keyword_arguments_reach_every_debate(tmp_path):
    run = scripted(ok(), ok())
    run_batch(parse_motions("A\nB\n"), output_dir=tmp_path, run=run, now=NOW, time_limit=7)
    assert all(c[2] == {"time_limit": 7} for c in run.calls)


def test_with_the_real_debate_and_a_fake_model_runs_land_in_the_batch_folder(tmp_path):
    reasoning = "The proposition made concrete points and the opposition answered them less well. " * 5
    llm = make_stage_llm({
        "You are proposing": ["FOR-TEXT " + "pro " * 200],
        "You are in opposition": ["AGAINST-TEXT " + "con " * 200],
        "Review the arguments": [json.dumps({"winner": "against", "reasoning": reasoning})],
    })
    result = run_batch(parse_motions("Cats | Dogs\n"), output_dir=tmp_path, now=NOW,
                       llm_factory=lambda _m: llm, write_backoff=0)
    assert result.completed == 2 and result.exit_code == 0
    folders = sorted(p.name for p in result.folder.iterdir() if p.is_dir())
    assert len(folders) == 2 and all(f.startswith("2026") or f[0].isdigit() for f in folders)
    for f in folders:
        assert sorted(p.name for p in (result.folder / f).iterdir()) == ["decide.md", "oppose.md", "propose.md"]
    text = summary_text(result)
    assert "Consistent pairs: 0 of 1 analyzed." in text  # against twice: not consistent
