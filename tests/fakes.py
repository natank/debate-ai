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
