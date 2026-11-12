# Backend — Pentest Chess

## Trilhos e donos de pasta

| Trilho | Dono | Pastas/arquivos |
|---|---|---|
| **A — Motor** | backend-d | `app/engine/**` (scope, executor, planner, checks, evaluator, runner) |
| **B — Plataforma** | amigo | `app/api/`, `app/db.py`, `app/sink.py`, `app/audit.py`, `app/reporter/`, `app/report.py`, `app/main.py`, `requirements.txt` |
| **Compartilhado** | PR avisado | `app/models.py`, `app/interfaces.py` |

## Regras

1. Cada um edita **so** a sua pasta. `main.py` e `requirements.txt` sao do B (A pede dependencia nova ao B).
2. `models.py` / `interfaces.py` so mudam por PR avisado ao outro, com compatibilidade (campos novos opcionais).
3. O Motor nao importa db/api; a Plataforma nao importa checks. Conversam por `EventSink` e `run_campaign`.
4. Teste isolado com mocks: A usa um `EventSink` em memoria; B usa um `run_campaign` falso.
5. Rebase no `main` a cada PR mergeado. PRs pequenos. Commits com prefixo `engine:` ou `platform:`.
6. Credenciais so em `.env` (fora do Git). Segredos mascarados **antes** de gravar evidencia/auditoria e nunca vao para prompt de LLM.

## Contrato

- `status` = resultado (`pass|warning|fail|inconclusive`), so existe depois de executado.
- `approval` = fluxo (`not_required|pending|approved|denied`). Lance ativo leve ja nasce `pending`.
- `grade` = `brilliant|great|best|good|inaccuracy|mistake|miss|blunder|inconclusive`.
- Assinatura do Motor: `run_campaign(campaign_id, config, sink) -> Campaign` em `app/engine/runner.py`.

## Rodar

```bash
cd server
pip install -r requirements.txt
python -m pytest
```
