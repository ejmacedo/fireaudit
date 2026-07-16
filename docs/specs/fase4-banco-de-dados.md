# Fase 4 — Modelagem de Banco de Dados
## Produto: FireAudit — v1 (produto completo, ver nota de escopo abaixo)

Base para este desenho: PostgreSQL (decisão da Fase 3), `organizations` como entidade de primeira classe desde o dia 1 (decisão da Fase 1, item 2.4), tier definido por profundidade de acesso e não por quantidade de firewalls (decisão de negócio), e a distinção entre API key do pfSense (nunca exposta, criptografada) e token de ingestão do agente (Fase 3, seção 7) já refletida no schema.

**Atualização de 2026-07-08 — dois modelos de conta (Fase 2, seção 6.1):** o produto agora precisa de uma entidade acima de `organizations` para representar a conta/login que decide o tipo (Individual ou Multiempresa) e é o alvo real da cobrança. Isso muda a cardinalidade de `users` e `subscriptions` em relação à versão original desta fase — o restante do schema (firewalls, snapshots, findings, etc.) não é afetado, porque `organization_id` continua sendo a chave de isolamento multi-tenant em todas essas tabelas (Fase 5, seção 2), só ganha um nível a mais acima dela.

**Atualização de 2026-07-08 — escopo do v1 passou a incluir o produto completo (ver `fase2-prd.md`, nota de escopo no topo):** três blocos de schema que estavam adiados para fases futuras (v5/Premium) entram agora — (a) fila de comandos remotos para viabilizar edição de regra pelo tier Premium (seção 2.11, `firewall_commands`), (b) log de auditoria de escrita própria, append-only, mais rigoroso que `audit_logs` (seção 2.12, `remote_change_logs`), e (c) regras de alerta customizadas por limiar de métrica (seção 2.13, `alert_rules`). O achado `duplicate_rule` (6º tipo) também entra em `findings.check_type` (seção 2.6). Essas adições são tratadas com o mesmo rigor das tabelas originais — não são "esboço para depois".

---

## 1. Modelo conceitual (entidades e relacionamentos)

```
Account      1───N Organization   (1 para Conta Individual; 1..N para Conta Multiempresa)
Account      1───N User            (login pertence à conta, não direto à organização)
Account      1───1 Subscription   (billing agora agregado na conta, não na organização)
Organization 1───N Firewall
Firewall     1───N Snapshot
Snapshot     1───N Finding
Firewall     1───N AlertChannel
Finding      1───N AlertDelivery
Firewall     1───N AgentToken (histórico — permite rotação sem quebrar agente antigo em trânsito)
Organization 1───N AuditLog  (ações administrativas — preparação para RF05 da Fase 5)
Firewall     1───N FirewallCommand   (novo, 2026-07-08 — fila de comandos de escrita remota, tier Premium)
FirewallCommand 1───1 RemoteChangeLog (novo, 2026-07-08 — log de auditoria imutável da execução do comando)
Organization 1───N AlertRule         (novo, 2026-07-08 — regras de alerta customizadas por limiar de métrica)
AlertRule    1───N AlertDelivery     (reaproveita a mesma tabela de entrega de Finding, ver seção 2.8)
```

**Por que essa cardinalidade e não outra:**
- `Firewall` pertence a exatamente uma `Organization` (regra de negócio da Fase 2, seção 8) — não há tabela de associação N:N aqui, é FK direta. Simplicidade proposital: não existe caso de uso hoje de um firewall compartilhado entre organizações, e forçar N:N sem necessidade é overengineering.
- `Organization` pertence a exatamente uma `Account` — **nova relação desta rodada.** Uma Conta Individual tem exatamente 1 `Organization` (trava estrutural aplicada na camada de aplicação, ver seção 4); uma Conta Multiempresa pode ter N. Isso é o que sustenta, no schema, a decisão de negócio da Fase 2 seção 6.1.
- `User` pertence a uma `Account`, não mais direto a uma `Organization` — **mudança em relação à versão original desta fase.** Motivo: na Conta Multiempresa, o mesmo login (Priya) precisa administrar várias `Organization` diferentes; se o usuário continuasse com FK direta para uma única organização, não haveria como representar isso sem duplicar o usuário por empresa (ruim: mesmo login, senha e sessão deveriam servir para todas as empresas que ele administra). Para a Conta Individual, o efeito prático não muda nada (1 conta = 1 organização, então "usuário vê a organização da sua conta" e "usuário vê a única organização dele" são a mesma coisa). A regra de "1 usuário por conta" no MVP continua sendo constraint de aplicação, não física — mesmo racional já usado antes: v3 (RBAC) vai precisar de N usuários por conta, e não queremos migração de schema quando isso chegar.
- `Subscription` é 1-para-1 com `Account`, não mais com `Organization` — **mudança em relação à versão original desta fase.** Motivo direto: a Conta Multiempresa tem faixas de desconto por volume (Fase 2, seção 6.1) que dependem da contagem de organizações *da conta inteira*, então cobrar por assinatura Stripe separada por organização tornaria o cálculo de desconto por volume mais complicado do que precisa ser — uma assinatura Stripe por conta, com o valor calculado pela aplicação a partir da contagem de organizações ativas daquela conta, é o desenho mais simples que atende a regra de negócio.

## 2. Modelo lógico — tabelas

### 2.0 `accounts` — NOVA (2026-07-08, Fase 2 seção 6.1)
| Coluna | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| account_type | TEXT NOT NULL | `individual` \| `multiempresa` — declarado no cadastro, decisão inicial (Fase 2, seção 6.1) |
| tax_id | TEXT NULL | identificador fiscal (CNPJ/EIN/VAT/etc.) — obrigatório e usado para confirmação quando `account_type = 'multiempresa'`; NULL para `individual` (que informa dados de empresa na própria `organization`, não na conta) |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| updated_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| deleted_at | TIMESTAMPTZ NULL | soft-delete (ver seção 5) |

Esta é a entidade de topo — dono do login e do billing. `organizations` deixa de ser a raiz da árvore de tenancy e passa a ser filha de `accounts`.

### 2.1 `organizations`
| Coluna | Tipo | Notas |
|---|---|---|
| id | UUID PK | UUID em vez de serial — evita enumeração de IDs sequenciais em APIs públicas (mini-hardening que custa nada) |
| account_id | UUID FK → accounts.id NOT NULL | **nova coluna (2026-07-08)** — toda organização pertence a uma conta; ver seção 4 para a trava de "exatamente 1 organização" em contas `individual` |
| name | TEXT NOT NULL | nome da empresa — em Conta Multiempresa, é o nome usado para separar visualmente cada empresa-cliente na UI (Fase 2, seção 6.1) |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| updated_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| deleted_at | TIMESTAMPTZ NULL | soft-delete (ver seção 5) |

### 2.2 `users`
| Coluna | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| account_id | UUID FK → accounts.id NOT NULL | **mudou de `organization_id` para `account_id` nesta rodada** — login pertence à conta; ver seção 1 para o motivo (Multiempresa precisa de um usuário administrando N organizações) |
| email | CITEXT UNIQUE NOT NULL | `citext` evita bug clássico de duplicidade por caixa (Maria@x.com vs maria@x.com) |
| password_hash | TEXT NOT NULL | bcrypt/argon2 — nunca a senha, detalhamento em Fase 5 |
| role | TEXT NOT NULL DEFAULT 'owner' | hoje só existe 'owner'; coluna já existe para não precisar de migração quando RBAC (v2) chegar |
| created_at / updated_at / deleted_at | igual acima | |

### 2.3 `firewalls`
| Coluna | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| organization_id | UUID FK NOT NULL | índice (ver seção 4) |
| name | TEXT NOT NULL | apelido dado pelo usuário ("Firewall Matriz") |
| pfsense_version | TEXT NULL | preenchido pelo primeiro snapshot, não no cadastro |
| status | TEXT NOT NULL DEFAULT 'pending' | `pending` \| `active` \| `offline` — motor de achados (5ª checagem, Fase 1 item 2.6) escreve aqui |
| last_seen_at | TIMESTAMPTZ NULL | atualizado a cada check-in do agente; é o que alimenta o achado "agente offline" |
| created_at / updated_at / deleted_at | | |

Deliberadamente **não existe coluna `pfsense_api_key` nesta tabela nem em nenhuma outra tabela do backend** — essa é a decisão mais importante desta fase e vem direto da Fase 1 (item 2.1): a API key do pfSense é usada **localmente pelo agente** para consultar a API do próprio firewall; ela nunca sobe para a nuvem. O que o backend armazena é o **token de ingestão** (tabela `agent_tokens`), que é uma credencial diferente, gerada pelo backend, com escopo único de "aceitar POST deste firewall específico" — se vazar, o dano máximo é alguém conseguir mandar dados falsos de snapshot para aquele firewall, não conseguir *ler ou alterar* o firewall real. Isso elimina o cenário mais grave descrito na Fase 1 (backend como "central de inteligência" de API keys de clientes).

### 2.4 `agent_tokens`
| Coluna | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| firewall_id | UUID FK NOT NULL | |
| token_hash | TEXT NOT NULL | armazena o hash do token (SHA-256), nunca o token em claro — mesmo princípio de senha |
| status | TEXT NOT NULL DEFAULT 'active' | `active` \| `revoked` — permite rotação sem deletar histórico |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| revoked_at | TIMESTAMPTZ NULL | |

Tabela separada (não uma coluna em `firewalls`) porque token precisa ser **rotacionável** — se o usuário suspeitar de comprometimento, ele revoga e gera outro sem tocar no resto do cadastro do firewall, e mantemos histórico de tokens antigos para auditoria.

### 2.5 `snapshots`
| Coluna | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| firewall_id | UUID FK NOT NULL | |
| received_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| raw_payload | JSONB NOT NULL | payload bruto do agente — guardar o bruto além do parseado permite reprocessar se uma checagem tiver bug, sem esperar o próximo ciclo do cliente |
| processed_at | TIMESTAMPTZ NULL | NULL = ainda na fila (ver Fase 3, seção 6, fila baseada em Postgres) |
| processing_status | TEXT NOT NULL DEFAULT 'queued' | `queued` \| `processing` \| `done` \| `failed` |

Esta é a tabela de maior volume do sistema (um registro por check-in de cada firewall, potencialmente a cada poucos minutos) — decisões de índice e particionamento na seção 4 e 6 são focadas quase inteiramente nela.

### 2.6 `findings`
| Coluna | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| snapshot_id | UUID FK NOT NULL | |
| firewall_id | UUID FK NOT NULL | desnormalizado de propósito — evita join com `snapshots` em toda consulta do dashboard, que é a tela mais acessada do produto |
| check_type | TEXT NOT NULL | `risky_rule` \| `expiring_cert` \| `known_cve` \| `config_drift` \| `agent_offline` \| `duplicate_rule` (novo, 2026-07-08) — os 6 tipos da Fase 2 seção 6.3 |
| severity | TEXT NOT NULL | `low` \| `medium` \| `high` \| `critical` |
| details | JSONB NOT NULL | dados específicos do achado (ex: qual regra, qual CVE, data de expiração) |
| status | TEXT NOT NULL DEFAULT 'open' | `open` \| `acknowledged` \| `resolved` — permite ao usuário marcar como tratado sem esperar o achado desaparecer sozinho no próximo snapshot |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| resolved_at | TIMESTAMPTZ NULL | |

A desnormalização de `firewall_id` é a única desta fase e é intencional, não descuido — está documentada aqui exatamente para deixar claro que é uma escolha, coerente com o RNF04 (dashboard <2s com até 20 firewalls).

### 2.7 `alert_channels`
| Coluna | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| organization_id | UUID FK NOT NULL | canal é da organização, não do firewall — um webhook do Slack normalmente vale para toda a conta |
| type | TEXT NOT NULL | `email` \| `webhook_slack` \| `webhook_discord` \| `webhook_telegram` \| `webhook_generic` |
| config | JSONB NOT NULL | URL do webhook ou endereço de email — **nunca armazenar segredo de assinatura de webhook em texto puro**; ver Fase 5 |
| active | BOOLEAN NOT NULL DEFAULT true | |

### 2.8 `alert_deliveries`
| Coluna | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| finding_id | UUID FK NULL | **passou a ser nullable (2026-07-08)** — mutuamente exclusivo com `alert_rule_id` via `CHECK` (ver DDL, seção 3) |
| alert_rule_id | UUID FK NULL | **novo (2026-07-08)** — preenchido quando a entrega tem origem em `alert_rules` (seção 2.13), não em um achado automático |
| alert_channel_id | UUID FK NOT NULL | |
| status | TEXT NOT NULL DEFAULT 'pending' | `pending` \| `sent` \| `failed` |
| sent_at | TIMESTAMPTZ NULL | |
| error | TEXT NULL | |

Tabela de log de entrega — sem ela, "o webhook falhou e o cliente nunca soube que tinha um achado crítico" é um bug invisível e crítico de produto de segurança (a própria falha de alerta é o tipo de coisa que destrói confiança, ver Fase 1 seção 2.3 sobre confiança em produto de segurança).

### 2.9 `subscriptions`
| Coluna | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| account_id | UUID FK UNIQUE NOT NULL | **mudou de `organization_id` para `account_id` nesta rodada** — 1:1 com conta, não mais com organização (ver seção 1 para o motivo: faixas de desconto por volume da Conta Multiempresa dependem da contagem de organizações da conta inteira) |
| tier | TEXT NOT NULL DEFAULT 'free' | `free` \| `pro` \| `premium` para conta `individual` (premium vendável desde o v1 — inclui escrita remota de regra, ver Fase 8 seção 3; deixou de ser "reservado para versão futura" na atualização de 2026-07-08); para conta `multiempresa`, sempre efetivamente `pro`-equivalente por organização — `free` não se aplica a essa conta (Fase 2, seção 6.1), então esse valor default só é usado por contas `individual` |
| stripe_customer_id | TEXT NULL | |
| stripe_subscription_id | TEXT NULL | |
| status | TEXT NOT NULL DEFAULT 'active' | `active` \| `past_due` \| `canceled` |
| current_period_end | TIMESTAMPTZ NULL | |

**Como o valor cobrado é calculado para Conta Multiempresa:** a tabela não guarda um preço fixo — a aplicação calcula o valor da fatura a partir da contagem de `organizations` ativas (`deleted_at IS NULL`) daquela `account`, aplicando a tabela de faixas de desconto (Fase 2, seção 6.1) no momento de gerar a cobrança no Stripe. Isso evita duplicar a lógica de preço em duas camadas (banco e aplicação) — o banco só guarda o estado da assinatura (ativa, período, IDs do Stripe), o preço em si é regra de aplicação/Stripe.

### 2.10 `audit_logs`
| Coluna | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| organization_id | UUID FK NOT NULL | |
| user_id | UUID FK NULL | NULL possível para ações do sistema (ex: downgrade automático por falta de pagamento) |
| action | TEXT NOT NULL | ex: `firewall.created`, `subscription.upgraded`, `alert_channel.deleted` |
| metadata | JSONB NULL | |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |

Esta tabela registra eventos administrativos (ex: `firewall.created`, `subscription.upgraded`) — **não é** o "log imutável de escrita remota" pedido no RNF05 da Fase 2. Escrita remota de regra de firewall (tier Premium) tem sua própria tabela dedicada, mais rigorosa (seção 2.12, `remote_change_logs`), porque o padrão de prova exigido é mais alto do que o de um log administrativo comum.

### 2.11 `firewall_commands` — NOVA (2026-07-08, Fase 2 seção 6/RF10/RF12)
| Coluna | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| firewall_id | UUID FK NOT NULL | |
| user_id | UUID FK NOT NULL | quem solicitou o comando — nunca NULL, ação de escrita sempre tem autor humano identificado |
| command_type | TEXT NOT NULL | `create_rule` \| `update_rule` \| `delete_rule` (v1) — ver `fase8-design-api.md` para o payload de cada tipo |
| payload | JSONB NOT NULL | descrição declarativa da mudança pedida (ex: regra completa a criar/atualizar/excluir) — nunca um comando de shell arbitrário, sempre uma operação estruturada e validável |
| preview | JSONB NULL | resultado do preview de impacto (Fase 6-7) calculado pelo backend antes da confirmação — guardado para auditoria de "o que foi mostrado ao usuário antes de ele confirmar" |
| status | TEXT NOT NULL DEFAULT 'pending_confirmation' | `pending_confirmation` \| `confirmed` \| `sent_to_agent` \| `applied` \| `failed` \| `rolled_back` \| `expired` |
| confirmed_at | TIMESTAMPTZ NULL | momento da 2ª etapa de confirmação explícita (Fase 6-7/RNF05) |
| expires_at | TIMESTAMPTZ NOT NULL | comando `pending_confirmation` que não é confirmado em até 15 minutos expira automaticamente — evita comando "esquecido" ser aplicado horas depois, quando o contexto que o preview mostrou pode ter mudado |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| applied_at | TIMESTAMPTZ NULL | preenchido quando o agente confirma a aplicação (ver fluxo de polling, `fase3-arquitetura.md`) |

**Por que uma fila de comandos e não uma chamada direta backend→firewall:** a arquitetura de coleta já decidida (Fase 3) estabelece que o backend nunca alcança o firewall do cliente diretamente (API do pfSense só responde na LAN) — o mesmo princípio de "agente sempre inicia a conexão" que vale para o snapshot (push) vale para comandos (o agente busca comandos pendentes via polling no seu próprio ciclo, não é o backend que empurra um comando para dentro da rede do cliente). Isso mantém a regra de "nunca abrir porta/túnel no firewall do cliente" válida mesmo com escrita remota.

**Segurança do comando (detalhe em `fase5-seguranca.md`):** o agente só aceita processar comandos vindos de um `firewall_token` com escopo de escrita distinto do token de ingestão de snapshot (ver seção 2.4 e `fase5-seguranca.md`) — comprometer o token de ingestão (mais exposto, roda em Cron) não deve, por si só, permitir enviar comandos de escrita.

### 2.12 `remote_change_logs` — NOVA (2026-07-08, RNF05 da Fase 2)
| Coluna | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| firewall_command_id | UUID FK UNIQUE NOT NULL | 1:1 com o comando que originou a mudança |
| firewall_id | UUID FK NOT NULL | desnormalizado, mesmo racional de `findings.firewall_id` (seção 2.6) — tela de auditoria por firewall é consulta frequente |
| user_id | UUID FK NOT NULL | quem aplicou |
| before_state | JSONB NOT NULL | estado da regra/config antes da mudança — necessário para o rollback (RF10) |
| after_state | JSONB NOT NULL | estado depois da mudança |
| applied_at | TIMESTAMPTZ NOT NULL | |
| rolled_back_at | TIMESTAMPTZ NULL | |
| rolled_back_by_user_id | UUID FK NULL | |
| record_hash | TEXT NOT NULL | hash (SHA-256) do registro anterior + conteúdo deste registro (hash-chain simples) — detecta adulteração retroativa do log sem precisar de infraestrutura de blockchain/WORM storage, suficiente para o padrão de prova de um produto de auditoria de firewall no estágio atual |

**Por que esta tabela é separada de `audit_logs` (seção 2.10) e não uma extensão dela:** o padrão de prova exigido é diferente — `audit_logs` é para eventos administrativos (consulta ocasional, sem necessidade de hash-chain); `remote_change_logs` é a evidência de que o produto não alterou configuração de segurança do cliente sem rastro verificável, e é o dado que sustenta a funcionalidade de rollback (RF10) — por isso guarda `before_state`/`after_state` completos, não só uma descrição textual da ação como em `audit_logs.action`.

**É append-only por convenção de aplicação** (nenhuma rota de API expõe `UPDATE`/`DELETE` sobre esta tabela) — não há trigger físico de banco impedindo escrita direta via SQL administrativo porque, no estágio atual (VPS única, sem equipe de operações separada do fundador), a defesa real contra adulteração é o hash-chain (permite *detectar* se algo foi alterado fora do fluxo normal), não impedir fisicamente que o superusuário do Postgres escreva — isso é consistente com o nível de rigor já aceito em outras partes desta fase (ex: seção 4, trava de "1 organização por conta" também só na aplicação).

### 2.13 `alert_rules` — NOVA (2026-07-08, Fase 2 seção 6.2)
| Coluna | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| organization_id | UUID FK NOT NULL | regra pertence à organização, pode ser aplicada a 1 firewall específico ou a todos (`firewall_id` NULL) |
| firewall_id | UUID FK NULL | NULL = aplica a todos os firewalls atuais e futuros da organização; preenchido = só aquele firewall |
| metric | TEXT NOT NULL | `cpu_usage_pct` \| `ram_usage_pct` \| `disk_usage_pct` \| `temperature_c` (disponíveis em qualquer tier) \| `open_findings_count` \| `open_findings_critical_count` \| `vpn_tunnel_down_count` (exigem tier Pro+, ver regra de negócio na Fase 2 seção 6.2) |
| operator | TEXT NOT NULL | `gt` \| `gte` \| `lt` \| `lte` \| `eq` |
| threshold | NUMERIC NOT NULL | valor de comparação (ex: `50` para "50%") |
| duration_minutes | INTEGER NOT NULL DEFAULT 0 | condição precisa se manter verdadeira por N minutos consecutivos antes de disparar — evita alerta de ruído por picos momentâneos (0 = dispara no primeiro snapshot que satisfizer a condição) |
| alert_channel_id | UUID FK NOT NULL | reaproveita `alert_channels` (seção 2.7) — mesmo canal usado pelos achados automáticos |
| active | BOOLEAN NOT NULL DEFAULT true | |
| created_by_user_id | UUID FK NOT NULL | |
| created_at / updated_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**Como isso se conecta ao motor de análise (Fase 3):** `alert_rules` não é uma 7ª estratégia do `AnalysisCheck` — achados (`findings`) são conhecimento embutido do produto sobre o que é "arriscado"; `alert_rules` é avaliada por um worker separado e mais simples, que a cada snapshot processado consulta as regras ativas da organização daquele firewall e verifica se a métrica extraída do payload satisfaz a condição pelo tempo mínimo configurado — ao disparar, cria um registro reaproveitando `alert_deliveries` (seção 2.8), com uma FK opcional nova (`alert_rule_id`, nullable) além da já existente `finding_id` (também passa a ser nullable), já que agora uma entrega de alerta pode ter origem em um achado automático OU em uma regra customizada, nunca as duas.

**Regra de negócio (Fase 2 seção 6.2):** a validação de "métrica pertence ao conjunto que o tier atual expõe" é feita na camada de aplicação no momento de criar/editar a regra (mesmo padrão de outras travas de tier já usado neste schema) — não há constraint física, porque tier pode mudar (upgrade/downgrade) e a regra de alerta deveria idealmente ficar inativa (não ser deletada) se a organização fizer downgrade para um tier que não expõe mais aquela métrica.

## 3. Modelo físico — DDL essencial (resumo, não exaustivo)

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE accounts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  account_type TEXT NOT NULL DEFAULT 'individual',
  tax_id TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ NULL,
  CONSTRAINT chk_account_type CHECK (account_type IN ('individual', 'multiempresa'))
);

CREATE TABLE organizations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ NULL
);

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  email CITEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'owner',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ NULL
);

CREATE TABLE firewalls (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  pfsense_version TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  last_seen_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ NULL
);

CREATE TABLE agent_tokens (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  firewall_id UUID NOT NULL REFERENCES firewalls(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ NULL
);

CREATE TABLE snapshots (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  firewall_id UUID NOT NULL REFERENCES firewalls(id) ON DELETE CASCADE,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  raw_payload JSONB NOT NULL,
  processed_at TIMESTAMPTZ NULL,
  processing_status TEXT NOT NULL DEFAULT 'queued'
);

CREATE TABLE findings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  snapshot_id UUID NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
  firewall_id UUID NOT NULL REFERENCES firewalls(id) ON DELETE CASCADE,
  check_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  details JSONB NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ NULL
);

CREATE TABLE alert_channels (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  config JSONB NOT NULL,
  active BOOLEAN NOT NULL DEFAULT true
);

-- NOVA (2026-07-08) — criada antes de alert_deliveries porque esta a referencia
CREATE TABLE alert_rules (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  firewall_id UUID NULL REFERENCES firewalls(id) ON DELETE CASCADE,
  metric TEXT NOT NULL,
  operator TEXT NOT NULL,
  threshold NUMERIC NOT NULL,
  duration_minutes INTEGER NOT NULL DEFAULT 0,
  alert_channel_id UUID NOT NULL REFERENCES alert_channels(id) ON DELETE CASCADE,
  active BOOLEAN NOT NULL DEFAULT true,
  created_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT chk_alert_rule_operator CHECK (operator IN ('gt', 'gte', 'lt', 'lte', 'eq'))
);

CREATE TABLE alert_deliveries (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  finding_id UUID NULL REFERENCES findings(id) ON DELETE CASCADE,
  alert_rule_id UUID NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
  alert_channel_id UUID NOT NULL REFERENCES alert_channels(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending',
  sent_at TIMESTAMPTZ NULL,
  error TEXT NULL,
  CONSTRAINT chk_alert_delivery_origin CHECK (
    (finding_id IS NOT NULL AND alert_rule_id IS NULL) OR
    (finding_id IS NULL AND alert_rule_id IS NOT NULL)
  )
);

CREATE TABLE subscriptions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  account_id UUID NOT NULL UNIQUE REFERENCES accounts(id) ON DELETE CASCADE,
  tier TEXT NOT NULL DEFAULT 'free',
  stripe_customer_id TEXT,
  stripe_subscription_id TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  current_period_end TIMESTAMPTZ,
  CONSTRAINT chk_subscription_status CHECK (status IN ('active', 'past_due', 'canceled'))
);

CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- NOVA (2026-07-08) — fila de comandos de escrita remota, tier Premium (seção 2.11)
CREATE TABLE firewall_commands (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  firewall_id UUID NOT NULL REFERENCES firewalls(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),
  command_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  preview JSONB NULL,
  status TEXT NOT NULL DEFAULT 'pending_confirmation',
  confirmed_at TIMESTAMPTZ NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  applied_at TIMESTAMPTZ NULL,
  CONSTRAINT chk_firewall_command_type CHECK (command_type IN ('create_rule', 'update_rule', 'delete_rule')),
  CONSTRAINT chk_firewall_command_status CHECK (status IN (
    'pending_confirmation', 'confirmed', 'sent_to_agent', 'applied', 'failed', 'rolled_back', 'expired'
  ))
);

-- NOVA (2026-07-08) — log de auditoria imutável (hash-chain) da escrita remota (seção 2.12)
CREATE TABLE remote_change_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  firewall_command_id UUID NOT NULL UNIQUE REFERENCES firewall_commands(id),
  firewall_id UUID NOT NULL REFERENCES firewalls(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),
  before_state JSONB NOT NULL,
  after_state JSONB NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL,
  rolled_back_at TIMESTAMPTZ NULL,
  rolled_back_by_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  record_hash TEXT NOT NULL
);
```

## 4. Índices e travas de aplicação

**Índices** (cobrem os padrões de acesso mais frequentes citados em `fase9-10-performance-infra.md` seção 1.2: listagem por organização, achados por firewall+status+severidade):

```sql
CREATE INDEX idx_organizations_account_id ON organizations(account_id);
CREATE INDEX idx_users_account_id ON users(account_id);
CREATE INDEX idx_firewalls_organization_id ON firewalls(organization_id);
CREATE INDEX idx_agent_tokens_firewall_id ON agent_tokens(firewall_id);
CREATE INDEX idx_snapshots_firewall_id_received_at ON snapshots(firewall_id, received_at DESC);
CREATE INDEX idx_snapshots_processing_status ON snapshots(processing_status) WHERE processing_status = 'queued';
CREATE INDEX idx_findings_firewall_id_status_severity ON findings(firewall_id, status, severity);
CREATE INDEX idx_findings_snapshot_id ON findings(snapshot_id);
CREATE INDEX idx_alert_channels_organization_id ON alert_channels(organization_id);
CREATE INDEX idx_alert_rules_organization_id ON alert_rules(organization_id);
CREATE INDEX idx_alert_deliveries_alert_channel_id ON alert_deliveries(alert_channel_id);
CREATE INDEX idx_firewall_commands_firewall_id_status ON firewall_commands(firewall_id, status);
CREATE INDEX idx_remote_change_logs_firewall_id ON remote_change_logs(firewall_id);
CREATE INDEX idx_audit_logs_organization_id ON audit_logs(organization_id);
```

`idx_snapshots_processing_status` é um índice parcial (só sobre `queued`) porque é exatamente essa fatia da tabela que a fila baseada em Postgres (Fase 3, seção 6) consulta a cada ciclo — indexar o restante (`done`/`failed`, que crescem sem limite) seria custo sem benefício de consulta.

**Trava estrutural de "1 organização por conta `individual`" (citada nas seções 1 e 2.1):** não existe `CHECK`/`UNIQUE` físico no banco para isso — é validada em `application/CreateOrganization` (ver `CLAUDE.md`, seção de arquitetura), rejeitando a criação antes de chegar ao banco se a conta já tem 1 organização ativa (`deleted_at IS NULL`) e `account_type = 'individual'`. Ficou de fora do banco pelo mesmo racional já usado em outras regras desta fase (ex: métrica de `alert_rules` fora do tier, seção 2.13): é uma regra de negócio que precisa de contexto (contagem de organizações ativas daquela conta específica) mais barato de expressar e testar na camada de aplicação do que em uma constraint declarativa, e mantém a simetria com o resto do isolamento multi-tenant, que já é centralizado em `application` (Fase 5, seção 2) e não em constraints de banco.

**Isolamento multi-tenant (`organization_id`):** toda query de dado de organização (firewalls, snapshots, findings, alert_channels, alert_rules, firewall_commands, remote_change_logs, audit_logs) filtra por `organization_id` do usuário autenticado — centralizado na camada de `application`, nunca decisão pontual de endpoint (Fase 5, seção 2). Os índices acima existem tanto por performance quanto porque são a mesma coluna usada nesse filtro em praticamente toda consulta do produto.

## 5. Soft-delete

`organizations`, `accounts`, `users` e `firewalls` usam `deleted_at TIMESTAMPTZ NULL` em vez de `DELETE` físico — motivo: são as entidades que sustentam histórico de billing (Stripe já referencia `account_id`/`organization_id` em disputas e reembolsos), auditoria (`audit_logs`/`remote_change_logs` referenciam `user_id`/`firewall_id` que não podem virar referência quebrada) e o "gatilho de reconsideração" documentado no LGPD/GDPR (`fase5-seguranca.md`) de que hard-delete/anonimização real é item pendente antes do lançamento comercial — soft-delete é o estado intermediário aceitável para o estágio atual, não a solução final de privacidade.

Tabelas de fato/log (`snapshots`, `findings`, `alert_deliveries`, `firewall_commands`, `remote_change_logs`, `audit_logs`) **não** têm `deleted_at` — são apagadas via `ON DELETE CASCADE` quando o `firewall`/`organization` pai é removido (hard-delete em cascata), exceto `remote_change_logs`, que é append-only por convenção de aplicação (seção 2.12) e cuja política de retenção ainda não está definida (mesma pendência de LGPD/GDPR citada acima).

Toda consulta de listagem nas tabelas com soft-delete deve filtrar `deleted_at IS NULL` — não há índice parcial dedicado para isso ainda porque o volume de registros soft-deleted é baixo no estágio atual (mesma lógica de "otimização sem problema correspondente" já usada em `fase9-10-performance-infra.md` seção 1.3); reconsiderar se o volume de contas/organizações canceladas crescer o suficiente para distorcer os índices da seção 4.

## 6. Particionamento (deliberadamente adiado)

`snapshots` é a tabela de maior volume do sistema (seção 2.5) e a única candidata real a particionamento neste schema — mas particionamento (por `firewall_id` ou por intervalo de `received_at`) está **deliberadamente fora do v1** (`CLAUDE.md`, lista "o que explicitamente NÃO existe no v1").

**Por que adiar é seguro:** no volume esperado do MVP (poucos clientes, poucos firewalls por cliente, check-in a cada poucos minutos — RNF04 da Fase 2 assume até 20 firewalls por organização), o número de linhas em `snapshots` fica em uma faixa que o Postgres sem particionamento atende bem, com os índices da seção 4 já cobrindo o padrão de acesso mais comum (leitura do snapshot mais recente por firewall).

**Gatilho de reconsideração:** o mesmo tipo de sinal usado nas outras decisões de infraestrutura adiada desta fase (cache em memória → Redis, rate limiting em memória → Redis, ver `fase9-10-performance-infra.md` seção 1.3) — quando o volume de linhas em `snapshots` começar a degradar o tempo de resposta do dashboard (RNF04, meta de <2s) ou o tempo de vacuum/backup da tabela crescer a ponto de impactar a janela de manutenção (`fase12-operacao-manutencao.md`), particionar por intervalo de tempo (mensal, por exemplo) é o próximo passo natural. Não implementar preventivamente — é overengineering para o volume atual, mesmo princípio já aplicado a outras decisões desta fase (ex: ausência de tabela de associação N:N em `firewalls`, seção 1).