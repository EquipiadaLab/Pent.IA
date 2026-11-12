"""Pentest Chess pelo terminal: envia um site, ve os lances ao vivo, recebe o relatorio.

Exemplos (dentro da pasta server):
    python scan.py --lab                      # sobe o site de treino e testa ele
    python scan.py --lab --hardened           # site de treino ja corrigido ("revanche")
    python scan.py https://alvo-autorizado.com --por "Organizacao do hackathon"

So roda contra alvos de AUTHORIZED_TARGETS (.env) ou enderecos locais.
Testes sensiveis perguntam sua aprovacao (ou use --aprovar-tudo / --negar-tudo).
O relatorio vai para server/reports/ (fora do Git).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "devtools"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from app.authorization import explain_refusal, is_authorized  # noqa: E402
from app.explainer import apply_explanations, validate_citations  # noqa: E402
from app.engine.memory_sink import MemorySink  # noqa: E402
from app.engine.runner import run_campaign  # noqa: E402
from app.engine.scope import utcnow  # noqa: E402
from app.models import Approval, Campaign, CampaignConfig, Event, EventType, Grade, Move  # noqa: E402

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
GRAVIDADE = {Grade.BLUNDER: 0, Grade.MISTAKE: 1, Grade.INACCURACY: 2}


# ----------------------------------------------------------------- ao vivo
class LiveSink(MemorySink):
    """Mostra cada lance no terminal assim que sai e pergunta as aprovacoes."""

    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode  # perguntar | aprovar | negar

    async def emit(self, event: Event) -> None:
        await super().emit(event)
        if event.type is EventType.FINDING_CREATED and event.move:
            m = event.move
            g = m.grade.value if m.grade else "inconclusive"
            print(f"  {m.move:>2}. [{ICONE[g]}] {ROTULO[g]:<13} {m.title}")
        elif event.type is EventType.SCORE_UPDATED and "eval_bar" in event.data:
            print("      " + barra(event.data["eval_bar"]))
        elif event.type is EventType.SCOPE_BLOCKED:
            print(f"  [BLOQUEADO] {event.data.get('reason')}")

    async def wait_approval(self, campaign_id: str, move: Move) -> Approval:
        if self.mode == "aprovar":
            ok = True
        elif self.mode == "negar":
            ok = False
        else:
            resp = await asyncio.to_thread(
                input, f"\n  >> Teste sensivel: '{move.title}'. Aprovar? [s/N] ")
            ok = resp.strip().lower() in ("s", "sim", "y", "yes")
        print(f"  {move.move:>2}. [{'ok' if ok else 'xx'}] {'Aprovado' if ok else 'Negado':<13} {move.title}")
        return Approval.APPROVED if ok else Approval.DENIED


def barra(eval_bar: float, largura: int = 30) -> str:
    """Barra de avaliacao: cheia = site seguro, vazia = site fragil."""
    cheio = round((eval_bar + 100) / 200 * largura)
    return "[" + "#" * cheio + "." * (largura - cheio) + f"] avaliacao {eval_bar:+.0f}"


# ----------------------------------------------------------------- relatorio
def passos_reproducao(origin: str, m: Move) -> list[str]:
    cmds = []
    for ev in m.evidence:
        partes = ev.request.split()
        if len(partes) < 2 or partes[0] not in ("GET", "OPTIONS"):
            continue
        metodo, caminho = partes[0], partes[1]
        extra = ""
        mo = re.search(r"Origin(?: enviado)?: (\S+)", ev.note or "")
        if mo:
            extra = f' -H "Origin: {mo.group(1)}"'
        flag = "-X OPTIONS " if metodo == "OPTIONS" else ""
        cmds.append(f'curl -i {flag}"{origin.rstrip("/")}{caminho}"{extra}')
    return list(dict.fromkeys(cmds))


async def resumo_ia(campaign: Campaign) -> tuple[str, str]:
    """Resumo executivo pelo Claude (Bedrock). Se falhar, usa texto automatico."""
    ruins = sorted((m for m in campaign.moves if m.grade in GRAVIDADE), key=lambda m: GRAVIDADE[m.grade])
    fatos = "\n".join(
        f"- Lance {m.move} '{m.title}': nota={m.grade.value}, severidade={m.severity.value}, "
        f"achado={m.explanation}, evidencias={[e.id for e in m.evidence]}"
        for m in campaign.moves if m.grade)
    prompt = (
        "Escreva um resumo executivo (4 a 6 frases) para um gestor nao tecnico, com os problemas "
        "mais graves primeiro e o que priorizar corrigir. Cite evidencias no formato [ev-N-N] "
        f"somente dentre as listadas.\nAccuracy: {campaign.score.accuracy}/100.\nLances:\n{fatos}")
    try:
        from app.llm_bedrock import BedrockLLM

        texto = await BedrockLLM().complete("Relatorio de pentest em portugues.", prompt, max_tokens=700)
        ids = {e.id for m in campaign.moves for e in m.evidence}
        return validate_citations(texto, ids), "Claude (Amazon Bedrock)"
    except Exception as exc:  # noqa: BLE001
        top = ", ".join(m.title for m in ruins[:3]) or "nenhum problema grave"
        return (f"Accuracy {campaign.score.accuracy}/100. Prioridades: {top}.",
                f"texto automatico (IA indisponivel: {type(exc).__name__})")


def markdown(c: Campaign, sink: MemorySink, resumo: str, fonte: str, inicio: datetime) -> str:
    s = c.score
    contagem = {}
    for m in c.moves:
        chave = m.grade.value if m.grade else f"nao executado ({m.approval.value})"
        contagem[chave] = contagem.get(chave, 0) + 1
    L = [
        f"# Game Review — {c.config.origin}", "",
        f"- **Data:** {inicio:%d/%m/%Y %H:%M} UTC · **Duracao:** {(c.finished_at - inicio).total_seconds():.1f}s",
        f"- **Autorizado por:** {c.config.authorized_by}",
        f"- **Estado:** {c.state.value} · **Requisicoes:** {sum(1 for a in sink.audits if a.allowed)}"
        f" · **Bloqueadas:** {sum(1 for a in sink.audits if not a.allowed)}", "",
        "## Placar", "",
        f"**Accuracy: {s.accuracy}/100** · Barra de avaliacao: {s.eval_bar:+.0f}", "",
        "| Nota | Quantidade |", "|---|---|",
        *[f"| {ROTULO.get(k, k)} | {v} |" for k, v in contagem.items()], "",
        f"## Resumo executivo", f"_Gerado por: {fonte}_", "", resumo or "(vazio)", "",
        "## Momentos-chave", "",
    ]
    ruins = sorted((m for m in c.moves if m.grade in GRAVIDADE), key=lambda m: GRAVIDADE[m.grade])
    L += [f"{i}. **Lance {m.move} — {m.title}** ({ROTULO[m.grade.value]}): {m.explanation}"
          for i, m in enumerate(ruins[:5], 1)] or ["Nenhum problema grave."]
    L += ["", "## Lances", ""]
    for m in c.moves:
        g = m.grade.value if m.grade else None
        L += [f"### {m.move}. {m.title} — {ROTULO.get(g, 'Nao executado (' + m.approval.value + ')')}", "",
              f"- **Referencia:** {m.wstg} · {m.owasp_top10} · fase {m.phase.value} · perfil {m.profile.value}"]
        if m.status:
            L += [f"- **Resultado:** {m.status.value} · severidade {m.severity.value} · confianca {m.confidence.value if m.confidence else '-'}",
                  f"- **O que encontramos:** {m.explanation}"]
            if m.ai_explanation:
                L.append(f"- **Comentario do treinador (IA):** {m.ai_explanation}")
            if m.recommendation:
                L.append(f"- **Melhor lance (correcao):** `{m.recommendation}`")
            for ev in m.evidence:
                L.append(f"- **Evidencia `{ev.id}`:** `{ev.request}` -> {ev.response_status or '-'}"
                         + (f" · {ev.note}" if ev.note else ""))
                for k, v in ev.response_headers.items():
                    L.append(f"    - `{k}: {v}`")
            passos = passos_reproducao(c.config.origin, m)
            if passos:
                L += ["- **Como reproduzir:**", "  ```", *[f"  {p}" for p in passos], "  ```"]
        L.append("")
    L += ["## Trilha de auditoria", "", "| Horario | Metodo | URL | Permitido | Status | Motivo |",
          "|---|---|---|---|---|---|"]
    L += [f"| {a.at:%H:%M:%S} | {a.method} | {a.url} | {'sim' if a.allowed else 'NAO'} | "
          f"{a.status_code or '-'} | {a.reason or ''} |" for a in sink.audits]
    L += ["", "> Escopo do MVP: configuracao HTTP/TLS e exposicao de arquivos. Nao cobre login, "
          "autorizacao, injecao nem logica de negocio. Accuracy nao significa \"% seguro\"."]
    return "\n".join(L)


# ----------------------------------------------------------------- main
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

    config = CampaignConfig(origin=alvo, extra_origins=a.extra, authorized_by=a.por,
                            authorized_at=utcnow(), max_requests_per_second=a.rps)
    modo = "aprovar" if a.aprovar_tudo else "negar" if a.negar_tudo else "perguntar"
    sink = LiveSink(modo)
    inicio = utcnow()
    print(f"\nPentest Chess — partida contra {alvo}\n")
    try:
        campanha = await run_campaign(uuid.uuid4().hex, config, sink)
    finally:
        if servidor:
            servidor.shutdown()

    if campanha.state.value == "failed":
        return 3
    print(f"\n  Accuracy final: {campanha.score.accuracy}/100   " + barra(campanha.score.eval_bar))
    print("  A IA esta comentando cada lance e escrevendo o resumo...")
    try:
        from app.llm_bedrock import BedrockLLM

        await apply_explanations(BedrockLLM(), campanha)
    except Exception:  # noqa: BLE001 - sem IA, o relatorio sai sem comentarios
        pass
    comentados = sum(1 for m in campanha.moves if m.ai_explanation)
    print(f"  Lances comentados pela IA: {comentados}/{sum(1 for m in campanha.moves if m.status)}")
    resumo, fonte = await resumo_ia(campanha)
    print(f"\n  Resumo ({fonte}):\n  {resumo}\n")

    pasta = ROOT / "reports"
    pasta.mkdir(exist_ok=True)
    nome = f"{inicio:%Y%m%d-%H%M%S}"
    md = pasta / f"game-review-{nome}.md"
    md.write_text(markdown(campanha, sink, resumo, fonte, inicio), encoding="utf-8")
    (pasta / f"game-review-{nome}.json").write_text(json.dumps({
        "campaign": campanha.model_dump(mode="json"),
        "executive_summary": resumo,
        "audit": [x.model_dump(mode="json") for x in sink.audits],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Relatorio salvo em: {md}")
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
    p.add_argument("--rps", type=float, default=2.0, help="requisicoes por segundo (max 5)")
    a = p.parse_args()
    a.rps = min(max(a.rps, 0.1), 5.0)
    raise SystemExit(asyncio.run(principal(a)))


if __name__ == "__main__":
    main()
