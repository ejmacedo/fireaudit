# Fase 8 — Design de API
## Produto: FireAudit — v1 (produto completo, inclui escrita remota — ver nota abaixo)

Duas APIs distintas compõem o sistema, com públicos e contratos diferentes: a **API do dashboard** (consumida pelo frontend Next.js, autenticada por usuário) e a **API de ingestão** (consumida pelo agente, autenticada por `agent_token`). Tratá-las como uma API única seria confuso — os requisitos de autenticação, payload e frequência de chamada são completamente diferentes.

**Atualização de 2026-07-08 — escopo do v1 passou a incluir o produto completo:** a versão original desta fase tratava escrita remota de regras como "fora do MVP, v5". Isso mudou (`fase2-prd.md`, nota de escopo). As seções 2, 3 e 4 foram atualizadas com os novos endpoints de comando remoto (criação/confirmação/polling do agente), CRUD de `alert_rules`, e os filtros de dashboard — nenhum desses é mais hipotético.

---

## 1. Convenções gerais

- **Estilo:** REST sobre HTTPS, JSON em request/response (coerente com FastAPI, Fase 3).
- **Versionamento:** prefixo de URL (`/v1/...`) desde o primeiro endpoint — mesmo no MVP com um único cliente (o próprio frontend), isso evita o problema clássico de "esquecer de versionar e descobrir tarde demais que mudar um campo quebra todo mundo". Custo de adicionar `/v1` agora é zero; custo de adicionar depois é migrar todo cliente existente.
- **Formato de erro padronizado:**
```json
{
  "error": {
    "code": "FIREWALL_NOT_FOUND",
    "message": "Firewall não encontrado ou você não tem acesso a ele.",
    "details": null
  }
}
```
Código de erro em `SCREAMING_SNAKE_CASE` estável (para o frontend tratar programaticamente) + mensagem legível (não necessariamente para exibir direto ao usuário sem tradução i18n, mas útil em debug). **Nunca** vazar detalhes internos (stack trace, nome de tabela, query) no campo `details` em produção.
- **Paginação:** cursor-based (`?cursor=...&limit=...`) em endpoints de listagem que podem crescer (ex: histórico de snapshots, achados) — não offset-based, para evitar o problema clássico de páginas pulando/repetindo quando novos registros são inseridos entre requisições (relevante aqui porque snapshots chegam continuamente).
- **Datas:** sempre ISO 8601 em UTC no payload (`2026-07-08T14:30:00Z`) — consistente com RNF03 (Fase 2); conversão para timezone do usuário é responsabilidade do frontend, nunca do backend.

## 2. API de ingestão (agente → backend)

Esta é a API de maior volume e a mais sensível a falhas silenciosas — um bug aqui significa clientes achando que estão sendo monitorados quando não estão.

### `POST /v1/ingest/snapshot`
**Autenticação:** header `Authorization: Bearer <agent_token>` + header `X-Signature: <HMAC-SHA256 do body>` (Fase 5, seção 4).

**Request body (exemplo simplificado):**
```json
{
  "collected_at": "2026-07-08T14:30:00Z",
  "pfsense_version": "2.7.2",
  "system": { "cpu_pct": 12.4, "mem_pct": 38.1, "disk_pct": 55.0, "uptime_seconds": 934211 },
  "interfaces": [ { "name": "wan", "status": "up" }, { "name": "lan", "status": "up" } ],
  "rules": [ /* presente apenas se o tier permitir — decisão de o que enviar é do agente, não do backend, ver seção 5 */ ],
  "vpn_tunnels": [ /* idem */ ],
  "certificates": [ { "name": "webgui-cert", "expires_at": "2026-08-01T00:00:00Z" } ]
}
```

**Response (202 Accepted, não 200):** o snapshot é aceito e enfileirado, não processado sincronamente (Fase 3, fila via Postgres) — o agente não deveria esperar o motor de análise terminar para considerar o check-in bem-sucedido.
```json
{ "snapshot_id": "uuid", "status": "queued" }
```

**Por que 202 e não 200/201:** comunica corretamente ao cliente da API (o agente) que o processamento é assíncrono — importante para quem eventualmente escrever integrações próprias contra essa API entender o contrato real, não assumir sincronia que não existe.

**Códigos de erro específicos:** `401` (token inválido/revogado), `400` (payload malformado — validação Pydantic), `422` (assinatura HMAC não corresponde ao body — tratado separado de "payload malformado" porque indica um problema diferente: possível corrupção/adulteração em trânsito, não erro de programação do agente), `429` (rate limit, Fase 5).

### `GET /v1/ingest/agent-version`
Endpoint consultado pelo agente antes de decidir se faz auto-update (Fase 3, seção 7) — na verdade servido por um CDN estático (`latest.sh` + hash), não pela API principal, mas documentado aqui porque faz parte do contrato do agente. Não autenticado (é informação pública de versão, sem dado de cliente envolvido).

### `GET /v1/firewalls/{id}/commands/pending` — novo, 2026-07-08
**Autenticação:** mesmo `agent_token` da ingestão (Fase 5, seção 2 — escopo de leitura de comando, nunca de criação).

Chamado pelo agente no mesmo ciclo do push de snapshot (Fase 3, seção 7.1). Retorna no máximo 1 comando por vez (o agente processa um comando por ciclo, nunca em lote — reduz superfície de erro se algo der errado no meio da execução).

**Response (200):**
```json
{ "command": null }
```
ou, se houver um comando confirmado esperando:
```json
{
  "command": {
    "id": "uuid",
    "command_type": "create_rule",
    "payload": { "interface": "wan", "action": "block", "source": "203.0.113.0/24", "destination": "any", "protocol": "tcp", "port": 22 },
    "expires_at": "2026-07-08T15:00:00Z"
  }
}
```
Note que `preview` (campo interno usado na UI de confirmação, Fase 4 seção 2.11) não é enviado ao agente — o agente só recebe o `payload` estruturado necessário para executar, não o texto de preview voltado a humano.

### `POST /v1/firewalls/{id}/commands/{command_id}/result` — novo, 2026-07-08
**Autenticação:** mesmo `agent_token`.

Reporta o resultado da execução. **Request body:**
```json
{ "status": "applied", "before_state": { /* regra/config antes */ }, "after_state": { /* regra/config depois */ } }
```
ou, em caso de falha: `{ "status": "failed", "error": "mensagem legível do erro local do pfSense" }`.

Ao receber `status: "applied"`, o backend grava um `remote_change_logs` (Fase 4, seção 2.12) calculando o `record_hash` a partir do registro anterior da mesma cadeia — este é o único ponto do sistema que escreve nessa tabela, centralizado por desenho (evita duas rotas diferentes escrevendo no mesmo hash-chain e correndo risco de condição de corrida bagunçar a ordem).

## 3. API do dashboard (frontend → backend)

Autenticação: JWT no header `Authorization: Bearer <jwt>` (Fase 5, seção 2). Toda rota abaixo filtra implicitamente por `organization_id` do usuário autenticado — nunca um parâmetro de URL/query que o cliente possa manipular para acessar dado de outra organização.

### Autenticação
- `POST /v1/auth/register` — cria organização + usuário owner.
- `POST /v1/auth/login` — retorna JWT + refresh token.
- `POST /v1/auth/refresh` — troca refresh token por novo JWT.
- `POST /v1/auth/logout` — revoga refresh token.

### Firewalls
- `GET /v1/firewalls` — lista firewalls da organização (paginado). Campos retornados variam por tier (ver seção 5) — a mesma rota, resposta diferente, não duas rotas separadas.
- `POST /v1/firewalls` — cria firewall (nome), retorna `agent_token` **uma única vez** na resposta deste POST — depois disso, o token nunca é retornado em claro por nenhum outro endpoint (mesmo princípio de "write-only do ponto de vista de exibição" já estabelecido para a API key do pfSense na Fase 2, aplicado aqui ao agent_token).
- `GET /v1/firewalls/{id}` — detalhe (visão geral, sempre disponível em qualquer tier).
- `PATCH /v1/firewalls/{id}` — renomear.
- `DELETE /v1/firewalls/{id}` — soft-delete (Fase 4).
- `POST /v1/firewalls/{id}/rotate-token` — revoga o token atual, gera um novo, retorna-o uma única vez (mesma regra do POST de criação).

### Achados e dados de configuração (Pro+)
- `GET /v1/firewalls/{id}/findings?status=open&severity=critical&check_type=duplicate_rule` — filtrável por status/severidade/tipo de achado (o filtro `check_type` inclui o novo `duplicate_rule`, ver `fase2-prd.md` seção 6.3); retorna `403 UPGRADE_REQUIRED` (não `404`) se a organização for tier Free — distinção importa porque `403` com esse código específico é o que o frontend usa para acionar o teaser de upgrade (Fase 6-7, seção 4), enquanto `404` significaria "não existe".
- `PATCH /v1/firewalls/{id}/findings/{finding_id}` — atualizar `status` (ex: marcar como resolvido).
- `GET /v1/findings?severity=critical&status=open&firewall_status=online` — **novo (2026-07-08)**, listagem agregada cross-firewall (não por firewall específico) usada pelo dashboard principal — suporta os filtros combináveis de severidade, status do achado e status do firewall (Fase 2, seção 6.4); em Conta Multiempresa, aceita também `?organization_id=` para filtrar por empresa-cliente.
- `GET /v1/firewalls/{id}/rules` — regras de firewall, mesmo padrão de `403 UPGRADE_REQUIRED`.
- `GET /v1/firewalls/{id}/vpn-tunnels` — idem.

### Comandos remotos (escrita — Premium) — novo, 2026-07-08
- `POST /v1/firewalls/{id}/commands` — cria um `firewall_command` (`status = pending_confirmation`). Body: `{ "command_type": "create_rule", "payload": {...} }`. Response inclui o `preview` calculado pelo backend (texto legível do efeito da mudança, Fase 4 seção 2.11) — o frontend exibe esse preview antes de permitir a confirmação. Retorna `403 UPGRADE_REQUIRED` se tier não for Premium, `403 TWO_FACTOR_REQUIRED` se o usuário não tiver 2FA habilitado (Fase 5, seção 2).
- `POST /v1/firewalls/{id}/commands/{command_id}/confirm` — confirma o comando. Body exige o código 2FA do momento: `{ "totp_code": "123456" }` (step-up authentication, Fase 5 seção 11) — mesmo que o JWT da sessão já seja válido, este endpoint recusa sem o código. Muda `status` para `confirmed`. Retorna `409 COMMAND_EXPIRED` se `expires_at` já passou (15 min, Fase 4).
- `DELETE /v1/firewalls/{id}/commands/{command_id}` — cancela um comando ainda em `pending_confirmation` (usuário desistiu antes de confirmar).
- `GET /v1/firewalls/{id}/commands?status=applied` — histórico de comandos do firewall, com paginação cursor-based.
- `GET /v1/firewalls/{id}/change-log` — histórico de `remote_change_logs` (auditoria/rollback, Fase 4 seção 2.12), com `before_state`/`after_state` para a UI render