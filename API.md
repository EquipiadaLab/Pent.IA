# API do Pentest Chess — guia para o frontend

> Documento gerado a partir da API real (`server/app/api/routes.py`) e de respostas capturadas
> contra o site de treino. A especificação **OpenAPI (FastAPI)** completa está em
> [`openapi.json`](openapi.json) e, com o servidor rodando, em:
> - **Swagger (testar no navegador):** http://127.0.0.1:8000/docs
> - **OpenAPI JSON (gerar tipos):** http://127.0.0.1:8000/openapi.json

## 0. Subir o backendA

```bash
cd server
pip install -r requirements.txt
python devtools/lab_server.py                   # terminal 1: site de treino → http://127.0.0.1:8080
python -m uvicorn app.main:app --port 8000      # terminal 2: API          → http://127.0.0.1:8000
```

No front: `VITE_API_URL` (única variável; **nenhuma chave da AWS no front**):
- Local: `VITE_API_URL=http://127.0.0.1:8000`
- Servidor na AWS (com HTTPS via Caddy): `VITE_API_URL=https://3-81-3-113.sslip.io`

O WebSocket deriva daí trocando `http`→`ws` / `https`→`wss` (ex.: `wss://3-81-3-113.sslip.io/...`).
Para o navegador conectar, a **origem da página do front** precisa estar liberada no servidor: o
backend define `CORS_ORIGINS` (vale para CORS e WebSocket). Se o front for hospedado em um endereço
qualquer, use `CORS_ORIGINS=*` no `.env` do servidor (libera qualquer origem; mais aberto, menos seguro).

Gerar tipos TypeScript a partir do FastAPI (opcional):
```bash
npx openapi-typescript http://127.0.0.1:8000/openapi.json -o src/api/schema.d.ts
```

---

## 0A. O agente autônomo (o que mudou e como mostrar)

A IA agora **joga a partida**. O código continua como **árbitro**. Tudo chega em **JSON**.

| Etapa (por lance) | Quem | Onde aparece (JSON) | Item do desafio |
|---|---|---|---|
| Observar o site | código (GET / passivo, no início) | trilha `/audit` (`command`) | 8 |
| **Decidir o próximo lance** e registrar **hipótese, ação, resultado esperado, condição de parada** | **IA (planejador)** | `move.plan` no evento `move_planned` (**antes** de executar) | **3** |
| Validar a escolha (só catálogo, escopo, aprovação) | código (árbitro) | escolha inválida → `plan.source = "rules"` com o motivo em `plan.rationale` | 2 |
| Aprovar teste sensível | humano, ou pré-aprovação do servidor (execução automática) | `approval_requested` / `approval_resolved` (`data.actor`) | 4 |
| Executar | código | `test_started`, trilha `command` | — |
| **Confirmar** o achado com uma 2ª observação | código | `move.verdict`: `confirmed` / `discarded` / `inconclusive` | **5** |
| Explicar em linguagem simples | **IA (treinador)** | `move.ai_explanation` (após `/report`) | — |
| Revisar a explicação | **IA (juiz)** | `move.ai_review` (`approved` / `rejected` + `issues`) | 5 |
| Resumo executivo, riscos, próximos passos | **IA** (+ nível de risco por regra) | `report.summary` | **7** |
| Comparar com a partida anterior | código | `report.comparison` (`fixed`, `new`, `still_failing`) | contínuo |

**Tempo:** com a IA planejando, a partida leva ~60–75 s (cerca de 4 s de "pensamento" por lance). Entre
`finding_created` e o próximo `move_planned`, mostre **"A IA está analisando o tabuleiro..."**.
O primeiro `GET /report` leva ~25 s (treinador + juiz + resumo).

## 0B. Agentes especialistas (Pent + MITRE ATT&CK) — IMPORTANTE, leia antes de montar o "quem participou"

Desde a arquitetura multiagente, cada lance pode ter sido **recomendado por um agente especialista**
em uma tática do MITRE ATT&CK (Recon, Discovery, InitialAccess, Collection, PrivilegeEscalation,
Execution, Impact, CredentialAccess — mais táticas chegando). O agente master **Pent** coordena esses
especialistas, valida a sugestão contra o catálogo fechado e só então o Motor executa (sempre com
aprovação humana nos testes do `endgame`).

**Se o seu painel está mostrando "0 interação" para os agentes, é porque esses campos abaixo (que já
existem na API desde antes) ainda não foram consumidos no front.** Eles vêm dentro de cada `Move`:

```json
{
  "move": 9,
  "test_id": "COLLECT-APIFEEDBACK-001",
  "recommended_by": "Collection",
  "attack_tactic_id": "TA0009",
  "attack_tactic_name": "Collection",
  "attack_technique_id": "T1213",
  "attack_technique_name": "Data from Information Repositories",
  "attack_url": "https://attack.mitre.org/techniques/T1213",
  "exploitation_scenario": "Permite relacionar comentarios publicos a contas especificas...",
  "...": "demais campos de Move (seção 4.2)"
}
```

| Campo novo em `Move` | Comportamento na tela |
|---|---|
| `recommended_by` | Nome do agente que sugeriu o lance (ex.: `"Recon"`). **`null` ou `"-"`** = lance veio do fallback do catálogo (ainda sem agente especialista dedicado) |
| `attack_tactic_id` / `attack_tactic_name` | Tática MITRE ATT&CK (ex.: `"TA0043"` / `"Reconnaissance"`). Selo no card do lance |
| `attack_technique_id` / `attack_technique_name` | Técnica MITRE (ex.: `"T1595"` / `"Active Scanning"`) |
| `attack_url` | Link oficial `attack.mitre.org` da técnica — abra em nova aba |
| `exploitation_scenario` | Texto explicando como um atacante se aproveitaria da falha (só em achados `fail`/`warning`). Mostre junto de `recommendation` no painel de detalhe |

**Sugestão de UI:** no card do lance, mostre um selo com o nome do agente + ícone da tática
(ex.: "🔎 Recon · Reconnaissance"). Isso é o que prova visualmente que "vários agentes jogaram",
não só o Pent.

### Novo endpoint: `GET /campaigns/{id}/agents` — participação agregada

Pensado exatamente para a tela "Agentes" (lista com quantos lances cada um jogou, achados
confirmados e técnicas MITRE usadas) — **sem precisar agregar isso manualmente no front**.

```json
{
  "campaign_id": "a9c3bfcb4db84ce5ac0a048cfc6870cb",
  "agents": [
    { "agent": "Recon", "tactic_id": "TA0043", "tactic_name": "Reconnaissance",
      "moves_recommended": 7, "moves_approved": 7, "moves_denied": 0,
      "findings": 1, "techniques_used": ["T1594", "T1595"] },
    { "agent": "Discovery", "tactic_id": "TA0007", "tactic_name": "Discovery",
      "moves_recommended": 1, "moves_approved": 1, "moves_denied": 0,
      "findings": 0, "techniques_used": ["T1518"] },
    { "agent": "Collection", "tactic_id": "TA0009", "tactic_name": "Collection",
      "moves_recommended": 3, "moves_approved": 3, "moves_denied": 0,
      "findings": 1, "techniques_used": ["T1213"] },
    { "agent": "CredentialAccess", "tactic_id": "TA0006", "tactic_name": "Credential Access",
      "moves_recommended": 1, "moves_approved": 1, "moves_denied": 0,
      "findings": 1, "techniques_used": ["T1212"] },
    { "agent": "-", "tactic_id": null, "tactic_name": null,
      "moves_recommended": 9, "moves_approved": 9, "moves_denied": 0,
      "findings": 4, "techniques_used": [] }
  ]
}
```

| Campo | Comportamento na tela |
|---|---|
| `agent` | Nome do agente. `"-"` = lances do catálogo ainda sem agente especialista dedicado (ex.: headers, cookies, CORS) — mostre como "Motor (regras)" em vez de "-" |
| `tactic_id` / `tactic_name` | Selo da tática MITRE daquele agente |
| `moves_recommended` | Quantos lances aquele agente sugeriu nesta campanha (barra/contador) |
| `moves_approved` / `moves_denied` | Quantos foram aprovados vs. negados pelo humano |
| `findings` | Quantos lances deram `fail`/`warning` **confirmados** (não descartados) — "achados" daquele agente |
| `techniques_used` | Lista de IDs de técnica MITRE observados (ex.: `["T1595", "T1594"]`) — chips clicáveis para `attack.mitre.org/techniques/{id}` |

Chame esse endpoint junto com `GET /campaigns/{id}/report`, quando a campanha terminar (ou a
qualquer momento, para mostrar progresso parcial por agente).

## 0C. CVEs e exploits conhecidos (NVD) — sugestão do mentor

Correlaciona a(s) tecnologia(s) **realmente observada(s)** na campanha (cabeçalhos `Server`/
`X-Powered-By`, capturados por `INFO-001`/Discovery) com a base pública **NVD** (National
Vulnerability Database, NIST). Nunca inventa CVE: se nenhum lance capturou um header de
tecnologia identificável, ou a NVD não retornar nada para o termo, a lista vem vazia —
**não existe "CVE genérico por categoria de achado"**.

CDNs/proxies conhecidos (`cloudflare`, `akamai`, `fastly`, `varnish`...) são **ignorados** na
correlação: eles descrevem a borda de rede, não o software de origem, e usá-los geraria CVEs
de produtos completamente não relacionados ao alvo.

### Novo endpoint: `GET /campaigns/{id}/cves`

```json
{
  "campaign_id": "a9c3bfcb4db84ce5ac0a048cfc6870cb",
  "matches": [
    {
      "search_term": "Express",
      "move": 2,
      "cves": [
        {
          "cve_id": "CVE-2024-29041",
          "description": "Express.js minimal web framework... open redirect...",
          "cvss_score": 6.1,
          "cvss_severity": "MEDIUM",
          "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:L/A:N",
          "cwe_ids": ["CWE-601"],
          "published": "2024-03-25T21:15:08.527",
          "nvd_url": "https://nvd.nist.gov/vuln/detail/CVE-2024-29041",
          "exploits": [
            { "url": "https://github.com/x/poc-express-open-redirect", "source": "github.com" }
          ]
        }
      ],
      "queried_at": "2026-11-13T04:19:37.19Z",
      "source": "nvd",
      "error": null
    }
  ]
}
```

| Campo | Comportamento na tela |
|---|---|
| `matches[].search_term` | A tecnologia observada que gerou a busca (ex.: `"Express"`) — mostre como título da seção |
| `matches[].move` | Lance que capturou esse header; link para o card correspondente |
| `matches[].cves[]` | Lista ordenada por CVSS (maior primeiro). Vazio = NVD não tem CVE conhecido para esse termo |
| `cve_id` | Selo clicável → `nvd_url` (abre `nvd.nist.gov`) |
| `cvss_score` / `cvss_severity` | Selo colorido: `CRITICAL`/`HIGH` vermelho, `MEDIUM` amarelo, `LOW` cinza |
| `cwe_ids` | Chips pequenos (ex.: `CWE-601`), opcional link para `cwe.mitre.org/data/definitions/{n}.html` |
| `exploits[]` | **Se não vazio**, destaque com ícone de alerta: "⚠️ Exploit público conhecido" + link. Vem vazio na maioria dos CVEs — só aparece quando a própria NVD referencia um PoC/exploit |
| `error` | Se preenchido, a consulta à NVD falhou (rede/timeout) — mostre "Não foi possível consultar a NVD agora" sem detalhes técnicos |

Pode ser **lento na primeira chamada** (consulta externa, ~1–3 s por tecnologia observada);
resultados ficam em cache no servidor por 1h. Mostre um spinner "Consultando base de
vulnerabilidades (NVD)...".

### No relatório exportado (Markdown/PDF)

`GET /campaigns/{id}/report/export?format=md&include_cves=true` (ou `format=pdf`) inclui uma
seção **"CVEs e exploits conhecidos (NVD)"** entre o resumo executivo e os achados, com o mesmo
conteúdo do endpoint acima já formatado. Sem o parâmetro `include_cves=true`, o relatório sai
igual a antes (mais rápido, sem chamada externa) — use esse parâmetro só quando o usuário clicar
em algo como **"Gerar relatório com CVEs"**.

**No card do lance**, mostre o plano antes do resultado:
> **Hipótese:** {plan.hypothesis} · **Esperado:** {plan.expected_result} · **Por quê:** {plan.rationale}
> Selo: `IA` se `plan.source = "ai"`, `Regras` se `"rules"`.

**No card de aprovação**, mostre a hipótese: o humano aprova sabendo **por que** a IA quer o teste.

**Selo de confirmação** (`move.verdict`, só em achados `warning`/`fail`):
`confirmed` → "Confirmado (2 observações)" · `discarded` → "Descartado: não se reproduziu" (cinza, fora do
placar) · `inconclusive` → "Não reconfirmado".

Os títulos dos testes passaram a ser neutros (ex.: "Exposicao do repositorio .git" em vez de
"Repositorio .git exposto"): o título diz **o que foi verificado**; o resultado vem na nota.

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
| 12 | **WS** | `/campaigns/{id}/ws?since=N` | **Ao vivo por WebSocket** (recomendado) | stream de `Event` |
| 13 | GET | `/campaigns/{id}/audit` | **Trilha de auditoria** cronológica (item 8) | 200 `TimelineEntry[]` |
| 14 | GET | `/status` | **Painel "sistema no ar"**: API, banco, motor e IA | 200 `StatusResponse` |
| 15 | GET | `/catalog` | Todos os testes que o agente pode jogar (o "tabuleiro"; o total cresce conforme mais agentes são adicionados — confira `/status` para o número atual) | 200 `CatalogTest[]` |
| 16 | GET | `/scope` | Regras de engajamento do servidor (alvos autorizados, limites, pré-aprovação) | 200 `ScopeResponse` |
| 17 | GET | `/campaigns/{id}/status` | Progresso resumido da partida (barra de progresso, pendências) | 200 `CampaignStatusResponse` |
| 18 | GET | `/campaigns/{id}/agents` | **Tela "Agentes"**: participação de Pent/Recon/Discovery/etc. (ver seção 0B) | 200 `AgentsParticipationResponse` |
| 19 | GET | `/campaigns/{id}/cves` | **CVEs e exploits conhecidos** (NVD), correlacionados a tecnologia observada (ver seção 0C) | 200 `CvesResponse` |

Não há endpoint separado de auditoria: ela vem em `GET /report` → `audit`.

O WebSocket (#12) **não aparece no `/docs` nem no `openapi.json`** (o FastAPI não documenta
WebSockets no OpenAPI). A referência dele é a seção 3A deste guia.

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
{ "status": "ok", "engine": "real", "llm": "bedrock", "planner": "ai" }
```
- `engine`: `real` = motor de verdade; `sample` = dados de exemplo (mostre um aviso).
- `llm`: `bedrock` = treinador/juiz/resumo pela IA; `template` = textos automáticos.
- `planner`: `ai` = **a IA decide cada lance**; `rules` = ordem padrão do catálogo.
- Use o `/health` para um "ping" rápido (ex.: bolinha verde no topo). Para o detalhe, use o `/status` (2.10).

### 2.2 `POST /campaigns` — iniciar partida

Campos extras opcionais (aditivos):
- `config.unattended: true` → **execução automática** (ex.: n8n às 9h): testes sensíveis só rodam se
  estiverem na **pré-aprovação do servidor**; o resto é negado sem esperar humano.
- `revalidate_from: "<id da partida anterior>"` (fora de `config`) → **revalidação**: joga **só** os
  testes que falharam naquela partida (mesmo alvo). Erros: 404 (não existe), 422 (outro alvo),
  409 (nada a revalidar). A resposta mostra `config.only_tests`.
  Botão sugerido no relatório: **"Revanche: revalidar o que falhou"**.
> **Alvo travado — não existe mais campo de URL no front.** O servidor roda com
> `locked_target` ativo e **só testa o alvo autorizado** (o migbot). Não crie input
> de "Site a testar": **não mande `origin`** (ou mande vazio). O servidor usa o alvo
> travado sozinho. Se o front mandar qualquer outra URL, a resposta é **403**
> (`"Alvo travado: este sistema so testa ..."`). Para exibir qual é o alvo, leia
> `locked_target` em `GET /scope` e mostre fixo: *"Alvo: {locked_target}"*.

**Corpo** (os campos ficam dentro de `config`):
```json
{
  "config": {
    "authorized_by": "Organizacao do hackathon",
    "authorized_at": "2026-11-12T15:00:00Z"
  }
}
```

| Campo | Obrigatório | Comportamento na tela |
|---|---|---|
| `origin` | **não enviar** | **Sem campo de URL.** Alvo travado no servidor; mandar outra URL → 403. Apenas mostre `locked_target` (de `/scope`) como texto fixo |
| `authorized_by` | sim | Input "Quem autorizou" (fica na auditoria — accountability) |
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

**Alvo recusado:** o servidor roda **travado** (`locked_target`), então só o alvo autorizado passa.
Se o front mandar outra URL, vem **403** na hora (`"Alvo travado: este sistema so testa ..."`). Como
o front **não manda URL**, isso não deve acontecer no uso normal — mas trate o 403 mostrando em
vermelho: *"Alvo recusado: {detail}"*. Para saber qual é o alvo, use `GET /scope` → `locked_target`.
(Os campos `accepts_any_target`/`default_target`/`authorized_targets` do `/scope` existem para outros
modos de servidor; com a trava ligada, só `locked_target` importa para o front.)

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

### 2.9 `GET /campaigns/{id}/audit` — trilha de auditoria (item 8)
Lista **cronológica** com tudo o que aconteceu: decisões e hipóteses da IA, aprovações, cada
requisição (comando), bloqueios, resultados e parada.
```json
[
  { "at": "2026-11-12T18:12:50Z", "kind": "campaign", "move": null, "summary": "Partida iniciada contra http://127.0.0.1:8080", "details": { "planner": "ai", "unattended": false } },
  { "at": "2026-11-12T18:12:50Z", "kind": "command",  "move": null, "summary": "GET http://127.0.0.1:8080/ -> 200", "details": { "method": "GET", "allowed": true, "status_code": 200 } },
  { "at": "2026-11-12T18:12:52Z", "kind": "decision", "move": 1,    "summary": "Lance 1: IA escolheu 'Uso de HTTPS'. Hipotese: ...", "details": { "test_id": "TLS-001", "plan": { "...": "MovePlan" } } },
  { "at": "2026-11-12T18:12:52Z", "kind": "result",   "move": 1,    "summary": "Lance 1: Uso de HTTPS -> fail / blunder (confirmed)", "details": { "verdict": "confirmed", "evidence_ids": ["ev-1-2"] } },
  { "at": "2026-11-12T18:13:30Z", "kind": "approval", "move": 11,   "summary": "Lance 11: aprovado por Daniel", "details": { "approval": "approved", "actor": "Daniel" } }
]
```
`kind`: `campaign` · `decision` · `approval_requested` · `approval` · `command` · `blocked` · `result` · `stop`.

### 2.10 `GET /status` — o sistema está rodando?
Saúde detalhada. **Rápido** por padrão (não chama a IA).
`?check_llm=true` faz uma chamada curta ao Bedrock para provar que a IA responde (resultado guardado por 60 s).
```json
{
  "status": "ok",
  "version": "0.2.0",
  "time": "2026-11-12T18:22:33Z",
  "uptime_s": 120,
  "engine_mode": "real",
  "planner": "ai",
  "models": { "coach_judge_summary": "us.anthropic.claude-sonnet-5-5", "planner": "us.anthropic.claude-haiku-5-5" },
  "components": {
    "api":      { "status": "ok",  "detail": null, "latency_ms": null },
    "database": { "status": "ok",  "detail": null, "latency_ms": 0 },
    "engine":   { "status": "ok",  "detail": "N testes no catalogo (N cresce conforme agentes sao adicionados)", "latency_ms": null },
    "llm":      { "status": "ok",  "detail": "Bedrock respondeu", "latency_ms": 1553 }
  },
  "campaigns": { "total": 3, "created": 0, "running": 1, "waiting_approval": 0, "stopped": 0, "finished": 2, "failed": 0 }
}
```
| Campo | Comportamento na tela |
|---|---|
| `status` | `ok` = verde; `degraded` = amarelo ("funcionando com limitações") |
| `components.*.status` | `ok` verde · `degraded` amarelo · `error` vermelho · `disabled` cinza (IA desligada) · `unchecked` cinza ("clique para testar a IA") |
| `components.llm` | Se `error` com "credenciais expiradas?", avise: *"A IA está indisponível. As partidas continuam só com regras."* |
| `planner` | Selo "Agente com IA" (`ai`) ou "Modo regras" (`rules`) |
| `campaigns` | Contadores do painel (ex.: "1 partida em andamento") |

Sugestão: chame `/status` ao abrir o app; ofereça um botão **"Testar IA"** que chama `/status?check_llm=true`.

### 2.11 `GET /catalog` — o tabuleiro
Lista fixa dos testes (útil para mostrar **antes** da partida o que pode ser jogado, e para a legenda).
```json
[
  {
    "test_id": "FILE-001", "title": "Exposicao do repositorio .git", "phase": "endgame",
    "profile": "active_light", "severity": "high", "wstg": "WSTG-CONF-04", "owasp_top10": "A02:2025",
    "needs_approval": true,
    "hypothesis": "A pasta .git pode ter sido publicada junto com o site.",
    "expected": "/.git/HEAD nao acessivel (404/403).",
    "impact": "Com o .git exposto, o codigo-fonte e o historico (as vezes com senhas) podem ser baixados."
  }
]
```
Agrupe por `phase` (Abertura / Meio-jogo / Final) e marque com um cadeado os que têm `needs_approval`.

### 2.12 `GET /scope` — regras de engajamento
O que o **servidor** permite. Use na tela de configuração (item 2 do desafio).
```json
{
  "locked_target": "https://3.migbot.com.br",
  "authorized_targets": ["https://3.migbot.com.br:443"],
  "accepts_any_target": false,
  "default_target": "https://3.migbot.com.br",
  "blocks_private_targets": true,
  "allowed_methods": ["GET", "OPTIONS"],
  "allowed_profiles": ["active_light", "passive"],
  "blocked_profiles": ["intrusive"],
  "limits": { "max_requests_per_second": 5.0, "max_total_requests": 500, "request_timeout_s": 30.0 },
  "preapproval": { "tests": ["FILE-001", "ERR-001"], "approved_by": "Maria", "valid_until": "2026-11-30", "active": ["FILE-001", "ERR-001"] }
}
```
| Campo | Comportamento |
|---|---|
| `locked_target` | **É o que importa para o front.** Vem preenchido: o sistema **só testa esse endereço**. **Não crie campo de URL**; mostre "Alvo: {locked_target}" fixo. Qualquer outra URL enviada dá **403** |
| `accepts_any_target` | Virá `false` (travado). Os campos abaixo só valem para outros modos de servidor — **ignore com a trava ligada** |
| `default_target` | Não usado pelo front com a trava ligada |
| `blocks_private_targets` | `true` = redes internas/privadas são sempre recusadas (anti-SSRF). Informativo |
| `authorized_targets` | Só no modo lista fixa (não é o caso): os únicos alvos aceitos |
| `allowed_methods` / `blocked_profiles` | Texto fixo "Somente leitura (GET/OPTIONS) · Testes intrusivos bloqueados" |
| `limits` | "Até 5 requisições/s · máximo 500 por partida" |
| `preapproval` | Para execução automática: quais testes sensíveis rodam sem humano, quem autorizou e até quando. `active` = válidos agora |

### 2.13 `GET /campaigns/{id}/status` — progresso da partida
Resumo leve para o cabeçalho da partida (barra de progresso, "aguardando você").
```json
{
  "id": "dded14...", "state": "waiting_approval", "origin": "http://127.0.0.1:8080", "unattended": false,
  "progress": { "played": 10, "total": 14, "percent": 71 },
  "current_move": { "move": 11, "test_id": "FILE-002", "title": "Exposicao do arquivo .env", "stage": "awaiting_approval" },
  "pending_approvals": [ { "move": 11, "test_id": "FILE-002", "title": "Exposicao do arquivo .env", "hypothesis": "O arquivo .env pode estar acessivel publicamente." } ],
  "score": { "accuracy": 22.0, "eval_bar": -56.0, "counts": { "blunder": 2, "mistake": 5 } },
  "last_seq": 47,
  "created_at": "2026-11-12T18:12:50Z", "finished_at": null, "elapsed_s": 41
}
```
| Campo | Comportamento |
|---|---|
| `progress` | Barra "Lance 10 de 14". Em revalidação, `total` = só os testes revalidados |
| `current_move.stage` | `running` → "A IA está jogando: {title}"; `awaiting_approval` → destaque amarelo |
| `pending_approvals` | Badge com a quantidade + atalho para o card; mostre a `hypothesis` |
| `last_seq` | Ao reabrir a página, conecte o WebSocket com `?since=last_seq` e carregue o resto por `GET /campaigns/{id}` |
| `elapsed_s` | Cronômetro da partida |

O ao vivo continua sendo pelo WebSocket; este endpoint é para **reabrir a tela**, listas e o n8n.

### 2.8 `GET /campaigns/{id}/report/export?format=md`
Baixa um arquivo `.md` (`Content-Disposition: attachment`). Use um link/`fetch` + download.

---

## 3A. Ao vivo por WebSocket (recomendado)

`ws://127.0.0.1:8000/campaigns/{id}/ws?since=N`

- Cada mensagem é **um `Event`, com o mesmo JSON do polling** (seção 3.1). O `handle(ev)` é o mesmo.
- Ao conectar, o servidor manda os eventos com `seq > since` que você ainda não tem e depois
  **empurra cada evento novo na hora**.
- Depois de `campaign_finished`, o servidor **fecha** a conexão (código `1000`).
- O socket é **só de leitura**: aprovar, negar e parar continuam pelos `POST` (seções 2.5 e 2.6).
  Mensagens enviadas pelo front são ignoradas.
- A origem da página precisa estar em `CORS_ORIGINS` (padrão: `http://localhost:5173` e
  `http://127.0.0.1:5173`). Outra origem é recusada no handshake.

### Códigos de fechamento (`event.code` no `onclose`)
| Código | Significado | O que fazer |
|---|---|---|
| `1000` | Partida terminou | Mostrar "Ver relatório". Não reconectar |
| `1006` | Conexão caiu (rede, servidor reiniciou) | Reconectar com `since` = último `seq` |
| `1008` | Origem não autorizada | Erro de configuração (porta do Vite / `CORS_ORIGINS`) |
| `1013` | Servidor cheio | Usar o polling (seção 3) |
| `4404` | Campanha não existe | Mostrar "Partida não encontrada" |

### Exemplo (React/TS) com reconexão e plano B por polling
```ts
const WS_URL = import.meta.env.VITE_API_URL.replace(/^http/, "ws");

export function watchCampaign(id: string, handle: (ev: Event) => void, onEnd: () => void) {
  let since = 0;
  let tries = 0;
  let closedByUs = false;
  let socket: WebSocket | null = null;

  const connect = () => {
    socket = new WebSocket(`${WS_URL}/campaigns/${id}/ws?since=${since}`);
    socket.onmessage = (msg) => {
      const ev: Event = JSON.parse(msg.data);   // JSON.parse, nunca innerHTML
      if (ev.seq <= since) return;              // idempotente
      since = ev.seq;
      tries = 0;
      handle(ev);
    };
    socket.onclose = (e) => {
      if (closedByUs || e.code === 1000) return onEnd();
      if (e.code === 4404 || e.code === 1008) return onEnd();   // mostrar erro
      if (++tries <= 5) setTimeout(connect, 1000 * tries);      // reconecta e retoma
      else startPolling(id, since, handle, onEnd);              // plano B: seção 3
    };
  };
  connect();
  return () => { closedByUs = true; socket?.close(); };         // chamar no unmount
}
```

Dicas:
- Abra o socket **logo depois** do `POST /campaigns` (ou ao abrir uma partida existente).
- Ao clicar em Aprovar/Negar/Parar, **não** atualize o card "na mão": o evento correspondente
  chega pelo socket em milissegundos.
- Vários lances podem chegar quase juntos. Para efeito de "partida sendo jogada", enfileire e
  mostre um por um com ~300 ms de intervalo.

## 3. Fluxo ao vivo (polling — plano B)

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

#### Campos do agente autônomo (no `Move`)
```json
"plan": {
  "hypothesis": "O site pode estar servindo o cookie de sessao 'sid' sem criptografia, pois o esquema observado e http.",
  "action": "Verificar se o site responde por HTTPS e se o acesso em http:// ocorre sem criptografia.",
  "expected_result": "Um site seguro ofereceria HTTPS funcional e nao manteria o acesso em texto puro.",
  "stop_condition": "Encerrar se nao houver resposta ou se o alvo estiver fora do escopo autorizado.",
  "rationale": "O alvo foi observado em http e ha cookie de sessao, por isso o transporte e a prioridade.",
  "source": "ai",
  "planned_at": "2026-11-12T18:12:52Z"
},
"verdict": "confirmed",
"impact": "Sem HTTPS, qualquer pessoa na mesma rede le ou altera senhas, cookies e dados em transito.",
"reproduce": ["curl -i \"http://127.0.0.1:8080/.git/HEAD\""],
"ai_review": { "verdict": "approved", "issues": [] }
```
| Campo | Comportamento |
|---|---|
| `plan` | Vem **no `move_planned`, antes do resultado**. Mostre hipótese/esperado/porquê. `source`: `ai` ou `rules` |
| `verdict` | Só em achados. Selo Confirmado / Descartado / Não reconfirmado. `discarded` → nota vira `inconclusive` e sai do placar |
| `impact` | "O que pode acontecer" — mostre em achados `warning`/`fail` |
| `reproduce` | Lista de comandos `curl` — bloco de código com botão copiar ("Como reproduzir") |
| `ai_review` | `approved` → mostrar `ai_explanation` com selo "revisado pelo juiz". `rejected` → `ai_explanation` vem `null`; opcionalmente mostre "comentário da IA reprovado" + `issues` |

#### Campos do agente especialista que recomendou o lance (ver seção 0B)
| Campo | Comportamento |
|---|---|
| `recommended_by` | Nome do agente (ex.: `"Recon"`). `null`/`"-"` = fallback do catálogo |
| `attack_tactic_id` / `attack_tactic_name` | Tática MITRE (ex.: `"TA0043"` / `"Reconnaissance"`) — selo no card |
| `attack_technique_id` / `attack_technique_name` | Técnica MITRE (ex.: `"T1595"` / `"Active Scanning"`) |
| `attack_url` | Link oficial da técnica em `attack.mitre.org` |
| `exploitation_scenario` | Como um atacante exploraria a falha, em linguagem simples (achados `fail`/`warning`) |

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
| 3. Plano do agente | Hipótese/esperado/parada no card, **antes** do resultado | `move.plan` (`move_planned`) |
| 5. Confirmados/descartados | Selo de veredito + impacto + confiança | `move.verdict`, `impact`, `confidence` |
| 7. Relatório (completo) | Resumo estruturado, riscos, próximos passos, reprodução, comparação | `report.summary`, `move.reproduce`, `report.comparison` |
| 8. Auditoria | Tabela cronológica completa | `GET /campaigns/{id}/audit` |

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
   `default-src 'self'; connect-src 'self' http://127.0.0.1:8000 ws://127.0.0.1:8000; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'`

---

## 7. Limitações atuais (para não estranhar)

| Comportamento | Contorno no front |
|---|---|
| Primeira chamada do `/report` demora ~20–30 s (IA) | Mostrar "Analisando a partida..." |
| Sem credenciais da AWS no servidor, `/health` mostra `llm: template` e `ai_explanation` fica `null` | Mostrar só `explanation` |
| CORS **e WebSocket** liberados só para `http://localhost:5173` e `http://127.0.0.1:5173` | Rodar o Vite nessas portas, ou o backend ajusta `CORS_ORIGINS` no `.env` |
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
  plan: MovePlan | null; verdict: Verdict | null; impact: string | null; reproduce: string[];
  ai_review: { verdict: "approved" | "rejected"; issues: string[] } | null;
  recommended_by: string | null;
  attack_tactic_id: string | null; attack_tactic_name: string | null;
  attack_technique_id: string | null; attack_technique_name: string | null;
  attack_url: string | null;
  started_at: string | null; finished_at: string | null;
}
export type Verdict = "confirmed" | "discarded" | "inconclusive";
export interface MovePlan {
  hypothesis: string; action: string; expected_result: string; stop_condition: string;
  rationale: string | null; source: "ai" | "rules"; planned_at: string | null;
}
export interface Score { accuracy: number; eval_bar: number; counts: Partial<Record<Grade, number>>; }
export interface CampaignConfig {
  origin: string; extra_origins: string[]; included_paths: string[]; excluded_paths: string[];
  allowed_profiles: Profile[]; allowed_methods: string[]; max_requests_per_second: number;
  max_total_requests: number; request_timeout_s: number; window_start: string | null;
  window_end: string | null; authorized_by: string; authorized_at: string;
  unattended: boolean; only_tests: string[] | null;
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
  summary: ExecutiveSummary | null; comparison: Comparison | null;
}
export interface ExecutiveSummary {
  headline: string; risk_level: "critico" | "alto" | "medio" | "baixo"; plain_language: string;
  top_risks: { move: number; title: string; why: string }[]; next_steps: string[]; source: "ai" | "rules";
}
export interface Comparison {
  previous_campaign_id: string; previous_accuracy: number | null; accuracy_delta: number | null;
  fixed: string[]; new: string[]; still_failing: string[];
}
export interface TimelineEntry {
  at: string; kind: "campaign" | "decision" | "approval_requested" | "approval" | "command" | "blocked" | "result" | "score" | "stop";
  move: number | null; summary: string; details: Record<string, unknown>;
}
export interface ApprovalResponse { campaign_id: string; move: number; approval: Approval; }
export interface ComponentStatus { status: "ok" | "degraded" | "error" | "disabled" | "unchecked"; detail: string | null; latency_ms: number | null; }
export interface StatusResponse {
  status: "ok" | "degraded"; version: string; time: string; uptime_s: number;
  engine_mode: "real" | "sample"; planner: "ai" | "rules";
  models: { coach_judge_summary: string | null; planner: string | null };
  components: { api: ComponentStatus; database: ComponentStatus; engine: ComponentStatus; llm: ComponentStatus };
  campaigns: Record<"total" | CampaignState, number>;
}
export interface CatalogTest {
  test_id: string; title: string; phase: Phase; profile: Profile; severity: Severity; wstg: string;
  owasp_top10: string; needs_approval: boolean; hypothesis: string; expected: string; impact: string;
}
export interface ScopeResponse {
  locked_target: string | null; authorized_targets: string[]; accepts_any_target: boolean; default_target: string | null;
  blocks_private_targets: boolean; allowed_methods: string[];
  allowed_profiles: Profile[]; blocked_profiles: Profile[];
  limits: { max_requests_per_second: number; max_total_requests: number; request_timeout_s: number };
  preapproval: { tests: string[]; approved_by: string | null; valid_until: string | null; active: string[] };
}
export interface CampaignStatusResponse {
  id: string; state: CampaignState; origin: string; unattended: boolean;
  progress: { played: number; total: number; percent: number };
  current_move: { move: number; test_id: string; title: string; stage: "awaiting_approval" | "running" } | null;
  pending_approvals: { move: number; test_id: string; title: string; hypothesis: string | null }[];
  score: Score | null; last_seq: number; created_at: string; finished_at: string | null; elapsed_s: number;
}
export interface CreateCampaignBody {
  config: Pick<CampaignConfig, "authorized_by" | "authorized_at">
    & Partial<Pick<CampaignConfig, "origin" | "extra_origins" | "included_paths" | "excluded_paths" | "window_start" | "window_end" | "unattended">>;
  revalidate_from?: string;
}
```
