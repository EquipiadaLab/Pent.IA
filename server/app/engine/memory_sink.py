"""EventSink em memoria: para testes do Motor, CLI e demos sem banco."""

from __future__ import annotations

from app.models import Approval, AuditEntry, Event, Move


class MemorySink:
    def __init__(self, *, approve: bool = False, stop_after_events: int | None = None) -> None:
        self.events: list[Event] = []
        self.audits: list[AuditEntry] = []
        self.approve = approve
        self.stop_after_events = stop_after_events
        self.stop_flag = False

    async def emit(self, event: Event) -> None:
        event.seq = len(self.events) + 1
        self.events.append(event)

    async def audit(self, entry: AuditEntry) -> None:
        self.audits.append(entry)

    async def should_stop(self) -> bool:
        if self.stop_after_events is not None and len(self.events) >= self.stop_after_events:
            self.stop_flag = True
        return self.stop_flag

    async def wait_approval(self, campaign_id: str, move: Move) -> Approval:
        return Approval.APPROVED if self.approve else Approval.DENIED
