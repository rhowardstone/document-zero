"""Where a record goes, decided deterministically.

Five destinations, evaluated in strict precedence:

  REFUSED   never published anywhere, counted in aggregate  (spec §6.3)
  HOLD      published as a hold, with its reason            (spec §6.4)
  OMISSION  heavy coverage, no underlying change            ("what the coverage left out")
  DROP      nothing changed and nobody covered it
  WIRE      a real change, cleanly sourced

Precedence matters. A refusal outranks everything, because it is absolute and not
curable by sourcing. A hold outranks an omission, because uncertainty about whether
a thing is true outranks an observation about how it was covered.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from .recirculation import Verdict


class Placement(Enum):
    REFUSED = "refused"
    HOLD = "hold"
    OMISSION = "omission"
    DROP = "drop"
    WIRE = "wire"


@dataclass(frozen=True)
class PlacementInput:
    delta: object                      # StateDelta
    recirculation: Verdict = Verdict.FRESH
    refused: str | None = None         # refusal gate name, if one fired
    single_root: bool = False
    cascade_survived: bool = True


@dataclass(frozen=True)
class Result:
    placement: Placement
    reason: str | None = None


def classify(i: PlacementInput) -> Result:
    if i.refused:
        return Result(Placement.REFUSED, i.refused)
    if i.recirculation is Verdict.DATE_CONFLICT:
        return Result(Placement.HOLD, "date_conflict")
    if i.single_root:
        return Result(Placement.HOLD, "single_root_multi_source")
    if not i.cascade_survived:
        return Result(Placement.HOLD, "consensus_failure")
    if i.recirculation is Verdict.RECIRCULATION:
        # Heavy coverage with no new claims is itself the finding.
        return Result(Placement.OMISSION, "recirculation")
    if getattr(i.delta, "is_empty", False):
        return Result(Placement.DROP, "no_state_change")
    return Result(Placement.WIRE, None)
