"""Shared test doubles: a scripted fake LLM that records every call."""
import time

from crewai import Agent, BaseLLM


def flatten(messages) -> str:
    if isinstance(messages, str):
        return messages
    return "\n".join(str(m.get("content", "")) for m in messages)


class ScriptedLLM(BaseLLM):
    """Replies from `replies` in order (the last one repeats) and records prompts.

    `route` maps a marker in the prompt to a reply, for multi-task crews.
    """

    replies: list = ["ok"]
    route: dict = {}
    delay: float = 0.0
    calls: list = []

    def call(self, messages, *args, **kwargs):
        text = flatten(messages)
        self.calls.append(text)
        if self.delay:
            time.sleep(self.delay)
        for marker, reply in self.route.items():
            if marker in text:
                return reply
        return self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]

    def called(self, marker: str) -> int:
        return sum(marker in c for c in self.calls)


def make_llm(**kw) -> ScriptedLLM:
    llm = ScriptedLLM(model="fake", **kw)
    llm.calls = []
    return llm


def make_agent(llm, **kw) -> Agent:
    return Agent(role="r", goal="g", backstory="b", llm=llm, allow_delegation=False, **kw)


class StageLLM(BaseLLM):
    """Per-stage scripts. Each marker in `scripts` has its own reply list, consumed
    one per call (the last repeats). Records which stage each call belonged to."""

    scripts: dict = {}
    calls: list = []
    stages: list = []

    def call(self, messages, *args, **kwargs):
        text = flatten(messages)
        self.calls.append(text)
        for marker, replies in self.scripts.items():
            if marker in text:
                n = sum(s == marker for s in self.stages)
                self.stages.append(marker)
                reply = replies[min(n, len(replies) - 1)]
                # Report usage the way a real provider would: 100 prompt + 40 completion.
                self._track_token_usage_internal(
                    {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140}
                )
                return reply
        raise AssertionError("prompt matched no stage marker")

    def count(self, marker: str) -> int:
        return sum(s == marker for s in self.stages)


def make_stage_llm(scripts: dict) -> StageLLM:
    llm = StageLLM(model="fake", scripts=scripts)
    llm.calls, llm.stages = [], []
    return llm
