"""Concept localisation on a toy lens basis."""

import pytest

torch = pytest.importorskip("torch")

from jspace_pilot.concepts import concept_token_ids, locate_concepts  # noqa: E402
from jspace_pilot.interventions import JLensBasis  # noqa: E402


class FakeTokenizer:
    vocab = {"backup": 5, " backup": 6, "Backup": 7, " critical": 9}

    def encode(self, text, add_special_tokens=False):
        return [self.vocab[text]] if text in self.vocab else [100, 101]

    def decode(self, ids):
        inverse = {v: k for k, v in self.vocab.items()}
        return "".join(inverse.get(i, "?") for i in ids)


def test_concept_token_ids_single_token_spellings_only():
    ids = concept_token_ids(FakeTokenizer(), ["backup", "critical", "isolate"])
    assert ids == {5: "backup", 6: "backup", 7: "backup", 9: "critical"}


def test_locate_concepts_marks_sites_where_concept_is_in_top_n():
    d, vocab = 4, 12
    unembed = torch.zeros(vocab, d)
    unembed[5, 0] = 10.0  # token 5 ("backup") reads dimension 0 strongly
    unembed[1, 1] = 10.0  # token 1 (not a concept) reads dimension 1
    basis = JLensBasis({0: torch.eye(d)}, unembed, torch.ones(d), [0], torch.device("cpu"))
    h = torch.tensor([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]])
    protected = torch.tensor([[11], [11], [5]])  # at position 2 the model itself is about to say token 5
    plan = locate_concepts(basis, {0: h}, protected, {5: "backup"}, top_n=1)
    assert plan.site_tokens[0][:, 0].tolist() == [5, -1, -1]  # pos 0 yes; pos 1 not top-1; pos 2 protected
    assert plan.n_sites == {0: 1} and plan.word_counts["backup"] == 1
