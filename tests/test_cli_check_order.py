"""Feature 002, subtask 5: the --check-order flag on the CLI (fake model, no network)."""
import pytest

from debate_ai import cli
from debate_ai.order_check import compare_verdicts, not_completed
from debate_ai.run import RunResult, StageStats
from debate_ai.validation import Verdict


def v(w):
    return Verdict(winner=w, reasoning="x")


def checked(winner="against", swapped="against", tokens=3000):
    r = RunResult(
        "success", "m", run_id="r1", verdict=v(winner),
        stats={"decide": StageStats(1, 800, 200, 1000), "decide_swapped": StageStats(1, 800, 200, 1000),
               "propose": StageStats(1, 500, 500, tokens - 2000)},
    )
    r.order_check = compare_verdicts(v(winner), v(swapped))
    return r


def not_checked(reason="the swapped verdict was rejected 3 times"):
    r = checked()
    r.order_check = not_completed(reason)
    return r


def plain(winner="against"):
    return RunResult("success", "m", run_id="r1", verdict=v(winner),
                     stats={"decide": StageStats(1, 800, 200, 1000)})


def motions_file(tmp_path, text="A\nB\nC\n"):
    f = tmp_path / "motions.txt"
    f.write_text(text, encoding="utf-8")
    return str(f)


# ---- the flag reaches the debate only when given ----------------------------------

def test_a_single_run_passes_the_flag_only_when_it_is_given(monkeypatch):
    seen = []

    def fake(motion, **kw):
        seen.append(kw)
        return plain()

    monkeypatch.setattr(cli, "run_debate", fake)
    cli.main(["Cats are better"])
    cli.main(["Cats are better", "--check-order"])
    assert seen == [{"output_dir": "output"}, {"output_dir": "output", "check_order": True}]


def test_a_batch_passes_the_flag_to_every_debate_and_only_when_given(monkeypatch, tmp_path):
    seen = []

    def fake(motion, **kw):
        seen.append(kw.get("check_order"))
        return plain()

    monkeypatch.setattr(cli, "run_debate", fake)
    cli.main(["--batch", motions_file(tmp_path), "--output-dir", str(tmp_path)])
    assert seen == [None, None, None]
    seen.clear()
    cli.main(["--batch", motions_file(tmp_path), "--check-order", "--output-dir", str(tmp_path)])
    assert seen == [True, True, True]


# ---- single run: the Order check line ---------------------------------------------

def test_the_order_check_line_for_a_stable_verdict(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_debate", lambda motion, **k: checked("against", "against"))
    assert cli.main(["m", "--check-order"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "Winner: Against"
    assert lines[1] == "Order check: stable (the same side won with the arguments in either order)"
    assert lines[2].startswith("Run r1:")


@pytest.mark.parametrize("official,swapped,favored", [("against", "for", "last"), ("for", "against", "first")])
def test_the_order_check_line_for_a_sensitive_verdict(monkeypatch, capsys, official, swapped, favored):
    monkeypatch.setattr(cli, "run_debate", lambda motion, **k: checked(official, swapped))
    cli.main(["m", "--check-order"])
    line = capsys.readouterr().out.splitlines()[1]
    assert line == (f"Order check: order-sensitive (swapped verdict: {swapped.capitalize()}; "
                    f"the judge favored the argument it read {favored})")


def test_the_order_check_line_for_a_check_that_did_not_complete(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_debate", lambda motion, **k: not_checked())
    code = cli.main(["m", "--check-order"])
    out = capsys.readouterr()
    assert code == 0 and out.err == ""  # the run succeeded, so the exit code and stream are unchanged
    assert out.out.splitlines()[1] == "Order check: not completed (the swapped verdict was rejected 3 times)"


def test_the_report_shows_the_swapped_stage(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_debate", lambda motion, **k: checked())
    cli.main(["m", "--check-order"])
    out = capsys.readouterr().out
    assert "  swapped  1 attempt" in out and "decide_swapped" not in out


def test_without_the_flag_there_is_no_order_check_output(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_debate", lambda motion, **k: plain())
    cli.main(["m"])
    assert "Order check" not in capsys.readouterr().out


# ---- batch: progress tags, exit codes, summary ------------------------------------

def test_progress_lines_carry_a_tag_when_the_check_ran(monkeypatch, capsys, tmp_path):
    results = iter([checked("against", "against"), checked("against", "for"), not_checked()])
    monkeypatch.setattr(cli, "run_debate", lambda motion, **k: next(results))
    code = cli.main(["--batch", motions_file(tmp_path), "--check-order", "--output-dir", str(tmp_path)])
    lines = capsys.readouterr().out.splitlines()
    assert code == 0
    assert lines[0].endswith("Against  3,000 tokens  stable")
    assert lines[1].endswith("Against  3,000 tokens  sensitive")
    assert lines[2].endswith("Against  3,000 tokens  no check")
    assert all(len(l) <= 80 for l in lines[:3])


def test_progress_lines_have_no_tag_without_the_check(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "run_debate", lambda motion, **k: plain())
    cli.main(["--batch", motions_file(tmp_path, "A\n"), "--output-dir", str(tmp_path)])
    line = capsys.readouterr().out.splitlines()[0]
    assert not line.endswith(("stable", "sensitive", "no check"))


def test_a_long_motion_is_shortened_to_leave_room_for_the_tag():
    long_motion = "Social media does more harm than good for teenagers in modern democratic societies today"
    line = cli.format_progress_line(10, 12, long_motion, checked("against", "for", tokens=12345))
    assert len(line) <= 80 and "..." in line and line.endswith("sensitive")


def test_a_run_that_failed_before_the_check_has_no_tag():
    r = RunResult("exhausted", "m", stage="oppose", stats={"oppose": StageStats(3, 100, 40, 420)})
    line = cli.format_progress_line(2, 3, "Some motion", r)
    assert line.endswith("exhausted (oppose) 420 tokens")


def test_exit_codes_are_unchanged_by_the_check(monkeypatch, capsys, tmp_path):
    stuck = RunResult("exhausted", "m", stage="oppose", stats={"oppose": StageStats(3, 100, 40, 420)})
    results = iter([checked(), stuck, not_checked()])
    monkeypatch.setattr(cli, "run_debate", lambda motion, **k: next(results))
    code = cli.main(["--batch", motions_file(tmp_path), "--check-order", "--output-dir", str(tmp_path)])
    assert code == 1  # one run was exhausted; the not-completed check did not change that
    results = iter([checked(), not_checked(), checked("against", "for")])
    monkeypatch.setattr(cli, "run_debate", lambda motion, **k: next(results))
    assert cli.main(["--batch", motions_file(tmp_path), "--check-order", "--output-dir", str(tmp_path)]) == 0


def test_the_batch_summary_gets_the_order_check_column(monkeypatch, tmp_path):
    results = iter([checked("against", "against"), checked("against", "for")])
    monkeypatch.setattr(cli, "run_debate", lambda motion, **k: next(results))
    cli.main(["--batch", motions_file(tmp_path, "A\nB\n"), "--check-order", "--output-dir", str(tmp_path)])
    text = next(tmp_path.glob("batch-*/summary.md")).read_text()
    assert "| Winner | Order check | Attempts |" in text
    assert "stable" in text and "sensitive (last)" in text and "## Order check" in text


# ---- argument parsing --------------------------------------------------------------

def test_the_flag_needs_a_motion_or_a_batch(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--check-order"])
    assert e.value.code == 2 and "usage:" in capsys.readouterr().err


def test_the_usage_line_shows_the_flag(capsys):
    with pytest.raises(SystemExit):
        cli.main([])
    assert capsys.readouterr().err.count("--check-order") >= 2


def test_budget_still_only_applies_with_batch_even_with_the_flag(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["a motion", "--check-order", "--budget", "5000"])
    assert e.value.code == 2 and "--budget only applies with --batch" in capsys.readouterr().err
