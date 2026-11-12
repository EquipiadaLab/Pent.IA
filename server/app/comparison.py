"""Validacao continua: compara a partida com a anterior do mesmo alvo."""

from __future__ import annotations

from app.engine.scope import normalize_origin
from app.models import Campaign, CampaignState, Comparison, Status, Verdict

_FINAL = {CampaignState.FINISHED, CampaignState.STOPPED}


def failing(c: Campaign) -> set[str]:
    return {m.test_id for m in c.moves
            if m.status in (Status.FAIL, Status.WARNING) and m.verdict is not Verdict.DISCARDED}


def passing(c: Campaign) -> set[str]:
    return {m.test_id for m in c.moves if m.status is Status.PASS}


def previous_of(current: Campaign, history: list[Campaign]) -> Campaign | None:
    origin = normalize_origin(current.config.origin)
    older = [c for c in history
             if c.id != current.id and c.state in _FINAL and c.created_at < current.created_at
             and normalize_origin(c.config.origin) == origin and c.moves]
    return max(older, key=lambda c: c.created_at, default=None)


def compare(current: Campaign, previous: Campaign) -> Comparison:
    played = {m.test_id for m in current.moves if m.status is not None}
    before, now = failing(previous), failing(current)
    acc_now = current.score.accuracy if current.score else None
    acc_before = previous.score.accuracy if previous.score else None
    return Comparison(
        previous_campaign_id=previous.id,
        previous_accuracy=acc_before,
        accuracy_delta=round(acc_now - acc_before, 1) if acc_now is not None and acc_before is not None else None,
        fixed=sorted((before & played) & passing(current)),
        new=sorted(now - before),
        still_failing=sorted(now & before),
    )
