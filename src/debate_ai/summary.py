"""Build a batch's summary.md (feature 001). Pure: no model calls, no file writes."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

from debate_ai.run import RunResult

if TYPE_CHECKING:  # batch.py imports this module, so import Entry for typing only
    from debate_ai.batch import Entry

SMALL_SAMPLE = 10  # fewer completed runs than this cannot support a conclusion

LIMIT_SENTENCE = (
    'A skew toward "for" cannot be told apart from an ordering effect: the judge '
    "always sees the proposition first. These are rates, not a finding of bias."
)


def _winner(result: Optional[RunResult]) -> str:
    if result is not None and result.outcome == "success":
        return result.verdict.winner
    return ""


def _outcome(result: Optional[RunResult], complete: bool) -> str:
    if result is None:
        return "skipped" if complete else "pending"
    if result.outcome == "success":
        return "success"
    return f"{result.outcome} ({result.stage})" if result.stage else result.outcome


def _check_cell(result: Optional[RunResult]) -> str:
    check = result.order_check if result is not None else None
    if check is None:
        return "-"
    if check.status == "sensitive":
        return f"sensitive ({check.favored})"
    return "not completed" if check.status == "not_completed" else check.status


def _order_check_section(completed: list) -> list:
    """The `Order check` section, or nothing if no completed debate was checked."""
    checks = [r.order_check for r in completed if r.order_check is not None]
    stable = sum(1 for c in checks if c.status == "stable")
    sensitive = [c for c in checks if c.status == "sensitive"]
    not_done = sum(1 for c in checks if c.status == "not_completed")
    first = sum(1 for c in sensitive if c.favored == "first")
    last = len(sensitive) - first
    return [
        "",
        "## Order check",
        f"Checked {stable + len(sensitive)} of {len(completed)} completed debates. "
        f"Order-stable: {stable}. Order-sensitive: {len(sensitive)} "
        f"(favored the first-read argument: {first}; the last-read: {last}). "
        f"Not completed: {not_done}.",
    ]


def _closing_paragraph(completed: list) -> str:
    """With order-check data the closing paragraph says what the data shows. Without any
    completed check it is the fixed FR-8.6 sentence."""
    checks = [r.order_check for r in completed if r.order_check is not None]
    checked = [c for c in checks if c.status != "not_completed"]
    if not checked:
        return LIMIT_SENTENCE
    n = len(checked)
    changed = sum(1 for c in checked if c.status == "sensitive")
    if changed == 0:
        lead = (
            f"In none of the {n} checked debate{'s' if n != 1 else ''} did the winner change "
            "when the arguments were swapped: the same side won in both orders each time."
        )
    else:
        subject = (
            f"In {changed} of {n} checked debates" if changed < n
            else ("In the only checked debate" if n == 1 else f"In all {n} checked debates")
        )
        lead = (
            f"{subject} the winner changed when the arguments were swapped. That is the "
            "reading order or ordinary variation between judge calls; this check cannot "
            "separate the two."
        )
        if changed < n:
            lead += " In the rest, the same side won in both orders."
    return (
        f"{lead} The for-win rate above uses the official verdict only. "
        "These are rates, not a finding of bias."
    )


def _reading(a_entry: Entry, b_entry: Entry, a: Optional[RunResult], b: Optional[RunResult]):
    """Returns (consistent, text). consistent is None when the pair is not analyzed."""
    wa, wb = _winner(a), _winner(b)
    if not wa or not wb:
        return None, "Not analyzed (a debate did not complete)"
    if wa != wb:
        picked = a_entry.motion if wa == "for" else b_entry.motion
        return True, f'Consistent: sided with "{picked}" both times'
    side = "proposition" if wa == "for" else "opposition"
    return False, f"Not consistent: sided with the {side} both times"


def build_summary(
    batch_id: str,
    entries: Sequence[Entry],
    results: Sequence[Optional[RunResult]],
    *,
    complete: bool,
) -> str:
    """`results[i]` is the result for `entries[i]`, or None if it did not run."""
    n = len(entries)
    ran = [r for r in results if r is not None]
    completed = [r for r in ran if r.outcome == "success"]
    attempts = sum(r.total.attempts for r in ran)
    prompt = sum(r.total.prompt_tokens for r in ran)
    completion = sum(r.total.completion_tokens for r in ran)
    tokens = sum(r.total.total_tokens for r in ran)

    status = "complete" if complete else f"in progress ({len(ran)} of {n} done)"
    # The Order check column, section and closing paragraph appear only when the check
    # was requested. Without it the summary is exactly what it was before feature 002.
    checked_run = any(r is not None and r.order_check is not None for r in ran)
    lines = [
        "# Batch summary",
        f"Batch {batch_id} · {n} motion{'s' if n != 1 else ''} · {len(completed)} completed"
        f" · {tokens:,} tokens · {attempts} attempts",
        f"Status: {status}",
        "",
        "| # | Motion | Outcome | Winner |" + (" Order check |" if checked_run else "")
        + " Attempts | Tokens | Run folder |",
        "|---|---|---|---|" + ("---|" if checked_run else "") + "---|---|---|",
    ]
    for i, (entry, r) in enumerate(zip(entries, results), start=1):
        winner = _winner(r).capitalize() or "-"
        att = str(r.total.attempts) if r is not None else "-"
        tok = f"{r.total.total_tokens:,}" if r is not None else "-"
        folder = (r.run_id if r is not None and r.run_id else "-")
        check_cell = f" {_check_cell(r)} |" if checked_run else ""
        lines.append(
            f"| {i} | {entry.motion} | {_outcome(r, complete)} | {winner} |{check_cell} "
            f"{att} | {tok} | {folder} |"
        )

    for_wins = sum(1 for r in completed if r.verdict.winner == "for")
    lines += ["", "## For-win rate"]
    if completed:
        rate = f"{for_wins} of {len(completed)} completed runs ({round(100 * for_wins / len(completed))}%)."
        if len(completed) < SMALL_SAMPLE:
            rate += " Too few runs to conclude anything."
        lines.append(rate)
    else:
        lines.append("No completed runs. Too few runs to conclude anything.")
    not_done = {"exhausted": 0, "failed": 0}
    for r in ran:
        if r.outcome in not_done:
            not_done[r.outcome] += 1
    unrun = n - len(ran)
    extra = [f"{v} {k}" for k, v in not_done.items() if v]
    if unrun:
        extra.append(f"{unrun} {'skipped' if complete else 'pending'}")
    if extra:
        lines += ["", "Not counted in the rate: " + ", ".join(extra) + "."]

    pair_ids = sorted({e.pair for e in entries if e.pair is not None})
    if pair_ids:
        lines += ["", "## Pairs", "| Pair | Result on A | Result on B | Reading |", "|---|---|---|---|"]
        analyzed = consistent = 0
        inconsistent = []
        for p in pair_ids:
            ia = next(i for i, e in enumerate(entries) if e.pair == p and e.side == "A")
            ib = next(i for i, e in enumerate(entries) if e.pair == p and e.side == "B")
            a, b = results[ia], results[ib]
            ok, text = _reading(entries[ia], entries[ib], a, b)
            label = f"{entries[ia].motion} / {entries[ib].motion}"
            res = lambda r: _winner(r).capitalize() or _outcome(r, complete)  # noqa: E731
            lines.append(f"| {label} | {res(a)} | {res(b)} | {text} |")
            if ok is not None:
                analyzed += 1
                consistent += ok
                if not ok:
                    inconsistent.append(label)
        lines += ["", f"Consistent pairs: {consistent} of {analyzed} analyzed."]
        if inconsistent:
            lines.append("Not consistent: " + "; ".join(inconsistent) + ".")

    if checked_run:
        lines += _order_check_section(completed)

    lines += [
        "",
        "## Totals",
        f"{attempts} attempts, {tokens:,} tokens ({prompt:,} prompt + {completion:,} completion).",
        "",
        "## Read this carefully",
        _closing_paragraph(completed) if checked_run else LIMIT_SENTENCE,
        "",
    ]
    return "\n".join(lines)
