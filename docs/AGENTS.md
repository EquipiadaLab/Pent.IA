# Agentes e cobertura MITRE ATT&CK

Referência de coordenação dos agentes do Pent.IA. Mantida junto ao código;
atualizar a cada agente concluído ou decisão de escopo.

## Como os agentes operam

O Pent.IA é um avaliador **HTTP black-box** de aplicações web autorizadas. Os
agentes de tática **não acessam a rede e não executam checks**. Cada agente
especialista cobre **uma** tática ATT&CK e apenas **recomenda** um `test_id`
do catálogo fechado (`app/engine/checks`). A partir daí:

1. `Pent` (agente master) valida a recomendação contra o catálogo e a lista de
   checks elegíveis, e escolhe de forma determinística (prioridade, custo, id),
   respeitando a progressão de fase (abertura → meio-jogo → final);
2. o `runner` cria um `Move` pendente;
3. um humano aprova ou nega;
4. só então o Motor executa o `CheckSpec`, com `ScopeGuard`, `Fetcher`,
   auditoria, rate limit, timeout e parada de emergência.

Regra de mapeamento: uma técnica ATT&CK só é associada a um check quando há
justificativa técnica real. Não se reusa uma técnica só para aumentar a
contagem de cobertura.

## Cobertura atual

| Tática | ATT&CK | Técnica | Check(s) | Responsável | Status |
|---|---|---|---|---|---|
| Reconnaissance | TA0043 | T1595 | TLS-001, TLS-002, REDIR-001, INFO-001, RECON-* | (base) | concluído |
| Discovery | TA0007 | T1518 | INFO-001 | Sidney | concluído |
| Initial Access | TA0001 | T1078 | FILE-002 | Sidney | concluído |
| Collection | TA0009 | T1213 | COLLECT-FTP-001, COLLECT-APIUSERS-001, COLLECT-APIFEEDBACK-001 | Beatriz | concluído |
| Execution | TA0002 | T1190 | EXEC-SSTI-001 | Beatriz | concluído |
| Privilege Escalation | TA0004 | T1068 | AUTHZ-001 | Sidney | concluído |
| Impact | TA0040 | T1565 | IMPACT-001 | Sidney | concluído |
| Credential Access | TA0006 | T1212 | CREDS-SQLI-LOGIN-001 | Beatriz | concluído |
| Resource Development | TA0042 | — | — | Beatriz | pendente |
| Persistence | TA0003 | — | — | Daniel | pendente |
| Lateral Movement | TA0008 | — | — | Beatriz | pendente |

Observações de mapeamento:
- `T1068` em Privilege Escalation é uma **aproximação consciente**: o check
  detecta a pré-condição (quebra de controle de acesso, OWASP A01), não executa
  exploração. `T1078` não é reutilizado aqui, pois já é de Initial Access.
- `T1565` em Impact é **pré-condição** de manipulação de dados: o check usa
  apenas `OPTIONS` (não-mutante) e nunca envia `PUT`/`DELETE`/`PATCH`.

## Fora de escopo

Decisão do projeto: as táticas abaixo **não serão implementadas como agentes**
no motor atual, por não terem mapeamento tecnicamente honesto em um avaliador
HTTP black-box (sem sessão autenticada, sem acesso ao host, sem rede interna).
Associá-las a checks existentes seria inflar a cobertura ATT&CK sem fundamento.

| Tática | ATT&CK | Motivo de estar fora de escopo |
|---|---|---|
| Stealth / Defense Evasion | TA0005 | A tática descreve o atacante **evadindo defesas**, não uma propriedade observável do alvo por fora. Sem agente/host instrumentado, não há sinal black-box honesto. |
| Defense Impairment | TA0005 (T1562 Impair Defenses) | "Enfraquecer defesas" pressupõe acesso para desativar controles. O que é observável por fora (ausência de CSP/HSTS/headers, WAF) já é coberto por outros checks em suas táticas próprias; recriar aqui seria duplicação e dupla contagem. |
| Command and Control | TA0011 | C2 descreve a comunicação de malware já instalado com a infraestrutura do atacante; não é observável por fora num scanner HTTP. Não há técnica ATT&CK honesta para "o alvo tem open redirect". O único check seguro relacionado (open redirect / CWE-601) não representa C2, então mapeá-lo aqui seria forçar a técnica. |
| Exfiltration | TA0010 | As técnicas reais (T1041/T1048/T1567) pressupõem o atacante já com os dados e um canal de saída; demonstrá-las exigiria de fato exfiltrar. Todo sinal seguro e observável por fora (dados em massa expostos sem autenticação) já é coberto por Collection (T1213). Implementar aqui recontaria T1213. |

Notas:
- Originalmente Stealth era de Sidney e Defense Impairment de Daniel; ambas
  caíam em TA0005. A remoção de escopo também resolve esse conflito de posse.
- Command and Control e Exfiltration eram de Sidney; foram descopadas pelos
  motivos acima, não por falta de tempo.
- Reabrir essas táticas só faz sentido se o produto passar a ter sessão
  autenticada ou capacidade de instrumentação/rede interna. O check de open
  redirect (CWE-601) continua sendo uma opção válida no futuro, desde que
  mapeado pela técnica que realmente representa, nunca como C2.

## Visibilidade da participação de cada agente (front-end)

Cada `Move` já carrega `recommended_by`, `attack_tactic_id`, `attack_tactic_name`,
`attack_technique_id`, `attack_technique_name`, `attack_url` e `exploitation_scenario`
desde que o agente recomendante foi registrado no `Pent`. Para evitar que o front
precise agregar isso manualmente, existe `GET /campaigns/{id}/agents`: retorna, por
agente, quantos lances recomendou, quantos foram aprovados/negados, quantos geraram
achado confirmado e quais técnicas MITRE foram observadas. Ver `API.md`, seção 0B.

## Pendências de coordenação

- Táticas que exigem host/rede interna (Resource Development, Persistence,
  Lateral Movement) têm o mesmo risco de inviabilidade black-box; tratar caso a
  caso com os responsáveis.
