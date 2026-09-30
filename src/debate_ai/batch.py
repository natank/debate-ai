"""Batch of debates (feature 001): input parsing, the driver, and the summary.

A batch is a driver above the single run. It calls `run_debate` once per motion
and never changes how a debate works.
"""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal, Optional

from debate_ai.artifacts import write_summary_with_retry
from debate_ai.run import RunResult, run_debate
from debate_ai.summary import build_summary

DEFAULT_BUDGET = 20_000  # tokens; about 10 debates at the ~2,000 measured per debate


class BatchInputError(ValueError):
    """The motions file is unusable. Raised before any model call."""


@dataclass(frozen=True)
class Entry:
    """One motion to debate. A pair contributes two entries sharing `pair`."""

    motion: str
    pair: Optional[int] = None  # index of the pair this belongs to, if any
    side: Optional[Literal["A", "B"]] = None  # which half of the pair


def parse_motions(text: str) -> list[Entry]:
    """Parse the motions file contents.

    One entry per line; blank lines and lines starting with `#` are ignored.
    `Motion A | Motion B` declares a pair of opposite motions. The whole file is
    validated first, so a bad line never wastes a model call.
    """
    entries: list[Entry] = []
    pairs = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        bars = line.count("|")
        if bars > 1:
            raise BatchInputError(f'Line {number}: a pair uses one "|" (found {bars}).')
        if bars == 1:
            a, b = (part.strip() for part in line.split("|"))
            if not a or not b:
                raise BatchInputError(
                    f'Line {number}: a pair needs a motion on both sides of the "|".'
                )
            entries.append(Entry(a, pair=pairs, side="A"))
            entries.append(Entry(b, pair=pairs, side="B"))
            pairs += 1
        else:
            entries.append(Entry(line))
    if not entries:
        raise BatchInputError("The file has no motions.")
    return entries


def read_motions_file(path) -> list[Entry]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise BatchInputError(f"Cannot read {path}: {e}") from e
    return parse_motions(text)


@dataclass
class BatchResult:
    batch_id: str
    folder: Path
    summary_path: Path
    entries: list
    results: list  # Optional[RunResult] per entry; None if it did not run
    stopped: Optional[str] = None  # why the batch stopped early, if it did

    @property
    def completed(self) -> int:
        return sum(1 for r in self.results if r is not None and r.outcome == "success")

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r is None)

    @property
    def exit_code(self) -> int:
        """0 if every motion completed; 1 if any run was exhausted or failed, or any
        motion was skipped. (2, for invalid input or an unwritable summary, is the CLI's.)"""
        return 0 if self.completed == len(self.entries) else 1


def make_batch_id(now: Optional[datetime] = None) -> str:
    return f"{(now or datetime.now()):%Y%m%d-%H%M%S}"


def unique_batch_id(output_dir, batch_id: str) -> str:
    candidate, n = batch_id, 1
    while (Path(output_dir) / f"batch-{candidate}").exists():
        n += 1
        candidate = f"{batch_id}-{n}"
    return candidate


def run_batch(
    entries: list,
    *,
    output_dir="output",
    budget: int = DEFAULT_BUDGET,
    run: Callable[..., RunResult] = run_debate,
    on_progress: Optional[Callable[[int, int, Entry, RunResult], None]] = None,
    now: Optional[datetime] = None,
    write_backoff: float = 0.2,
    **run_kwargs,
) -> BatchResult:
    """Run each entry as an ordinary single debate, one after another.

    The budget is checked between debates against tokens spent so far, so a batch can
    pass it by at most one debate. A run that is exhausted or failed does not stop the
    batch. The summary is rewritten after every debate, so an interrupted batch still
    leaves a valid one. `run` and `run_kwargs` let tests inject a fake debate or model.
    """
    n = len(entries)
    batch_id = unique_batch_id(output_dir, make_batch_id(now))
    folder = Path(output_dir) / f"batch-{batch_id}"
    results: list = [None] * n
    spent = 0
    stopped = None

    def save(complete: bool):
        text = build_summary(batch_id, entries, results, complete=complete)
        return write_summary_with_retry(output_dir, batch_id, text, backoff=write_backoff)

    for i, entry in enumerate(entries):
        if spent >= budget:
            left = n - i
            relation = "over" if spent > budget else "at"
            stopped = (
                f"{spent:,} tokens used, {relation} the {budget:,} budget. "
                f"Skipped {left} motion{'s' if left != 1 else ''}."
            )
            break
        result = run(entry.motion, output_dir=folder, **run_kwargs)
        results[i] = result
        spent += result.total.total_tokens
        if on_progress:
            on_progress(i + 1, n, entry, result)
        save(complete=False)

    artifact = save(complete=True)
    return BatchResult(batch_id, folder, artifact.path, list(entries), results, stopped)
