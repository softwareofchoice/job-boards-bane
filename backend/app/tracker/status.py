"""Application statuses and the changes allowed between them (TRK-4.2)."""

import enum


class Status(enum.StrEnum):
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"


# Applied → Interviewing → Offer or Rejected; Applied → Rejected. Offer and Rejected are final.
TRANSITIONS: dict[Status, tuple[Status, ...]] = {
    Status.APPLIED: (Status.INTERVIEWING, Status.REJECTED),
    Status.INTERVIEWING: (Status.OFFER, Status.REJECTED),
    Status.OFFER: (),
    Status.REJECTED: (),
}

LABELS = {
    Status.APPLIED: "Applied",
    Status.INTERVIEWING: "Interviewing",
    Status.OFFER: "Offer",
    Status.REJECTED: "Rejected",
}

# The longest possible history: applied, interviewing, then offer or rejected.
STAGES = 3


def allowed_next(status: Status) -> tuple[Status, ...]:
    return TRANSITIONS[status]


def can_change(current: Status, new: Status) -> bool:
    return new in TRANSITIONS[current]


def flow_path(history: list[Status]) -> tuple[Status, ...]:
    """A history as a path through the plot's stages, carrying the last status forward
    (TRK-5.1): [applied, rejected] → (applied, rejected, rejected)."""
    path = list(history[:STAGES]) or [Status.APPLIED]
    while len(path) < STAGES:
        path.append(path[-1])
    return tuple(path)
