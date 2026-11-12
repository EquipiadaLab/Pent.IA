# API pública — Pentest Chess

Contrato entre Plataforma (trilho B) e Frontend. Schemas em `app/public_schemas.py`
(saída = `Public*`, entrada = `*Request`). Tudo é JSON.

## Endpoints

| Método | Rota | Entrada | Saída | Notas |
|---|---|---|---|---|
| POST | `/campaigns` | `CreateCampaignRequest` | `PublicCampaign` (201) | Valida escopo **antes** de criar; fora do escopo → `403 out_of_scope` e registra na auditoria |
| GET | `/campaigns/{id}` | — | `PublicCampaign` | Estado + lances atuais |
| GET | `/campaigns/{id}/events?after_seq=N` | — | `PublicEventPage` | **Polling** (lances ao vivo). Guarde `next_after_seq` |
| POST | `/campaigns/{id}/moves/{move}/approval` | `ApprovalDecisionRequest` | `PublicMove` | Aprova/nega lance `pending`. Registra quem/quando/por quê |
| POST | `/campaigns/{id}/stop` | `StopRequest` | `PublicCampaign` | Parada de emergência; preserva parciais |
| GET | `/campaigns/{id}/audit` | — | `list[PublicAuditEntry]` | Trilha, inclusive bloqueios |
| GET | `/campaigns/{id}/report` | — | `PublicGameReview` | Game Review |
| GET | `/campaigns/{id}/report.md` | — | `text/markdown` | Exportação |

Erros: sempre `ApiError {code, message}` com mensagem genérica. Códigos:
`invalid_request` (422), `unauthorized` (401), `out_of_scope` (403), `not_found` (404),
`rate_limited` (429), `internal` (500, sem detalhe).

## Fluxo ao vivo (front)

1. `POST /campaigns` → guarda `id`.
2. Loop a cada ~1 s: `GET /events?after_seq=<cursor>` → desenha cada `PublicEvent`.
   - `move_planned` / `approval_requested` → card do lance (pendente = amarelo, botões Aprovar/Negar).
   - `finding_created` → lance ganha `status`, `grade`, evidência.
   - `scope_blocked` → linha vermelha na auditoria.
   - `score_updated` → anima a eval bar.
   - `campaign_finished` / `stop_requested` → encerra o polling.
3. Aprovar/negar: `POST .../approval`. Parar: `POST .../stop`.

## Regras de segurança

### Backend (trilho B)
- **Autenticação:** todas as rotas exigem `Authorization: Bearer <API_TOKEN>` (valor em `.env`,
  comparar com `secrets.compare_digest`). Sem token → `401`.
- **CORS:** allowlist com **apenas** a origem do front (variável de ambiente). Nunca `*`.
- **Saída só por `Public*.from_internal`.** Proibido devolver modelo interno ou `model_dump()` dele.
- **Gravar já mascarado:** use `app/redact.py` antes de persistir evidência/auditoria e antes de
  qualquer prompt de LLM.
- **Entrada:** `CreateCampaignRequest` não permite escolher métodos HTTP; `allowed_methods`,
  `authorized_at` e tetos de taxa/total são definidos/limitados pelo servidor.
- **Escopo síncrono:** validar no `POST /campaigns`, não na task de fundo.
- **IDs de campanha:** `uuid4` (não sequenciais).
- **Erros:** handler global devolve `ApiError` genérico; log detalhado só no servidor.
- **Rate limit** por IP/token nas rotas de escrita; docs (`/docs`) desligados fora de dev.
- **Headers de resposta:** `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`.

### Frontend
- **Nunca renderizar HTML vindo da API.** `explanation`, `recommendation`, `title`, `note`,
  evidência: sempre como **texto** (JSX normal; **proibido** `dangerouslySetInnerHTML`). Código em `<pre>`.
  O conteúdo vem do alvo/LLM e é não confiável.
- **Sem segredos no bundle:** só `VITE_API_URL`. Nada de chaves AWS/LLM no front (tudo que começa
  com `VITE_` vira público).
- **Token da API:** mantido em memória (estado React), **não** em `localStorage`; enviado no header,
  nunca na URL/querystring.
- **Sem logs sensíveis:** não dar `console.log` de respostas completas; sem analytics de terceiros
  nas telas de evidência.
- **Links:** nunca transformar strings da API em `href`/`src` sem validar `https:`.
- **CSP no `index.html`** do front: `default-src 'self'; connect-src 'self' <API_URL>; img-src 'self' data:`.
- **Tipos TS:** gerar a partir dos schemas (ou espelhar `Public*`); campo fora do contrato = erro.

## O que NUNCA sai da API
Corpo bruto de respostas · valores de cookie/token · headers fora da allowlist · querystring/userinfo
de URLs · stack trace/mensagem de exceção · prompts e respostas cruas do LLM · credenciais/`.env` ·
caminhos do servidor · IDs internos do banco.
