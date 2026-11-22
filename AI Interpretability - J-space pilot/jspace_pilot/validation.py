"""Dataset assertions (spec §3.4). Run these before any model is loaded."""

from __future__ import annotations

import itertools
from collections import Counter

from jspace_pilot.agent import build_messages, get_backup_info
from jspace_pilot.config import TASK_TYPES
from jspace_pilot.scenarios import ACTION_TEXT, ACTIONS, LETTERS, Scenario, expected_action


class DatasetValidationError(AssertionError):
    """Raised when the generated benchmark violates one of its invariants."""


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise DatasetValidationError(message)


def check_decision_rule() -> list[str]:
    """``expected_action`` on every combination of the three input variables."""
    truth = {
        ("high", False, False): "isolate_now",
        ("high", False, True): "isolate_now",
        ("high", True, True): "failover_then_isolate",
        ("high", True, False): "contain_and_plan",
    }
    for risk, critical, backup in itertools.product(("low", "medium", "high"), (False, True), (False, True)):
        want = truth.get((risk, critical, backup), "monitor")
        got = expected_action(risk, critical, backup)
        _check(got == want, f"rule({risk}, {critical}, {backup}) = {got}, expected {want}")
    return ["decision rule correct on all 12 input combinations"]


def validate_scenarios(scenarios: list[Scenario], n_test_per_action: int) -> list[str]:
    """Check every invariant of the benchmark; return a list of passed checks.

    Raises:
        DatasetValidationError: on the first violated invariant.
    """
    passed = check_decision_rule()

    ids = [s.scenario_id for s in scenarios]
    _check(len(ids) == len(set(ids)), "duplicate scenario_id")
    _check(len({s.server_id for s in scenarios}) == len(scenarios), "duplicate server_id")
    _check(len({s.backup_id for s in scenarios}) == len(scenarios), "duplicate backup_id")
    passed.append("scenario, server and backup ids are unique (no dev/test overlap)")

    test_counts = Counter(s.semantic_correct_action for s in scenarios if s.split == "test")
    _check(
        all(test_counts[a] == n_test_per_action for a in ACTIONS),
        f"test split not balanced: {dict(test_counts)}",
    )
    passed.append(f"test split balanced: {n_test_per_action} scenarios per semantic action")

    for s in scenarios:
        _check(
            s.semantic_correct_action == expected_action(s.risk, s.critical_service, s.backup_ready),
            f"{s.scenario_id}: label does not come from expected_action()",
        )
        for task in TASK_TYPES:
            options = s.options(task)
            _check(tuple(options) == LETTERS, f"{s.scenario_id}/{task}: options are not exactly A-D")
            _check(len(set(options.values())) == 4, f"{s.scenario_id}/{task}: duplicate option text")
            correct_text = options[s.correct_letter(task)]
            wanted = ACTION_TEXT[s.semantic_correct_action] if task == "integration" else s.backup_id
            _check(correct_text == wanted, f"{s.scenario_id}/{task}: letter does not match answer")
            n_matching = sum(text == wanted for text in options.values())
            _check(n_matching == 1, f"{s.scenario_id}/{task}: {n_matching} correct options")

        entries = get_backup_info(s)["backups"]
        target = [e for e in entries if e["server_id"] == s.server_id]
        _check(len(target) == 1, f"{s.scenario_id}: alerted server must appear exactly once in tool 3")
        _check(
            target[0]["backup_id"] == s.retrieval_options[s.correct_retrieval_letter]
            and target[0]["backup_ready"] == s.backup_ready,
            f"{s.scenario_id}: retrieval answer / backup_ready do not match tool 3's entry for the alerted server",
        )
        tool3_ids = {e["backup_id"] for e in entries}
        decoys_in_options = sum(
            text in tool3_ids for letter, text in s.retrieval_options.items() if letter != s.correct_retrieval_letter
        )
        _check(decoys_in_options == len(entries) - 1, f"{s.scenario_id}: every decoy backup id should be an option")

        # The answer key itself must never be in the prompt. Options and rules are.
        memory_and_system = {
            task: build_messages(s, task)[1]["content"].split("QUESTION")[0] for task in TASK_TYPES
        }
        _check(
            memory_and_system["integration"] == memory_and_system["retrieval"],
            f"{s.scenario_id}: memory differs between tasks",
        )
        for task in TASK_TYPES:
            text = build_messages(s, task)[1]["content"]
            _check("correct" not in text.split("QUESTION")[0].lower(), f"{s.scenario_id}: answer leak")
            # Internal ids like "failover_then_isolate" must never reach the model
            # ("monitor" is skipped: it is a substring of the option text "monitoring").
            leaked = [a for a in ACTIONS if "_" in a and a in text]
            _check(not leaked, f"{s.scenario_id}/{task}: internal label ids leaked: {leaked}")

    passed += [
        "every label comes from expected_action(), not from a model",
        "every question has exactly 4 options (A-D) and exactly 1 correct option",
        "option letters match the semantic answers after shuffling",
        "retrieval answer = tool 3 entry of the alerted server; decoy ids from memory are wrong options",
        "memory is identical for both tasks of a scenario; no answer key in prompts",
    ]
    return passed
