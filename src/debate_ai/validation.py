"""Shape checks on stage output (design step 4, section 1).

Content checks (side drift, whether the verdict cites real points) are a
recorded, accepted gap in v1.
"""
import re
from typing import Literal

from pydantic import BaseModel, ValidationError

ARGUMENT_MIN_WORDS = 150
ARGUMENT_MAX_WORDS = 350
VERDICT_MIN_WORDS = 50


class Verdict(BaseModel):
    winner: Literal["for", "against"]
    reasoning: str


def word_count(text: str) -> int:
    return len(text.split())


def argument_guardrail(output):
    text = (output.raw or "").strip()
    if not text:
        return False, "Your answer was empty. Write an argument of about 200 to 300 words."
    n = word_count(text)
    if not ARGUMENT_MIN_WORDS <= n <= ARGUMENT_MAX_WORDS:
        return False, (
            f"Your argument has {n} words. Write between {ARGUMENT_MIN_WORDS} and "
            f"{ARGUMENT_MAX_WORDS} words (aim for 200 to 300)."
        )
    return True, text


_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


def parse_verdict(raw: str) -> Verdict:
    """Parse the judge's reply, tolerating a Markdown code fence around the JSON."""
    text = (raw or "").strip()
    fenced = _FENCE.match(text)
    return Verdict.model_validate_json(fenced.group(1) if fenced else text)


def verdict_guardrail(output):
    try:
        verdict = parse_verdict(output.raw)
    except ValidationError as e:
        first = e.errors()[0]
        where = ".".join(str(p) for p in first["loc"]) or "response"
        return False, (
            f"Invalid verdict ({where}: {first['msg']}). Reply with a JSON object "
            'with "winner" set to "for" or "against", and "reasoning".'
        )
    n = word_count(verdict.reasoning)
    if n < VERDICT_MIN_WORDS:
        return False, (
            f"Your reasoning has {n} words. Give at least {VERDICT_MIN_WORDS} words that "
            "refer to specific points in the arguments."
        )
    return True, output.raw
