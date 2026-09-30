"""Command line entry point.

    debate "<motion>"                 one debate
    debate --batch FILE [--budget N]  many debates and a summary (feature 001)

Add --check-order to either form to ask the judge a second time with the two
arguments in swapped order (feature 002). It adds about 1,000 tokens per debate.
"""
import argparse
import sys

from dotenv import load_dotenv

from debate_ai.artifacts import ALL_STAGES, WriteFailed
from debate_ai.batch import DEFAULT_BUDGET, BatchInputError, BatchResult, read_motions_file, run_batch
from debate_ai.run import RunResult, StageStats, run_debate

EXIT = {"success": 0, "exhausted": 1, "failed": 2}
LINE_WIDTH = 80
# The report's label column is 8 wide; `decide_swapped` would misalign it.
STAGE_LABELS = {"decide_swapped": "swapped"}


def _line(label: str, s: StageStats, path=None) -> str:
    attempts = f"{s.attempts} attempt{'s' if s.attempts != 1 else ''}"
    tokens = (
        f"{s.total_tokens:,} tokens ({s.prompt_tokens:,} prompt + {s.completion_tokens:,} completion)"
    )
    return f"  {label:<8} {attempts:<12} {tokens}" + (f"  {path}" if path else "")


def format_report(result: RunResult) -> list[str]:
    """Per-stage attempts, tokens and artifact path, then a total."""
    lines = []
    for stage in ALL_STAGES:
        if stage in result.stats or stage in result.artifacts:
            label = STAGE_LABELS.get(stage, stage)
            lines.append(_line(label, result.stats.get(stage, StageStats()), result.artifacts.get(stage)))
    if result.stats:
        lines.append(_line("total", result.total))
    return lines


def _check_tag(result: RunResult) -> str:
    """Short order-check tag for a batch progress line; empty if no check was requested."""
    check = result.order_check
    if check is None:
        return ""
    return {"stable": "stable", "sensitive": "sensitive"}.get(check.status, "no check")


def format_order_check_line(check) -> str:
    """The `Order check:` line for a single debate (stdout, after the winner)."""
    if check.status == "stable":
        return "Order check: stable (the same side won with the arguments in either order)"
    if check.status == "sensitive":
        return (
            f"Order check: order-sensitive (swapped verdict: {check.swapped.winner.capitalize()}; "
            f"the judge favored the argument it read {check.favored})"
        )
    return f"Order check: not completed ({check.reason})"


def format_progress_line(i: int, n: int, motion: str, result: RunResult, width: int = LINE_WIDTH) -> str:
    """`[i/N] <motion> ..... <winner or outcome>  <tokens> tokens`, at most `width` wide.
    A long motion is shortened with `...`; the full motion is in the summary."""
    if result.outcome == "success":
        label = result.verdict.winner.capitalize()
    else:
        label = f"{result.outcome} ({result.stage})" if result.stage else result.outcome
    right = f"{label:<8} {result.total.total_tokens:,} tokens"
    tag = _check_tag(result)
    if tag:
        right += f"  {tag}"
    left = f"[{i}/{n}] {' '.join(motion.split())}"
    room = width - len(right) - 5  # a space, at least three dots, a space
    if len(left) > room:
        left = left[: max(room - 3, 0)].rstrip() + "..."
    dots = "." * max(width - len(left) - len(right) - 2, 3)
    return f"{left} {dots} {right}"


def format_batch_summary_line(result: BatchResult) -> str:
    """`Batch <id>: 2 of 3 completed, 1 exhausted, 8 attempts, 5,470 tokens`."""
    ran = [r for r in result.results if r is not None]
    parts = [f"{result.completed} of {len(result.entries)} completed"]
    for outcome in ("exhausted", "failed"):
        count = sum(1 for r in ran if r.outcome == outcome)
        if count:
            parts.append(f"{count} {outcome}")
    if result.skipped:
        parts.append(f"{result.skipped} skipped")
    attempts = sum(r.total.attempts for r in ran)
    tokens = sum(r.total.total_tokens for r in ran)
    parts += [f"{attempts} attempts", f"{tokens:,} tokens"]
    return f"Batch {result.batch_id}: " + ", ".join(parts)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="debate",
        description='Run a debate on a motion, or a batch of motions with --batch.',
        usage='debate "<motion>" [--check-order] [--output-dir DIR]\n'
        "       debate --batch FILE [--budget TOKENS] [--check-order] [--output-dir DIR]",
    )
    parser.add_argument("motion", nargs="?", help="the motion to debate, in quotes")
    parser.add_argument("--batch", metavar="FILE", help="run every motion in FILE and write a summary")
    parser.add_argument(
        "--budget", type=int, default=None, metavar="TOKENS",
        help=f"with --batch: stop once this many tokens are spent (default {DEFAULT_BUDGET:,})",
    )
    parser.add_argument(
        "--check-order", action="store_true",
        help="ask the judge again with the two arguments in swapped order (about 1,000 extra tokens per debate)",
    )
    parser.add_argument("--output-dir", default="output", help="where run folders go")
    return parser


def _run_single(motion: str, output_dir: str, check_order: bool = False) -> int:
    # Only pass the flag when it was given, so an unflagged run calls run_debate as before.
    extra = {"check_order": True} if check_order else {}
    result = run_debate(motion, output_dir=output_dir, **extra)

    ok = result.outcome == "success"
    out = sys.stdout if ok else sys.stderr
    if ok:
        print(f"Winner: {result.verdict.winner.capitalize()}")
        if result.order_check is not None:
            print(format_order_check_line(result.order_check))
        print(f"Run {result.run_id}:")
    else:
        where = f" at stage '{result.stage}'" if result.stage else ""
        print(f"Run {result.outcome}{where}: {result.reason}", file=out)
    for line in format_report(result):
        print(line, file=out)
    return EXIT[result.outcome]


def _run_batch(path: str, budget: int, output_dir: str, check_order: bool = False) -> int:
    try:
        entries = read_motions_file(path)
    except BatchInputError as e:
        print(f"{e} No debates were run.", file=sys.stderr)
        return 2

    def progress(i, n, entry, result):
        print(format_progress_line(i, n, entry.motion, result), flush=True)

    extra = {"check_order": True} if check_order else {}
    try:
        result = run_batch(
            entries, output_dir=output_dir, budget=budget, run=run_debate,
            on_progress=progress, **extra,
        )
    except WriteFailed as e:
        print(f"Could not write the batch summary: {e}", file=sys.stderr)
        return 2

    if result.stopped:
        print(f"Stopped: {result.stopped}", file=sys.stderr)
    print()
    print(format_batch_summary_line(result))
    print(f"Summary: {result.summary_path}")
    return result.exit_code


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.batch is not None and args.motion is not None:
        parser.error("give either a motion or --batch FILE, not both")
    if args.batch is None and args.motion is None:
        parser.error("give a motion, or --batch FILE")
    if args.batch is None and args.budget is not None:
        parser.error("--budget only applies with --batch")
    if args.budget is not None and args.budget < 1:
        parser.error("--budget must be at least 1")

    load_dotenv()
    if args.batch is not None:
        return _run_batch(args.batch, args.budget or DEFAULT_BUDGET, args.output_dir, args.check_order)
    return _run_single(args.motion, args.output_dir, args.check_order)


if __name__ == "__main__":
    sys.exit(main())
