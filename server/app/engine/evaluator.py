"""Evaluator: nota estilo Chess.com + score. 100% deterministico (sem LLM)."""

from __future__ import annotations

from app.models import Grade, Move, Score, Severity, Status

# Matriz status x severidade (corrige o problema #2 do dossie).
_FAIL = {Severity.HIGH: Grade.BLUNDER, Severity.MEDIUM: Grade.MISTAKE, Severity.LOW: Grade.INACCURACY}
_WARN = {Severity.HIGH: Grade.MISTAKE, Severity.MEDIUM: Grade.INACCURACY, Severity.LOW: Grade.INACCURACY}

# Pontos por nota; inconclusive/miss ficam FORA do score.
POINTS: dict[Grade, float] = {
    Grade.BRILLIANT: 100, Grade.GREAT: 100, Grade.BEST: 100, Grade.GOOD: 95,
    Grade.INACCURACY: 60, Grade.MISTAKE: 30, Grade.BLUNDER: 0,
}
WEIGHT = {Severity.HIGH: 3, Severity.MEDIUM: 2, Severity.LOW: 1}


def grade_for(status: Status, severity: Severity, exemplary: bool = False) -> Grade:
    if status is Status.INCONCLUSIVE:
        return Grade.INCONCLUSIVE
    if status is Status.PASS:
        if exemplary:  # defesa acima do padrao
            return Grade.BRILLIANT if severity is Severity.HIGH else Grade.GREAT
        return Grade.BEST if severity is Severity.HIGH else Grade.GOOD
    if status is Status.WARNING:
        return _WARN[severity]
    return _FAIL[severity]


def compute_score(moves: list[Move]) -> Score:
    counts: dict[Grade, int] = {}
    total = weighted = 0.0
    for mv in moves:
        if mv.grade is None:
            continue
        counts[mv.grade] = counts.get(mv.grade, 0) + 1
        if mv.status is None or mv.grade not in POINTS:
            continue
        w = WEIGHT[mv.severity]
        total += w
        weighted += w * POINTS[mv.grade]
    if total == 0:
        return Score(accuracy=0.0, eval_bar=0.0, counts=counts)
    accuracy = round(weighted / total, 1)
    return Score(accuracy=accuracy, eval_bar=round(accuracy * 2 - 100, 1), counts=counts)
