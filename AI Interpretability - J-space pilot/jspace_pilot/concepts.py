"""Observe first, then intervene: locate task concepts in the J-lens.

A clean (unedited) forward pass gives the residual ``h`` at every layer of the
band. At each (layer, position) we read the lens top-n tokens. If any
pre-registered concept token is among them (and it is not one of the clean
model's own next-token guesses at that position), that site is added to the
*concept plan* with those token ids. C1 then removes exactly those directions at
exactly those sites; C2 adds random vectors of the same size at the same sites.
"""

from __future__ import annotations

import string
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

import torch

from jspace_pilot.interventions import JLensBasis


def concept_token_ids(tokenizer: Any, words: Iterable[str]) -> dict[int, str]:
    """Single-token spellings of each concept word -> {token_id: word}.

    Tries "word", " word", "Word", " Word". Words with no single-token spelling
    are skipped (and reported by :func:`describe_concepts`).
    """
    ids: dict[int, str] = {}
    for word in words:
        for spelling in {word, f" {word}", word.capitalize(), f" {word.capitalize()}"}:
            encoded = tokenizer.encode(spelling, add_special_tokens=False)
            if len(encoded) == 1:
                ids.setdefault(encoded[0], word)
    return ids


def describe_concepts(tokenizer: Any, words: Iterable[str], ids: Mapping[int, str]) -> dict[str, list[str]]:
    """{word: [token strings found]} including words with none (empty list)."""
    found: dict[str, list[str]] = {w: [] for w in words}
    for token_id, word in ids.items():
        found[word].append(repr(tokenizer.decode([token_id])))
    return found


def non_content_token_ids(tokenizer: Any) -> torch.Tensor:
    """Special tokens and tokens that decode to only whitespace / punctuation.

    Used by the "topk" selection so that the top-k are content tokens rather than
    end-of-message or formatting signals (the v1 failure mode).
    """
    special = set(getattr(tokenizer, "all_special_ids", []) or [])
    added = getattr(tokenizer, "added_tokens_decoder", {}) or {}
    special.update(int(i) for i in added)
    junk = set(string.punctuation) | set(string.whitespace) | {"…", "–", "—", "“", "”", "‘", "’"}
    bad = []
    for token_id in range(len(tokenizer)):
        if token_id in special:
            bad.append(token_id)
            continue
        text = tokenizer.decode([token_id])
        if not text.strip() or all(ch in junk for ch in text):
            bad.append(token_id)
    return torch.tensor(sorted(bad), dtype=torch.long)


@dataclass
class ConceptPlan:
    """Which concept directions to remove where, for one prompt.

    ``site_tokens[layer]`` is ``[P, K]`` (P = editable positions, -1 = padding);
    a row of all -1 means "do not touch this position at this layer".
    """

    site_tokens: dict[int, torch.Tensor]
    n_sites: dict[int, int]  # positions with >= 1 concept, per layer
    word_counts: Counter = field(default_factory=Counter)  # concept word -> number of (layer, position) hits

    @property
    def total_sites(self) -> int:
        return sum(self.n_sites.values())

    def summary(self, top: int = 6) -> str:
        return ", ".join(f"{w}:{c}" for w, c in self.word_counts.most_common(top)) or "(none)"


@torch.no_grad()
def locate_concepts(
    basis: JLensBasis,
    layer_residuals: Mapping[int, torch.Tensor],
    protected: torch.Tensor,
    concept_ids: Mapping[int, str],
    top_n: int,
) -> ConceptPlan:
    """Build the concept plan from CLEAN residuals.

    Args:
        basis: J-lens basis for the band layers.
        layer_residuals: ``{layer: [P, d]}`` clean residuals at editable positions.
        protected: ``[P, n]`` clean next-token guesses (never ablated).
        concept_ids: ``{token_id: word}`` from :func:`concept_token_ids`.
        top_n: a concept counts as present if it is in the lens top-n.
    """
    ids_tensor = torch.tensor(sorted(concept_ids), device=basis.device)
    site_tokens: dict[int, torch.Tensor] = {}
    n_sites: dict[int, int] = {}
    counts: Counter = Counter()
    for layer, h in layer_residuals.items():
        top = basis.top_tokens(h.to(basis.device, torch.float32), layer, top_n, protected)  # [P, N]
        present = torch.isin(top, ids_tensor)  # [P, N]
        k_max = int(present.sum(dim=1).max().item()) if len(top) else 0
        tokens = torch.full((len(top), max(k_max, 1)), -1, dtype=torch.long)
        for row in present.any(dim=1).nonzero().flatten().tolist():
            hits = top[row][present[row]].tolist()
            tokens[row, : len(hits)] = torch.tensor(hits)
            counts.update(concept_ids[t] for t in hits)
        site_tokens[layer] = tokens
        n_sites[layer] = int(present.any(dim=1).sum())
    return ConceptPlan(site_tokens=site_tokens, n_sites=n_sites, word_counts=counts)
