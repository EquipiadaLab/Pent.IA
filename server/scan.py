"""Pentest Chess pelo terminal: envia um site, ve o agente jogar ao vivo, recebe o relatorio.

Exemplos (dentro da pasta server):
    python scan.py --lab                      # sobe o site de treino e testa ele
    python scan.py --lab --hardened           # site de treino ja corrigido ("revanche")
    python scan.py --lab --automatico         # execucao automatica (usa so a pre-aprovacao do .env)
    python scan.py --lab --sem-ia             # so regras (sem Bedrock)
    python scan.py https://alvo-autorizado.com --por "Organizacao do hackathon"

So roda contra alvos de AUTHORIZED_TARGETS (.env) ou enderecos locais.
O relatorio vai para server/reports/ em Markdown e JSON (fora do Git).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "devtools"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from app.authorization import explain_refusal, is_authorized  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.engine.memory_sink import MemorySink  # noqa: E402
from app.engine.runner import run_campaign  # noqa: E402
from app.engine.scope import utcnow  # noqa: E402
from app.explainer import apply_explanations, build_summary  # noqa: E402
from app.models import Approval, Campaign, CampaignConfig, Event, EventType, ExecutiveSummary, Move  # noqa: E402

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

ROTULO = {
    "brilliant": "Brilhante", "great": "Otimo", "best": "Melhor lance", "good": "Bom",
    "inaccuracy": "Imprecisao", "mistake": "Erro", "miss": "Nao executado", "blunder": "ERRO GRAVE",
    "inconclusive": "Inconclusivo",
}
ICONE = {"brilliant": "!!", "great": "! ", "best": "* ", "good": "+ ", "inaccuracy": "?!",
         "mistake": "? ", "miss": "--", "blunder": "??", "inconclusive": ".."}
VEREDITO = {"confirmed": "confirmado", "discarded": "DESCARTADO", "inconclusive": "nao reconfirmado"}


# ----------------------------------------------------------------- ao vivo
class LiveSink(MemorySink):
    """Mostra o plano da IA ANTES de cada lance, o resultado depois, e pergunta aprovacoes."""

    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode  # perguntar | aprovar | negar

    async def emit(self, event: Event) -> None:
        await super().emit(event)
        m, d = event.move, event.data
        if event.type is EventType.CAMPAIGN_STARTED:
            quem = "IA (Bedrock)" if d.get("planner") == "ai" else "regras do catalogo"
            print(f"  Planejamento: {quem}" + (" | execucao AUTOMATICA" if d.get("unattended") else "") + "\n")
        elif event.type is EventType.MOVE_PLANNED and m and m.plan:
            quem = "IA" if m.plan.source == "ai" else "regras"
            print(f"  {m.move:>2}. Plano ({quem}): {m.title}")
            print(f"      hipotese : {m.plan.hypothesis}")
            print(f"      esperado : {m.plan.expected_result}")
            if m.plan.rationale:
                print(f"      porque   : {m.plan.rationale}")
        elif event.type is EventType.APPROVAL_RESOLVED and "actor" in d:
            ok = d.get("approval") == "approved"
            print(f"      [{'ok' if ok else 'xx'}] {'Aprovado' if ok else 'Negado'} por {d['actor']}")
        elif event.type is EventType.FINDING_CREATED and m:
            g = m.grade.value if m.grade else "inconclusive"
            ver = f" ({VEREDITO[m.verdict.value]})" if m.verdict else ""
            print(f"      => [{ICONE[g]}] {ROTULO[g]}{ver}: {m.explanation}")
        elif event.type is EventType.SCORE_UPDATED and "eval_bar" in d and len(self.events) % 2 == 0:
            print("      " + barra(d["eval_bar"]) + "\n")
        elif event.type is EventType.SCOPE_BLOCKED:
            print(f"  [BLOQUEADO] {d.get('reason')}")

    async def wait_approval(self, campaign_id: str, move: Move) -> Approval:
        if self.mode == "aprovar":
            ok = True
        elif self.mode == "negar":
            ok = False
        else:
            resp = await asyncio.to_thread(input, f"      >> Teste sensivel: '{move.title}'. Aprovar? [s/N] ")
            ok = resp.strip().lower() in ("s", "sim", "y", "yes")
        print(f"      [{'ok' if ok else 'xx'}] {'Aprovado' if ok else 'Negado'} pelo operador")
        return Approval.APPROVED if ok else Approval.DENIED


def barra(eval_bar: float, largura: int = 30) -> str:
    """Barra de avaliacao: cheia = site seguro, vazia = site fragil."""
    cheio = round((eval_bar + 100) / 200 * largura)
    return "[" + "#" * cheio + "." * (largura - cheio) + f"] avaliacao {eval_bar:+.0f}"


# ----------------------------------------------------------------- relatorio
def markdown(c: Campaign, sink: MemorySink, s: ExecutiveSummary, inicio: datetime) -> str:
    sc = c.score
    contagem: dict[str, int] = {}
    for m in c.moves:
        chave = m.grade.value if m.grade else f"nao executado ({m.approval.value})"
        contagem[chave] = contagem.get(chave, 0) + 1
    L = [
        f"# Game Review — {c.config.origin}", "",
        f"- **Data:** {inicio:%d/%m/%Y %H:%M} UTC · **Duracao:** {(c.finished_at - inicio).total_seconds():.1f}s",
        f"- **Autorizado por:** {c.config.authorized_by}"
        + (" · **Execucao automatica**" if c.config.unattended else ""),
        f"- **Estado:** {c.state.value} · **Requisicoes:** {sum(1 for a in sink.audits if a.allowed)}"
        f" · **Bloqueadas:** {sum(1 for a in sink.audits if not a.allowed)}", "",
        "## Placar", "",
        f"**Accuracy: {sc.accuracy}/100** · Barra de avaliacao: {sc.eval_bar:+.0f} · **Risco: {s.risk_level}**", "",
        "| Nota | Quantidade |", "|---|---|",
        *[f"| {ROTULO.get(k, k)} | {v} |" for k, v in contagem.items()], "",
        "## Resumo executivo", f"_Gerado por: {'IA (Claude via Bedrock)' if s.source == 'ai' else 'regras'}_", "",
        f"**{s.headline}**", "", s.plain_language, "",
        "**Principais riscos:**", *[f"{i}. Lance {r.move} — {r.title}: {r.why}" for i, r in enumerate(s.top_risks, 1)],
        "", "**Proximos passos:**", *[f"{i}. {p}" for i, p in enumerate(s.next_steps, 1)], "",
        "## Lances", "",
    ]
    for m in c.moves:
        g = m.grade.value if m.grade else None
        L += [f"### {m.move}. {m.title} — {ROTULO.get(g, 'Nao executado (' + m.approval.value + ')')}", "",
              f"- **Referencia:** {m.wstg} · {m.owasp_top10} · fase {m.phase.value} · perfil {m.profile.value}"]
        if m.plan:
            L += [f"- **Plano ({'IA' if m.plan.source == 'ai' else 'regras'}):** hipotese: {m.plan.hypothesis} · "
                  f"acao: {m.plan.action} · esperado: {m.plan.expected_result} · parada: {m.plan.stop_condition}"]
        if m.status:
            L += [f"- **Resultado:** {m.status.value} · severidade {m.severity.value} · confianca "
                  f"{m.confidence.value if m.confidence else '-'}"
                  + (f" · **{VEREDITO[m.verdict.value]}**" if m.verdict else ""),
                  f"- **O que encontramos:** {m.explanation}"]
            if m.impact and m.status.value in ("fail", "warning"):
                L.append(f"- **Impacto:** {m.impact}")
            if m.ai_explanation:
                L.append(f"- **Comentario do treinador (IA, aprovado pelo juiz):** {m.ai_explanation}"
                         if m.ai_review else f"- **Comentario do treinador (IA):** {m.ai_explanation}")
            elif m.ai_review and m.ai_review.verdict == "rejected":
                L.append(f"- _Comentario da IA reprovado pelo juiz: {'; '.join(m.ai_review.issues) or 'sem detalhe'}_")
            if m.recommendation:
                L.append(f"- **Melhor lance (correcao):** `{m.recommendation}`")
            for ev in m.evidence:
                L.append(f"- **Evidencia `{ev.id}`:** `{ev.request}` -> {ev.response_status or '-'}"
                         + (f" · {ev.note}" if ev.note else ""))
            if m.reproduce:
                L += ["- **Como reproduzir:**", "  ```", *[f"  {p}" for p in m.reproduce], "  ```"]
        L.append("")
    L += ["## Trilha de auditoria", "", "| Horario | Metodo | URL | Permitido | Status | Motivo |",
          "|---|---|---|---|---|---|"]
    L += [f"| {a.at:%H:%M:%S} | {a.method} | {a.url} | {'sim' if a.allowed else 'NAO'} | "
          f"{a.status_code or '-'} | {a.reason or ''} |" for a in sink.audits]
    L += ["", "> Escopo do MVP: configuracao HTTP/TLS e exposicao de arquivos. Nao cobre login, "
          "autorizacao, injecao nem logica de negocio. Accuracy nao significa \"% seguro\"."]
    return "\n".join(L)


# ----------------------------------------------------------------- main
def _llms(sem_ia: bool):
    if sem_ia:
        return None, None
    s = load_settings()
    if not s.bedrock_model_id:
        return None, None
    from app.llm_bedrock import BedrockLLM

    return BedrockLLM(model_id=s.planner_model_id, region=s.aws_region), BedrockLLM(
        model_id=s.bedrock_model_id, region=s.aws_region)


async def principal(a: argparse.Namespace) -> int:
    servidor = None
    alvo = a.alvo
    if a.lab:
        import lab_server

        servidor, alvo = lab_server.start(hardened=a.hardened)
    if not alvo:
        print("Informe o site (ex.: python scan.py https://alvo.com) ou use --lab.")
        return 2
    if not is_authorized(alvo):
        print("\n  RECUSADO: " + explain_refusal(alvo))
        return 3

    config = CampaignConfig(origin=alvo, extra_origins=a.extra, authorized_by=a.por, authorized_at=utcnow(),
                            max_requests_per_second=a.rps, unattended=a.automatico)
    modo = "aprovar" if a.aprovar_tudo else "negar" if a.negar_tudo else "perguntar"
    sink = LiveSink(modo)
    planner_llm, llm = _llms(a.sem_ia)
    inicio, t0 = utcnow(), time.monotonic()
    print(f"\nPentest Chess — partida contra {alvo}")
    try:
        campanha = await run_campaign(uuid.uuid4().hex, config, sink, llm=planner_llm)
    finally:
        if servidor:
            servidor.shutdown()

    if campanha.state.value == "failed":
        return 3
    print(f"  Partida jogada em {time.monotonic() - t0:.0f}s. Accuracy final: {campanha.score.accuracy}/100   "
          + barra(campanha.score.eval_bar))
    if llm is not None:
        print("  A IA (treinador) esta comentando cada lance e a IA (juiz) esta revisando...")
        await apply_explanations(llm, campanha)
        ok = sum(1 for m in campanha.moves if m.ai_review and m.ai_review.verdict == "approved")
        rej = sum(1 for m in campanha.moves if m.ai_review and m.ai_review.verdict == "rejected")
        print(f"  Comentarios aprovados pelo juiz: {ok} | reprovados: {rej}")
    resumo = await build_summary(llm, campanha)
    print(f"\n  RESUMO ({'IA' if resumo.source == 'ai' else 'regras'}) — risco {resumo.risk_level.upper()}")
    print(f"  {resumo.headline}\n  {resumo.plain_language}")
    for i, p in enumerate(resumo.next_steps, 1):
        print(f"   {i}. {p}")

    pasta = ROOT / "reports"
    pasta.mkdir(exist_ok=True)
    nome = f"{inicio:%Y%m%d-%H%M%S}"
    md = pasta / f"game-review-{nome}.md"
    md.write_text(markdown(campanha, sink, resumo, inicio), encoding="utf-8")
    js = pasta / f"game-review-{nome}.json"
    js.write_text(json.dumps({
        "campaign": campanha.model_dump(mode="json"),
        "summary": resumo.model_dump(mode="json"),
        "executive_summary": resumo.plain_language,
        "audit": [x.model_dump(mode="json") for x in sink.audits],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Relatorio: {md}\n  JSON:      {js}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Testa um site AUTORIZADO e gera o relatorio estilo Chess.com.")
    p.add_argument("alvo", nargs="?", help="URL do site autorizado")
    p.add_argument("--lab", action="store_true", help="sobe e testa o site de treino local")
    p.add_argument("--hardened", action="store_true", help="site de treino na versao corrigida")
    p.add_argument("--por", default="Equipe Pentest Chess", help="quem autorizou o teste")
    p.add_argument("--extra", action="append", default=[], help="origem extra autorizada (ex.: versao http://)")
    p.add_argument("--aprovar-tudo", action="store_true")
    p.add_argument("--negar-tudo", action="store_true")
    p.add_argument("--automatico", action="store_true", help="sem humano: so a pre-aprovacao do .env vale")
    p.add_argument("--sem-ia", action="store_true", help="nao usa o Bedrock (so regras)")
    p.add_argument("--rps", type=float, default=2.0, help="requisicoes por segundo (max 5)")
    a = p.parse_args()
    a.rps = min(max(a.rps, 0.1), 5.0)
    raise SystemExit(asyncio.run(principal(a)))


if __name__ == "__main__":
    main()
