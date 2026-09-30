"""Test 1 (design step 5, section 6): S2 must never see S1's output.

A recording fake LLM replaces the model, so the test captures the exact
messages each call receives and needs no API key or network.
"""
from pathlib import Path

import pytest
import yaml
from crewai import Agent, BaseLLM, Crew, Process, Task

CONFIG = Path(__file__).resolve().parent.parent / "src" / "debate_ai" / "config"
MOTION = "Cats make better pets than dogs"
MARKER_FOR = "ZX-MARKER-FOR-7f3a"
MARKER_AGAINST = "QW-MARKER-AGAINST-91cd"


class RecordingLLM(BaseLLM):
    """Answers with a distinctive marker per side and records every call."""

    calls: list = []

    def call(self, messages, *args, **kwargs):
        text = messages if isinstance(messages, str) else "\n".join(
            str(m.get("content", "")) for m in messages
        )
        if "You are proposing" in text:
            kind, reply = "propose", f"Argument for. {MARKER_FOR}"
        elif "You are in opposition" in text:
            kind, reply = "oppose", f"Argument against. {MARKER_AGAINST}"
        else:
            kind, reply = "decide", "Winner: for. Reasoning."
        self.calls.append({"kind": kind, "text": text})
        return reply


def build_crew(*, isolate: bool, async_propose: bool):
    llm = RecordingLLM(model="fake")
    llm.calls = []  # per-crew record, not shared across tests
    agents_cfg = yaml.safe_load((CONFIG / "agents.yaml").read_text())
    tasks_cfg = yaml.safe_load((CONFIG / "tasks.yaml").read_text())

    agents = {}
    for name, cfg in agents_cfg.items():
        cfg = {**cfg, "llm": llm}
        agents[name] = Agent(**cfg, allow_delegation=False, verbose=False)

    def task(name, **extra):
        cfg = {k: v for k, v in tasks_cfg[name].items() if k not in ("agent", "output_file")}
        return Task(**cfg, agent=agents[tasks_cfg[name]["agent"]], **extra)

    ctx = {"context": []} if isolate else {}
    propose = task("propose", async_execution=async_propose, **ctx)
    oppose = task("oppose", **ctx)
    decide = task("decide", context=[propose, oppose])

    crew = Crew(
        agents=list(agents.values()),
        tasks=[propose, oppose, decide],
        process=Process.sequential,
        verbose=False,
    )
    return crew, llm


def run(**kw):
    crew, llm = build_crew(**kw)
    crew.kickoff(inputs={"motion": MOTION})
    return {c["kind"]: c["text"] for c in llm.calls}


@pytest.mark.parametrize("async_propose", [False, True])
def test_oppose_never_sees_proposition(async_propose):
    prompts = run(isolate=True, async_propose=async_propose)
    assert set(prompts) == {"propose", "oppose", "decide"}
    assert MARKER_FOR not in prompts["oppose"], "S2 prompt contains S1's output"
    assert MARKER_AGAINST not in prompts["propose"]
    # Control: the judge does receive both, so the markers do propagate.
    assert MARKER_FOR in prompts["decide"] and MARKER_AGAINST in prompts["decide"]


def test_detector_catches_default_context_leak():
    """Without context=[], CrewAI relays S1's output to S2. Proves the test can fail."""
    prompts = run(isolate=False, async_propose=False)
    assert MARKER_FOR in prompts["oppose"]
