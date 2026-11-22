from collections import Counter

import pytest

from jspace_pilot.agent import build_messages, run_scripted_agent
from jspace_pilot.scenarios import ACTIONS, generate_scenarios, split_scenarios
from jspace_pilot.validation import DatasetValidationError, check_decision_rule, validate_scenarios


@pytest.fixture(scope="module")
def scenarios():
    return generate_scenarios(seed=42, n_dev=6, n_test_per_action=6)


def test_decision_rule_all_combinations():
    assert check_decision_rule()


def test_sizes_and_balance(scenarios):
    dev, test = split_scenarios(scenarios)
    assert len(dev) == 6 and len(test) == 24
    assert Counter(s.semantic_correct_action for s in test) == {a: 6 for a in ACTIONS}


def test_validation_passes(scenarios):
    assert len(validate_scenarios(scenarios, n_test_per_action=6)) >= 5


def test_deterministic():
    assert generate_scenarios(seed=42) == generate_scenarios(seed=42)
    assert generate_scenarios(seed=42) != generate_scenarios(seed=7)


def test_letters_are_shuffled(scenarios):
    letters = Counter(s.correct_integration_letter for s in scenarios)
    assert len(letters) >= 3, "the correct letter should not be fixed"


def test_memory_identical_across_tasks(scenarios):
    s = scenarios[0]
    integration = build_messages(s, "integration")
    retrieval = build_messages(s, "retrieval")
    assert integration[0] == retrieval[0]
    assert integration[1]["content"].split("QUESTION")[0] == retrieval[1]["content"].split("QUESTION")[0]
    assert run_scripted_agent(s).render() in integration[1]["content"]


def test_validation_catches_bad_label(scenarios):
    import dataclasses

    bad = dataclasses.replace(scenarios[0], correct_integration_letter="A" if scenarios[0].correct_integration_letter != "A" else "B")
    with pytest.raises(DatasetValidationError):
        validate_scenarios([bad, *scenarios[1:]], n_test_per_action=6)
