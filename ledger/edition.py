"""Assemble the day's edition from placed, scored records.

Two rules that are easy to get wrong and matter more than the rest:

  - Silent truncation reads as "we covered everything". If the cap drops records,
    the count of what it dropped is published.
  - A refused record appears in no lane, but its refusal is counted and the
    aggregate publishes. What the system will not say is part of the record.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import collections
from .placement import Placement

DEFAULT_CAP = 8


@dataclass
class Edition:
    day: str
    wire: list = field(default_factory=list)
    omissions: list = field(default_factory=list)
    holds: list = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    refusal_summary: dict = field(default_factory=dict)
    publish: bool = True
    publish_blocked_by: str | None = None
    policy_revision: str | None = None

    @property
    def is_empty(self) -> bool:
        return not (self.wire or self.omissions or self.holds)

    def to_dict(self) -> dict:
        return {"day": self.day, "wire": self.wire, "omissions": self.omissions,
                "holds": self.holds, "counts": self.counts,
                "refusal_summary": self.refusal_summary, "publish": self.publish,
                "publish_blocked_by": self.publish_blocked_by,
                "policy_revision": self.policy_revision}


def _placement(r):
    p = r.get("placement")
    return p if isinstance(p, Placement) else Placement(p)


def assemble(records, day: str, policy: dict, policy_revision: str | None = None) -> Edition:
    pub = (policy or {}).get("publication", {}) or {}
    cap = int(pub.get("max_records_per_edition", DEFAULT_CAP))

    # Normalise placement to its string value on the way in: editions are written
    # to the ledger as JSON, so no enum may survive into a lane.
    lanes = collections.defaultdict(list)
    for r in records:
        p = _placement(r)
        lanes[p].append({**r, "placement": p.value})

    wire = sorted(lanes[Placement.WIRE], key=lambda r: -float(r.get("score", 0)))
    capped_out = max(0, len(wire) - cap)
    wire = wire[:cap]

    refused = lanes[Placement.REFUSED]
    counts = {
        "wire": len(wire), "capped_out": capped_out,
        "omissions": len(lanes[Placement.OMISSION]),
        "holds": len(lanes[Placement.HOLD]),
        "refused": len(refused), "dropped": len(lanes[Placement.DROP]),
    }
    summary = dict(collections.Counter(r.get("reason") for r in refused if r.get("reason")))

    blocked = None
    if pub.get("kill_switch"):
        blocked = "kill_switch"
    elif pub.get("dry_run"):
        blocked = "dry_run"

    return Edition(day=day, wire=wire, omissions=lanes[Placement.OMISSION],
                   holds=lanes[Placement.HOLD], counts=counts, refusal_summary=summary,
                   publish=blocked is None, publish_blocked_by=blocked,
                   policy_revision=policy_revision)
