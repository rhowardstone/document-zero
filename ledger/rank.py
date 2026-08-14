"""Ranking, with every component exposed.

Consequence is irreducibly editorial. The response is not to pretend otherwise
but to publish the components so the judgement can be argued with rather than
trusted. Nothing here is stochastic: given the same inputs the ranking is
identical, which is what makes an edition reproducible from the ledger.
"""
from __future__ import annotations
from dataclasses import dataclass, field

W_NOVELTY = 1.0
W_CONSEQUENCE = 1.6      # deliberately the heaviest term
W_EVIDENCE = 2.0
W_DERIVATION = 2.5       # a conclusion drawn from stored records is the product
QUIET_BONUS = 1.5


@dataclass(frozen=True)
class Score:
    total: float
    components: dict
    distortion: float
    undercovered: bool


def score_item(it: dict) -> Score:
    novelty = W_NOVELTY * float(it.get("material_changes", 0))
    if it.get("beat_was_quiet"):
        novelty += QUIET_BONUS
    consequence = W_CONSEQUENCE * float(it.get("consequence", 0))
    evidence = W_EVIDENCE * float(it.get("evidence", 0.0))
    derivation = W_DERIVATION if it.get("derived") else 0.0

    components = {"novelty": novelty, "consequence": consequence,
                  "evidence": evidence, "derivation": derivation}
    coverage = max(float(it.get("coverage", 0)), 0.0)
    # Attention distortion: consequence over coverage. >1 means the world cares
    # less than it should; <1 means it cares more.
    distortion = float(it.get("consequence", 0)) / (coverage + 1e-9) if coverage else float("inf")
    return Score(sum(components.values()), components, distortion, distortion > 1.0)
