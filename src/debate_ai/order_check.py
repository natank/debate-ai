"""The order check's result and the comparison (feature 002). Pure: no model calls.

The judge's `winner` is a *side* (for or against), not a position. The official
verdict reads the proposition argument first; the swapped verdict reads the
opposition argument first. If the same side wins both times, the arguments decided
it. If the winner changes, the judge picked whichever argument it read in the same
place both times.
"""
from dataclasses import dataclass
from typing import Literal, Optional

from debate_ai.validation import Verdict


@dataclass(frozen=True)
class OrderCheck:
    status: Literal["stable", "sensitive", "not_completed"]
    swapped: Optional[Verdict] = None  # None when not completed
    favored: Optional[Literal["first", "last"]] = None  # only when sensitive
    reason: Optional[str] = None  # only when not completed


def compare_verdicts(official: Verdict, swapped: Verdict) -> OrderCheck:
    """Compare the official verdict (proposition read first) with the swapped one
    (opposition read first)."""
    if official.winner == swapped.winner:
        return OrderCheck("stable", swapped=swapped)
    # Official for + swapped against: each time, the argument read first won.
    # Official against + swapped for: each time, the argument read last won.
    favored = "first" if official.winner == "for" else "last"
    return OrderCheck("sensitive", swapped=swapped, favored=favored)


def not_completed(reason: str) -> OrderCheck:
    """The swapped verdict was not obtained. The run keeps its official verdict."""
    if not reason or not reason.strip():
        raise ValueError("a not-completed order check needs a reason")
    return OrderCheck("not_completed", reason=reason.strip())
