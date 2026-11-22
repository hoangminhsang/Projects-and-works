"""Synthetic SOC incident-response benchmark.

Each scenario is a handful of facts about one server. A deterministic rule
turns three of those facts into the correct action (the *integration* answer);
the backup id reported by tool 3 is the *retrieval* answer. No LLM is involved
in producing any label.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from typing import Any

LETTERS: tuple[str, ...] = ("A", "B", "C", "D")

#: Semantic actions, in a fixed internal order. Option letters are assigned per
#: question (counterbalanced), so "B" means a different action in different prompts.
ACTIONS: tuple[str, ...] = (
    "isolate_now",
    "failover_then_isolate",
    "contain_and_plan",
    "monitor",
)

#: Text shown to the model for each action option.
ACTION_TEXT: dict[str, str] = {
    "isolate_now": "Isolate the server from the network immediately.",
    "failover_then_isolate": "Fail over to the backup, then isolate the server.",
    "contain_and_plan": (
        "Revoke suspicious credentials, increase monitoring, and plan a safe isolation."
    ),
    "monitor": "Keep monitoring; no containment action is needed yet.",
}

_SERVER_PREFIXES = ("FIN", "HR", "WEB", "DB", "MAIL", "OPS", "PAY", "CRM")
_NON_HIGH_RISKS = ("low", "medium")


def expected_action(risk: str, critical_service: bool, backup_ready: bool) -> str:
    """Ground-truth decision rule (the only source of integration labels).

    Args:
        risk: "low", "medium" or "high".
        critical_service: Whether the server runs a business-critical service.
        backup_ready: Whether a ready backup exists for fail-over.

    Returns:
        One of :data:`ACTIONS`.

    Example:
        >>> expected_action("high", True, True)
        'failover_then_isolate'
    """
    if risk != "high":
        return "monitor"
    if not critical_service:
        return "isolate_now"
    return "failover_then_isolate" if backup_ready else "contain_and_plan"


@dataclass(frozen=True)
class Scenario:
    """One benchmark item: the hidden facts plus both multiple-choice questions.

    ``integration_options`` / ``retrieval_options`` map letter -> option text and
    are already in their final order; the ``correct_*_letter`` fields were
    computed from that final order.
    """

    scenario_id: str
    split: str  # "dev" or "test"
    server_id: str
    risk: str
    critical_service: bool
    backup_ready: bool
    backup_id: str
    #: Other servers listed by tool 3: (server_id, backup_ready, backup_id).
    decoy_backups: tuple[tuple[str, bool, str], ...]
    #: Where the alerted server's entry sits in tool 3's list.
    target_backup_index: int
    semantic_correct_action: str
    integration_options: dict[str, str]
    correct_integration_letter: str
    retrieval_options: dict[str, str]
    correct_retrieval_letter: str

    def options(self, task_type: str) -> dict[str, str]:
        return self.integration_options if task_type == "integration" else self.retrieval_options

    def correct_letter(self, task_type: str) -> str:
        if task_type == "integration":
            return self.correct_integration_letter
        return self.correct_retrieval_letter

    def semantic_answer(self, task_type: str) -> str:
        return self.semantic_correct_action if task_type == "integration" else self.backup_id

    def backup_entries(self) -> list[dict[str, Any]]:
        """Tool 3's list: decoys plus the alerted server at ``target_backup_index``."""
        entries = [
            {"server_id": sid, "backup_ready": ready, "backup_id": bid} for sid, ready, bid in self.decoy_backups
        ]
        target = {"server_id": self.server_id, "backup_ready": self.backup_ready, "backup_id": self.backup_id}
        entries.insert(self.target_backup_index, target)
        return entries

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _facts_for_action(action: str, rng: random.Random) -> tuple[str, bool, bool]:
    """Sample (risk, critical_service, backup_ready) that the rule maps to ``action``."""
    if action == "monitor":
        return rng.choice(_NON_HIGH_RISKS), rng.random() < 0.5, rng.random() < 0.5
    if action == "isolate_now":
        return "high", False, rng.random() < 0.5
    if action == "failover_then_isolate":
        return "high", True, True
    if action == "contain_and_plan":
        return "high", True, False
    raise ValueError(f"unknown action {action!r}")


def _place_answer(correct: str, distractors: list[str], letter: str, rng: random.Random) -> dict[str, str]:
    """Put ``correct`` at ``letter`` and the shuffled distractors in the other slots."""
    others = distractors[:]
    rng.shuffle(others)
    slots = iter(others)
    return {slot: (correct if slot == letter else next(slots)) for slot in LETTERS}


def _balanced_letters(n: int, rng: random.Random) -> list[str]:
    """``n`` answer positions with each letter used equally often (+-1), shuffled.

    Counterbalancing stops a model with a position bias ("always A") from
    looking accurate by chance.
    """
    letters = [LETTERS[i % len(LETTERS)] for i in range(n)]
    rng.shuffle(letters)
    return letters


def _letter_of(options: dict[str, str], value: str) -> str:
    matches = [letter for letter, text in options.items() if text == value]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one option equal to {value!r}, got {matches}")
    return matches[0]


def generate_scenarios(
    seed: int = 42, n_dev: int = 8, n_test_per_action: int = 24, n_backup_entries: int = 3
) -> list[Scenario]:
    """Build the dev + held-out test scenarios deterministically.

    The test split is stratified: exactly ``n_test_per_action`` scenarios per
    semantic action. Independently, the position of the correct option is
    counterbalanced within each split and task (each letter is correct equally
    often), and the wrong options fill the remaining slots in random order. The dev split cycles
    through the actions. The alerted server ids and their backup ids are unique
    across the whole dataset, so no scenario is shared between splits.

    Tool 3 lists ``n_backup_entries`` servers: the alerted one plus decoys with
    their own (random) ``backup_ready`` and ``backup_id``. So both tasks must find
    the right server first; for retrieval, two wrong options are decoy backup ids
    that DO appear in memory (a real lookup, not "which id is present at all").

    Args:
        seed: Seed for :class:`random.Random` (the only randomness used).
        n_dev: Number of development scenarios.
        n_test_per_action: Held-out scenarios per semantic action.
        n_backup_entries: Servers listed by tool 3 (>= 1).

    Returns:
        Dev scenarios first, then test scenarios (test order is shuffled).
    """
    rng = random.Random(seed)
    n_total = n_dev + n_test_per_action * len(ACTIONS)

    server_pool = [f"{p}-{n:02d}" for p in _SERVER_PREFIXES for n in range(1, 100)]
    backup_pool = [f"BK-{n:03d}" for n in range(1, 1000)]
    rng.shuffle(server_pool)
    rng.shuffle(backup_pool)
    server_ids = server_pool[:n_total]
    backup_ids = backup_pool[:n_total]
    # Decoys and distractors come from ids never used by an alerted server, so a
    # wrong option can never coincide with any scenario's answer.
    decoy_server_pool = server_pool[n_total:]
    distractor_pool = backup_pool[n_total:]
    n_decoys = n_backup_entries - 1
    if not 0 <= n_decoys <= 3:
        raise ValueError("n_backup_entries must be between 1 and 4")

    dev_actions = [ACTIONS[i % len(ACTIONS)] for i in range(n_dev)]
    test_actions = [a for a in ACTIONS for _ in range(n_test_per_action)]
    rng.shuffle(test_actions)
    plan = [("dev", a) for a in dev_actions] + [("test", a) for a in test_actions]

    answer_slots = {
        (split, task): _balanced_letters(sum(1 for sp, _ in plan if sp == split), rng)
        for split in ("dev", "test")
        for task in ("integration", "retrieval")
    }
    split_position = {"dev": 0, "test": 0}

    scenarios: list[Scenario] = []
    for index, (split, action) in enumerate(plan):
        slot = split_position[split]
        split_position[split] += 1
        risk, critical, backup_ready = _facts_for_action(action, rng)
        assert expected_action(risk, critical, backup_ready) == action

        integration_options = _place_answer(
            ACTION_TEXT[action],
            [ACTION_TEXT[a] for a in ACTIONS if a != action],
            answer_slots[(split, "integration")][slot],
            rng,
        )
        backup_id = backup_ids[index]
        other_ids = rng.sample(distractor_pool, 3)  # first n_decoys go into memory, rest are absent
        decoys = tuple(
            (server, rng.random() < 0.5, other_ids[i])
            for i, server in enumerate(rng.sample(decoy_server_pool, n_decoys))
        )
        retrieval_options = _place_answer(backup_id, other_ids, answer_slots[(split, "retrieval")][slot], rng)

        scenarios.append(
            Scenario(
                scenario_id=f"case_{index + 1:03d}",
                split=split,
                server_id=server_ids[index],
                risk=risk,
                critical_service=critical,
                backup_ready=backup_ready,
                backup_id=backup_id,
                decoy_backups=decoys,
                target_backup_index=rng.randrange(n_backup_entries),
                semantic_correct_action=action,
                integration_options=integration_options,
                correct_integration_letter=_letter_of(integration_options, ACTION_TEXT[action]),
                retrieval_options=retrieval_options,
                correct_retrieval_letter=_letter_of(retrieval_options, backup_id),
            )
        )
    return scenarios


def split_scenarios(scenarios: list[Scenario]) -> tuple[list[Scenario], list[Scenario]]:
    """Return (dev, test)."""
    return (
        [s for s in scenarios if s.split == "dev"],
        [s for s in scenarios if s.split == "test"],
    )
