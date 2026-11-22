"""Scripted tool-use scaffold: three fake tools, an oracle memory, and prompts.

This is deliberately *not* an autonomous agent. The controller always calls the
same three tools in the same order, stores their JSON outputs verbatim, and
then asks the LLM one multiple-choice question about that memory. Only the
final question changes between the integration and retrieval tasks; the system
prompt and memory are byte-identical for both.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from jspace_pilot.scenarios import Scenario

ToolOutput = dict[str, Any]


# --------------------------------------------------------------------------- tools
def get_alert(scenario: Scenario) -> ToolOutput:
    """Tool 1: the SIEM alert for the server."""
    return {"server_id": scenario.server_id, "risk": scenario.risk}


def get_asset_info(scenario: Scenario) -> ToolOutput:
    """Tool 2: the asset inventory entry."""
    return {"server_id": scenario.server_id, "critical_service": scenario.critical_service}


def get_backup_info(scenario: Scenario) -> ToolOutput:
    """Tool 3: backup status for several servers (the alerted one plus decoys)."""
    return {"backups": scenario.backup_entries()}


#: Fixed call order. The controller never chooses tools.
TOOL_PIPELINE: tuple[Callable[[Scenario], ToolOutput], ...] = (
    get_alert,
    get_asset_info,
    get_backup_info,
)


# -------------------------------------------------------------------------- memory
@dataclass
class AgentMemory:
    """Ordered record of tool calls and their outputs."""

    entries: list[tuple[str, ToolOutput]] = field(default_factory=list)

    def append(self, tool_name: str, output: ToolOutput) -> None:
        self.entries.append((tool_name, output))

    def render(self) -> str:
        """Text block inserted into the prompt, one line per tool call."""
        return "\n".join(
            f"[{step}] {name} -> {json.dumps(output)}"
            for step, (name, output) in enumerate(self.entries, start=1)
        )


def run_scripted_agent(scenario: Scenario) -> AgentMemory:
    """Steps 2-5 of the controller: call each tool in order and store the output."""
    memory = AgentMemory()
    for tool in TOOL_PIPELINE:
        memory.append(tool.__name__, tool(scenario))
    return memory


# ------------------------------------------------------------------------- prompts
SYSTEM_PROMPT = """You are a security operations assistant. An automated controller has already called three tools and stored their outputs in memory. The alert (tool 1) names one server; tool 3 lists backups for several servers, so always use the entry whose server_id matches the alerted server. Answer the question using only that memory.

DECISION RULES (for the alerted server)
- If risk is not "high": keep monitoring; no containment action is needed yet.
- If risk is "high" and critical_service is false: isolate the server immediately.
- If risk is "high", critical_service is true and its backup_ready is true: fail over to the backup, then isolate the server.
- If risk is "high", critical_service is true and its backup_ready is false: revoke suspicious credentials, increase monitoring, and plan a safe isolation."""

QUESTIONS: dict[str, str] = {
    "integration": (
        "Given the tool outputs and the decision rules, which action is correct for the alerted server? "
        "Choose exactly one option."
    ),
    "retrieval": (
        "Which backup_id does tool 3 (get_backup_info) list for the alerted server? Choose exactly one option."
    ),
}

ANSWER_INSTRUCTION = "Answer with a single letter: A, B, C or D."


def build_user_message(scenario: Scenario, task_type: str, memory: AgentMemory) -> str:
    """Memory block + question + lettered options. Never contains the answer key."""
    options = "\n".join(f"{letter}. {text}" for letter, text in scenario.options(task_type).items())
    return (
        f"MEMORY (tool outputs, in call order)\n{memory.render()}\n\n"
        f"QUESTION\n{QUESTIONS[task_type]}\n{options}\n\n{ANSWER_INSTRUCTION}"
    )


def build_messages(scenario: Scenario, task_type: str) -> list[dict[str, str]]:
    """Chat messages for one trial (step 6 of the controller)."""
    if task_type not in QUESTIONS:
        raise ValueError(f"unknown task_type {task_type!r}")
    memory = run_scripted_agent(scenario)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_message(scenario, task_type, memory)},
    ]
