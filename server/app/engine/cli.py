"""Roda uma campanha pelo terminal (demo/depuracao do Motor, sem API).

    python -m app.engine.cli http://127.0.0.1:8000 --authorized-by "Org" --approve-active
"""

from __future__ import annotations

import argparse
import asyncio
import uuid

from app.engine.memory_sink import MemorySink
from app.engine.runner import run_campaign
from app.engine.scope import utcnow
from app.models import CampaignConfig

ICON = {"brilliant": "!!", "great": "! ", "best": "★ ", "good": "✓ ", "inaccuracy": "?!", "mistake": "? ",
        "miss": "--", "blunder": "??", "inconclusive": ".."}


async def _main(args: argparse.Namespace) -> None:
    config = CampaignConfig(
        origin=args.origin, extra_origins=args.extra_origin, authorized_by=args.authorized_by,
        authorized_at=utcnow(), max_requests_per_second=args.rps,
    )
    sink = MemorySink(approve=args.approve_active)
    campaign = await run_campaign(uuid.uuid4().hex, config, sink)
    print(f"\nPentest Chess — {config.origin}\n")
    for mv in campaign.moves:
        grade = mv.grade.value if mv.grade else f"({mv.approval.value})"
        print(f"{mv.move:>2}. [{ICON.get(grade, '  ')}] {grade:<12} {mv.test_id:<10} {mv.title}")
        if mv.explanation:
            print(f"      {mv.explanation}")
    s = campaign.score
    print(f"\nEstado: {campaign.state.value} | Accuracy: {s.accuracy if s else '-'} | Eval bar: {s.eval_bar if s else '-'}")
    print(f"Requisicoes: {len(sink.audits)} | Bloqueadas: {sum(1 for a in sink.audits if not a.allowed)}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("origin")
    p.add_argument("--authorized-by", required=True)
    p.add_argument("--extra-origin", action="append", default=[])
    p.add_argument("--approve-active", action="store_true", help="aprova automaticamente os lances pendentes")
    p.add_argument("--rps", type=float, default=2.0)
    asyncio.run(_main(p.parse_args()))


if __name__ == "__main__":
    main()
