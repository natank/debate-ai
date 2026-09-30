"""Batch of debates (feature 001): input parsing, the driver, and the summary.

A batch is a driver above the single run. It calls `run_debate` once per motion
and never changes how a debate works.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional


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
