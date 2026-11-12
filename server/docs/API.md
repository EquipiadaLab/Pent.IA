# API do Pentest Chess — guia para o frontend

> Documento gerado a partir da API real (`server/app/api/routes.py`) e de respostas capturadas
> contra o site de treino. A especificação **OpenAPI (FastAPI)** completa está em
> [`openapi.json`](openapi.json) e, com o servidor rodando, em:
> - **Swagger (testar no navegador):** http://127.0.0.1:8000/docs
> - **OpenAPI JSON (gerar tipos):** http://127.0.0.1:8000/openapi.json

## 0. Subir o backend

```bash
cd server
pip install -r requirements.txt
python devtools/lab_server.py                   # terminal 1: site de treino → http://127.0.0.1:8080
python -m uvicorn app.main:app --port 8000      # terminal 2: API          → http://127.0.0.1:8000
```

No front: `VITE_API_URL=http://127.0.0.1:8000` (única variável; **nenhuma chave da AWS no front**).

Gerar tipos TypeScript a partir do FastAPI (opcional):
```bash
npx openapi-typescript http://127.0.0.1:8000/openapi.json -o src/api/schema.d.ts
```

---

## 1. Endpoints

| # | Método | Caminho | Uso na tela | Sucesso |
|---|---|---|---|---|
| 1 | GET | `/health` | Indicador "servidor no ar" | 200 |
| 2 | POST | `/campaigns` | Botão **Iniciar partida** | 201 `Campaign` |
| 3 | GET | `/campaigns` | Histórico de partidas | 200 `Campaign[]` |
| 4 | GET | `/campaigns/{id}` | Tabuleiro: estado, placar, lances | 200 `Campaign` |
| 5 | GET | `/campaigns/{id}/moves` | Só a lista de lances | 200 `Move[]` |
| 6 | GET | `/campaigns/{id}/events?since=N` | **Ao vivo** (polling) | 200 `Event[]` |
| 7 | POST | `/campaigns/{id}/moves/{move}/approve` | Botão **Aprovar** | 200 `ApprovalResponse` |
| 8 | POST | `/campaigns/{id}/moves/{move}/deny` | Botão **Negar** | 200 `ApprovalResponse` |
| 9 | POST | `/campaigns/{id}/stop` | Botão **Parada de emergência** | 200 `Campaign` |
| 10 | GET | `/campaigns/{id}/report` | Tela **Game Review** (inclui auditoria) | 200 `GameReview` |
| 11 | GET | `/campaigns/{id}/report/export?format=md` | Botão **Baixar relatório** | 200 `text/markdown` |

Não há endpoint separado de auditoria: ela vem em `GET /report` → `audit`.

### Erros
Sempre `{"detail": "mensagem"}` (padrão FastAPI). Mostre a mensagem como texto.

| Código | Quando | Exemplo real |
|---|---|---|
| 403 | Perfil `intrusive` pedido; sem `authorized_by` | `{"detail": "Perfil 'intrusive' bloqueado por padrao (fora de escopo)."}` |
| 404 | Campanha não existe | `{"detail": "Campanha nao encontrada."}` |
| 409 | Aprovar/negar lance que não está aguardando | `{"detail": "Lance 12 da campanha ... nao esta aguardando aprovacao."}` |
| 422 | Corpo inválido (campo faltando, URL sem `http(s)://`) | `{"detail": [ ...lista de erros... ]}` |
| 501 | `format=pdf` sem biblioteca de PDF no servidor | use `format=md` |

---

## 2. Endpoint por endpoint

### 2.1 `GET /health`
```json
{ "status": "ok", "engine": "real", "llm": "template" }
```
- `engine`: `real` = motor de verdade; `sample` = dados de exemplo (mostre um aviso).
- `llm`: `bedrock` = resumo escrito pela IA; `template` = resumo automático.

### 2.2 `POST /campaigns` — iniciar partida
**Corpo** (os campos ficam dentro de `config`):
```json
{
  "config": {
    "origin": "http://127.0.0.1:8080",
    "authorized_by": "Organizacao do hackathon",
    "authorized_at": "2026-11-12T15:00:00Z"
  }
}
```

| Campo | Obrigatório | Comportamento na tela |
|---|---|---|
| `origin` | sim | Input "Site autorizado". Deve começar com `http://` ou `https://` |
| `authorized_by` | sim | Input "Quem autorizou" |
| `authorized_at` | sim | **Não pedir ao usuário**: envie `new Date().toISOString()` |
| `extra_origins` | não | Ex.: versão `http://` do site, para o teste de redirecionamento |
| `included_paths` / `excluded_paths` | não | Avançado. Padrão: `["/"]` / `[]` |
| `window_start` / `window_end` | não | Janela de horário permitida (ISO 8601) |
| `allowed_profiles`, `allowed_methods`, `max_requests_per_second`, `max_total_requests`, `request_timeout_s` | não | **NÃO exponha na tela. Não envie.** Use os padrões do servidor |

**Resposta 201** (`Campaign`, estado inicial):
```json
{
  "id": "dded14a5aeb249138e9a354e6589b2b8",
  "config": { "origin": "http://127.0.0.1:8080", "authorized_by": "Org", "...": "..." },
  "state": "created",
  "created_at": "2026-11-12T16:15:29.520700Z",
  "finished_at": null,
  "score": null,
  "moves": []
}
```
Guarde o `id` e comece o polling (seção 3).

**Site não autorizado:** a resposta ainda é **201**, mas a partida termina sem lances, com
`state = "failed"`, e chegam os eventos `scope_blocked` → `campaign_finished` com `data.reason`.
Mostre isso em vermelho: *"Bloqueado: fora do escopo autorizado"*. É um ótimo momento da demo.

**Regras do servidor:** se o corpo trouxer `allowed_methods`, limites de velocidade etc., o
servidor **ignora ou limita** esses valores (só GET/OPTIONS, no máximo 5 req/s). A resposta mostra
o `config` que realmente vale.

### 2.3 `GET /campaigns/{id}` — tabuleiro
Retorna o `Campaign` completo (seção 4). Use para:
- recarregar a página / abrir uma partida antiga;
- sincronizar tudo depois que a partida termina.

### 2.4 `GET /campaigns/{id}/events?since=N` — ao vivo
Retorna só os eventos com `seq > N`, em ordem. Lista vazia `[]` = nada novo. Ver seção 3.

### 2.5 `POST /campaigns/{id}/moves/{move}/approve` e `/deny`
Sem corpo. Query opcional `?actor=Nome` (quem decidiu; padrão `operator`).
```json
{ "campaign_id": "dded14...", "move": 12, "approval": "approved" }
```
- **409** só se o lance já foi decidido (ou não existe / não pede aprovação).

### 2.6 `POST /campaigns/{id}/stop` — parada de emergência
Sem corpo. Retorna o `Campaign` com `state: "stopped"` e `finished_at` preenchido.
Lances pendentes de aprovação viram negados. Resultados já obtidos são preservados.
Peça confirmação antes ("Parar a partida?").

### 2.7 `GET /campaigns/{id}/report` — Game Review
```json
{
  "campaign": { "...Campaign completo..." },
  "executive_summary": "texto",
  "key_moments": [
    { "move": 1,  "summary": "HTTPS em uso — blunder (high)." },
    { "move": 10, "summary": "CORS com origem refletida — blunder (high)." }
  ],
  "audit": [
    {
      "campaign_id": "dded14...", "at": "2026-11-12T16:15:29.637468Z",
      "method": "GET", "url": "http://127.0.0.1:8080/", "allowed": true,
      "reason": null, "status_code": 200, "response_sha256": "02f64d...", "actor": "agent"
    }
  ]
}
```
- Chame **só quando a partida terminar**. Com a IA ligada, a **primeira** chamada leva ~20–30 s
  (a IA escreve o resumo e comenta cada lance): mostre um "Analisando a partida...". As chamadas
  seguintes são instantâneas (resultado guardado).
- Depois do relatório, cada lance passa a ter `ai_explanation` (também em `GET /campaigns/{id}`).
- `executive_summary` pode citar evidências como `[ev-10-4]`: transforme em link que rola até a
  evidência com esse `id` (seção 4.3).
- `key_moments.move` aponta para o número do lance: clique leva ao lance.
- `audit`: tabela cronológica. `allowed: false` → linha vermelha com `reason`.

### 2.8 `GET /campaigns/{id}/report/export?format=md`
Baixa um arquivo `.md` (`Content-Disposition: attachment`). Use um link/`fetch` + download.

---

## 3. Fluxo ao vivo (polling)

```ts
let since = 0;
const timer = setInterval(async () => {
  const events: Event[] = await (await fetch(`${API}/campaigns/${id}/events?since=${since}`)).json();
  for (const ev of events) {
    since = Math.max(since, ev.seq);
    handle(ev);                                   // tabela 3.1
    if (ev.type === "campaign_finished") clearInterval(timer);
  }
}, 1000);
```

### 3.1 Tipos de evento

| `type` | `move` | `data` | O que fazer na tela |
|---|---|---|---|
| `campaign_started` | — | `{ origin }` | "Partida iniciada contra {origin}" |
| `move_planned` | `Move` | `{}` | Card do lance aparece (cinza, "na fila") |
| `approval_requested` | `Move` | `{ move }` | Card **amarelo** com botões Aprovar/Negar |
| `approval_resolved` | `Move` | `{ move, approval, actor }` | Card vira aprovado (verde) ou negado (cinza); mostre "por {actor}" |
| `test_started` | `Move` | `{}` | Card com animação "pensando" |
| `finding_created` | `Move` | `{}` | Card ganha **nota, ícone, explicação e evidências** |
| `score_updated` | — | `{ accuracy, eval_bar, score }` | Anima a **barra de avaliação** e a accuracy |
| `scope_blocked` | — | `{ url?, method?, reason }` | Linha **vermelha**: "Bloqueado: {reason}" |
| `stop_requested` | — | `{ actor }` | "Partida interrompida por {actor}" |
| `campaign_finished` | — | `{ state, accuracy?, requests?, reason? }` | Para o polling; botão "Ver relatório" |

**Regra de ouro:** o lance é identificado por `move.move` (ou `data.move`). Sempre **substitua** o
card daquele número pelo `Move` mais recente — nunca crie um card duplicado.

### 3.2 Um evento por aprovação
Cada lance sensível gera **exatamente um** `approval_requested` e **um** `approval_resolved`.
Mesmo assim, atualize o card pelo número do lance (idempotente), que é a prática mais robusta.

### 3.3 Quando habilitar o botão Aprovar
Assim que o lance aparecer com `approval: "pending"` (já no `move_planned`). Clicar cedo **não**
dá mais 409. Desabilite os botões após o clique (evita duplo clique). Use `?actor=Nome` para
registrar quem decidiu na auditoria.

---

## 4. Modelos

### 4.1 `Campaign`
| Campo | Tipo | Comportamento |
|---|---|---|
| `id` | string | Use na URL da tela (`/partida/{id}`) |
| `config` | objeto | Mostre `origin`, `authorized_by`, `authorized_at` no cabeçalho ("Regras de engajamento") |
| `state` | enum | Tabela 4.4 |
| `created_at` / `finished_at` | ISO 8601 \| null | Duração = diferença |
| `score` | `Score` \| null | `null` até o primeiro lance terminar |
| `moves` | `Move[]` | Ordenados por `move` |

### 4.2 `Move` (um lance)
Exemplo real:
```json
{
  "move": 10,
  "test_id": "CORS-001",
  "title": "CORS com origem refletida",
  "phase": "middlegame",
  "profile": "active_light",
  "wstg": "WSTG-CLNT-07",
  "owasp_top10": "A01:2025",
  "approval": "not_required",
  "status": "fail",
  "severity": "high",
  "grade": "blunder",
  "confidence": "high",
  "evidence": [ { "...ver 4.3..." } ],
  "explanation": "CORS reflete origem arbitraria COM credenciais: qualquer site le respostas autenticadas.",
  "recommendation": "Usar allowlist fixa de origens; nunca refletir o Origin recebido nem combinar * com credenciais.",
  "started_at": "2026-11-12T16:15:29.756308Z",
  "finished_at": "2026-11-12T16:15:29.790346Z"
}
```

| Campo | Tipo | Comportamento |
|---|---|---|
| `move` | int | Número do lance (1, 2, 3...). **Chave do card** |
| `title` | string | Título do card |
| `test_id` | string | Etiqueta pequena (ex.: `CORS-001`) |
| `phase` | `opening` \| `middlegame` \| `endgame` | Agrupe: **Abertura** / **Meio-jogo** / **Final** |
| `profile` | `passive` \| `active_light` \| `intrusive` | Selo: "Passivo" / "Ativo leve" |
| `wstg`, `owasp_top10` | string \| null | Selos de referência no painel de detalhe |
| `approval` | enum | `not_required` (sem selo), `pending` (**amarelo + botões**), `approved` (selo verde), `denied` (**cinza**, "Negado por decisão humana", sem nota) |
| `status` | `pass` \| `warning` \| `fail` \| `inconclusive` \| **null** | `null` = ainda não rodou ou foi negado |
| `severity` | `low` \| `medium` \| `high` | Selo Baixa / Média / Alta |
| `grade` | enum \| **null** | **Ícone e cor do lance** (tabela 4.5). `null` → card sem nota |
| `confidence` | `low` \| `medium` \| `high` \| null | "Confiança: alta" no detalhe |
| `evidence` | `Evidence[]` | Painel "Evidência" (pode ser vazio) |
| `explanation` | string \| null | "O que encontramos" — fato do teste, **texto puro**. Sempre presente após executar |
| `ai_explanation` | string \| null | **"Comentário do treinador" (IA)**: o que significa, impacto e primeiro passo, citando `[ev-…]`. Aparece depois do `GET /report`. Se `null`, mostre só `explanation`. **Texto puro**; transforme `[ev-…]` em link para a evidência |
| `recommendation` | string \| null | "**Melhor lance**" (a correção) — mostre em bloco `<pre>`/`<code>` com botão copiar |
| `started_at` / `finished_at` | ISO 8601 \| null | Duração do lance |

### 4.3 `Evidence`
```json
{
  "id": "ev-10-4",
  "request": "GET / HTTP/1.1",
  "response_status": 200,
  "response_headers": {
    "access-control-allow-origin": "https://evil.pentestchess.invalid",
    "access-control-allow-credentials": "true",
    "set-cookie": "sid=***; SameSite=None"
  },
  "response_sha256": "02f64defc20e...",
  "note": "Origin enviado: https://evil.pentestchess.invalid"
}
```
| Campo | Comportamento |
|---|---|
| `id` | Âncora (`<div id="ev-10-4">`) para os links do resumo |
| `request` | Mostre em fonte monoespaçada |
| `response_status` | Selo do status HTTP (pode ser `null` em evidência de configuração) |
| `response_headers` | Tabela `nome: valor`. Valores sensíveis já vêm como `***` — **não tente "desmascarar"** |
| `response_sha256` | Mostre truncado (12 chars) com tooltip: prova de integridade |
| `note` | Observação em itálico |

### 4.4 `state` da campanha
| Valor | Texto | Visual |
|---|---|---|
| `created` | Preparando | cinza |
| `running` | Em andamento | azul animado |
| `waiting_approval` | Aguardando sua aprovação | amarelo |
| `stopped` | Interrompida | laranja |
| `finished` | Concluída | verde |
| `failed` | Recusada / falhou | vermelho |

Botão **Parar** visível só em `running` / `waiting_approval`.

### 4.5 `grade` (notas estilo Chess.com)
| Valor | Rótulo | Ícone sugerido | Cor sugerida |
|---|---|---|---|
| `brilliant` | Brilhante | `!!` | ciano |
| `great` | Ótimo | `!` | azul |
| `best` | Melhor lance | `★` | verde |
| `good` | Bom | `✓` | verde claro |
| `inaccuracy` | Imprecisão | `?!` | amarelo |
| `mistake` | Erro | `?` | laranja |
| `blunder` | Erro grave | `??` | vermelho |
| `miss` | Não executado | `—` | cinza |
| `inconclusive` | Inconclusivo | `…` | cinza |

`inconclusive` e `miss` **não contam** na pontuação: deixe claro ("não foi possível concluir").

### 4.6 `Score` e barra de avaliação
```json
{ "accuracy": 18.5, "eval_bar": -63.0, "counts": { "blunder": 4, "mistake": 6, "inaccuracy": 2, "inconclusive": 2 } }
```
| Campo | Faixa | Comportamento |
|---|---|---|
| `accuracy` | 0 a 100 | Número grande "Accuracy 18.5". **Não** escreva "% seguro" |
| `eval_bar` | −100 a +100 | **Barra vertical estilo Chess.com**: altura branca = `(eval_bar + 100) / 2` %. +100 = site sólido, −100 = site frágil. Anime a cada `score_updated` |
| `counts` | mapa `grade → quantidade` | Placar "4 erros graves · 6 erros · 2 imprecisões". Notas ausentes = 0 |

Guarde o histórico de `eval_bar` de cada `score_updated` para um **gráfico de linha** da partida
(eixo x = número do lance), como o gráfico do Game Review do Chess.com.

---

## 5. Telas sugeridas (mapa dos 8 itens do desafio)

| Item do desafio | Tela | Endpoints |
|---|---|---|
| 1. Console da campanha | Formulário + tabuleiro | `POST /campaigns`, `GET /campaigns/{id}` |
| 2. Escopo e política | Cabeçalho "Regras de engajamento" + linhas `scope_blocked` | `config`, eventos |
| 4. Aprovação humana | Card amarelo com Aprovar/Negar | `approve` / `deny` |
| 5. Achados | Painel do lance (nota, severidade, confiança, evidência) | `Move` |
| 6. Interrupção | Botão vermelho fixo | `POST /stop` |
| 7. Relatório | Game Review + download | `GET /report`, `/report/export` |
| 8. Auditoria | Tabela cronológica | `GET /report` → `audit` |

---

## 6. Regras de segurança do front (obrigatórias)

1. **Nunca renderizar HTML vindo da API.** `explanation`, `recommendation`, `note`,
   `executive_summary`, cabeçalhos: sempre como **texto** (JSX normal). **Proibido
   `dangerouslySetInnerHTML`** e bibliotecas que interpretam HTML/markdown sem sanitizar. Esse texto
   vem do site testado ou da IA e não é confiável.
2. **Nada de segredo no bundle.** Só `VITE_API_URL`. Tudo que começa com `VITE_` é público.
3. **Não transformar strings da API em `href`/`src`** (ex.: `origin`, `url` da auditoria) sem
   checar que começam com `http://` ou `https://`; abra com `rel="noopener noreferrer"`.
4. **Não logar respostas inteiras** no console; sem analytics de terceiros nas telas de evidência.
5. **Não enviar** `allowed_methods`, `allowed_profiles` ou limites de taxa no `POST /campaigns`.
6. **CSP** no `index.html`:
   `default-src 'self'; connect-src 'self' http://127.0.0.1:8000; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'`

---

## 7. Limitações atuais (para não estranhar)

| Comportamento | Contorno no front |
|---|---|
| Primeira chamada do `/report` demora ~20–30 s (IA) | Mostrar "Analisando a partida..." |
| Sem credenciais da AWS no servidor, `/health` mostra `llm: template` e `ai_explanation` fica `null` | Mostrar só `explanation` |
| CORS liberado só para `http://localhost:5173` e `http://127.0.0.1:5173` | Rodar o Vite nessas portas, ou o backend ajusta `CORS_ORIGINS` no `.env` |
| API sem autenticação | Só para o hackathon, rodando local |

**Resolvido** (não precisa mais de contorno): eventos de aprovação duplicados, 409 ao aprovar cedo,
site não autorizado com `state = finished`, aprovação que apagava o resultado do lance,
resumo sem IA.

---

## 8. Tipos TypeScript (copiar e colar)

```ts
export type Phase = "opening" | "middlegame" | "endgame";
export type Profile = "passive" | "active_light" | "intrusive";
export type Approval = "not_required" | "pending" | "approved" | "denied";
export type Status = "pass" | "warning" | "fail" | "inconclusive";
export type Severity = "low" | "medium" | "high";
export type Confidence = "low" | "medium" | "high";
export type Grade = "brilliant" | "great" | "best" | "good" | "inaccuracy" | "mistake" | "miss" | "blunder" | "inconclusive";
export type CampaignState = "created" | "running" | "waiting_approval" | "stopped" | "finished" | "failed";
export type EventType =
  | "campaign_started" | "move_planned" | "approval_requested" | "approval_resolved"
  | "test_started" | "finding_created" | "scope_blocked" | "score_updated"
  | "stop_requested" | "campaign_finished";

export interface Evidence {
  id: string; request: string; response_status: number | null;
  response_headers: Record<string, string>; response_sha256: string | null; note: string | null;
}
export interface Move {
  move: number; test_id: string; title: string; phase: Phase; profile: Profile;
  wstg: string | null; owasp_top10: string | null; approval: Approval;
  status: Status | null; severity: Severity; grade: Grade | null; confidence: Confidence | null;
  evidence: Evidence[]; explanation: string | null; ai_explanation: string | null; recommendation: string | null;
  started_at: string | null; finished_at: string | null;
}
export interface Score { accuracy: number; eval_bar: number; counts: Partial<Record<Grade, number>>; }
export interface CampaignConfig {
  origin: string; extra_origins: string[]; included_paths: string[]; excluded_paths: string[];
  allowed_profiles: Profile[]; allowed_methods: string[]; max_requests_per_second: number;
  max_total_requests: number; request_timeout_s: number; window_start: string | null;
  window_end: string | null; authorized_by: string; authorized_at: string;
}
export interface Campaign {
  id: string; config: CampaignConfig; state: CampaignState; created_at: string;
  finished_at: string | null; score: Score | null; moves: Move[];
}
export interface Event {
  seq: number; campaign_id: string; type: EventType; at: string;
  move: Move | null; data: Record<string, unknown>;
}
export interface AuditEntry {
  campaign_id: string; at: string; method: string; url: string; allowed: boolean;
  reason: string | null; status_code: number | null; response_sha256: string | null; actor: string;
}
export interface GameReview {
  campaign: Campaign; executive_summary: string | null;
  key_moments: { move: number; summary: string }[]; audit: AuditEntry[];
}
export interface ApprovalResponse { campaign_id: string; move: number; approval: Approval; }
export interface CreateCampaignBody {
  config: Pick<CampaignConfig, "origin" | "authorized_by" | "authorized_at">
    & Partial<Pick<CampaignConfig, "extra_origins" | "included_paths" | "excluded_paths" | "window_start" | "window_end">>;
}
```
