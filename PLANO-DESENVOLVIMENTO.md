# Plano de Desenvolvimento — FireAudit v1 (produto completo)

Este documento existe porque tentar implementar as 12 fases de especificação de uma vez é a forma mais provável de travar ou gerar código inconsistente. A regra é: **siga a ordem abaixo, um passo por vez, e não avance para o próximo sem o critério de "pronto" do passo atual estar satisfeito.** Se um passo revelar que uma decisão anterior (deste plano ou de `docs/specs/`) estava errada, pare e avise o usuário em vez de improvisar uma correção silenciosa.

Cada passo referencia o(s) documento(s) de `docs/specs/` que contém o detalhe — leia o trecho relevante antes de implementar, não confie só no resumo deste plano.

**Atualização de 2026-07-08 — escopo mudou de "MVP read-only faseado" para "produto completo desde o v1":** este plano foi reestruturado para incluir, como parte do primeiro corte (não como fase futura), escrita remota de regra (tier Premium, com 2FA obrigatório), criador de alertas customizados por limiar, a 6ª estratégia de análise (`duplicate_rule`) e filtros combináveis de dashboard. As Fases 1, 6 e 7 abaixo foram atualizadas, e as Fases 9-13 são inteiramente novas — não existiam na versão anterior deste plano, que tratava essas quatro funcionalidades como "depois deste corte inicial". Ver `CLAUDE.md` para o resumo consolidado das decisões que motivam essa mudança.

---

## Fase 0 — Esqueleto do repositório (sem lógica de negócio ainda)

**Objetivo:** ter o monorepo rodando localmente com containers vazios, antes de escrever qualquer regra de negócio.

1. Backend FastAPI mínimo: projeto Python com a estrutura de pastas de `CLAUDE.md` (`domain/application/infrastructure/api/workers`), um único endpoint `GET /v1/health` que verifica conexão com o banco.
2. Postgres via Docker Compose (usar `docker-compose.yml` já presente na raiz como ponto de partida, ajustar se necessário).
3. Frontend Next.js mínimo: uma página estática de "Coming soon", sem lógica. Já inicializar `shadcn/ui` neste passo (`npx shadcn@latest init`, depois `add button` como smoke test) — ver `CLAUDE.md` seção "Biblioteca de componentes e padrões visuais". Fazer isso agora, mesmo sem tela real ainda, evita que a Fase 7 comece sem a base de componentes configurada.
4. `docker compose up` sobe os 4 serviços (api, worker vazio, postgres, frontend) sem erro.

**Critério de pronto:** `curl localhost:8000/v1/health` retorna `200` com o banco respondendo; frontend acessível no navegador.

## Fase 1 — Schema de banco e migrations

**Ref:** `docs/specs/fase4-banco-de-dados.md` (schema completo e DDL), seção 4 (índices).

1. Configurar ferramenta de migration (ex: Alembic).
2. Criar migration inicial com **todas** as tabelas da Fase 4, incluindo as de escrita remota e alertas customizados desde já (não deixar para uma migration futura): `accounts`, `organizations`, `users`, `firewalls`, `agent_tokens`, `snapshots`, `findings`, `firewall_commands`, `remote_change_logs`, `alert_rules`, `alert_channels`, `alert_deliveries`, `subscriptions`, `audit_logs`.
3. Aplicar os índices da seção 4 do documento (não pular — em especial `snapshots(processing_status)` parcial, `agent_tokens(firewall_id, status)`, `firewall_commands(firewall_id, status)` parcial e `firewall_commands(status, expires_at)` parcial, que são consultados em todo request/polling do caminho crítico).
4. Garantir a constraint `UNIQUE` em `remote_change_logs.firewall_command_id` desde esta migration — ela é o mecanismo de idempotência que impede um comando de ser aplicado duas vezes (ver `fase11-qualidade-testes.md` seção 3), não algo para adicionar depois.
5. Não implementar particionamento de `snapshots` (decisão explícita de adiar, seção 6 do documento).

**Critério de pronto:** `alembic upgrade head` roda limpo em banco vazio; todas as FKs e constraints de `CHECK`/`UNIQUE` da seção 3 existem de fato no banco (verificar com `\d+` no psql, não só assumir que a migration "deve" ter funcionado), incluindo a `UNIQUE` de `remote_change_logs.firewall_command_id`.

## Fase 2 — Domínio e casos de uso: cadastro de conta

**Ref:** `fase2-prd.md` seção 6.1 e 8 (regras de negócio), `fase4-banco-de-dados.md` seção 4 (constraint de aplicação).

1. Entidades de domínio puras: `Account`, `Organization`, `User` (sem import de framework/banco).
2. Caso de uso `RegisterIndividualAccount`: cria `Account(account_type='individual')` + 1 `Organization` + 1 `User`, tudo em uma transação.
3. Caso de uso `RegisterMultiempresaAccount`: cria `Account(account_type='multiempresa', tax_id=...)` + 1 `User`, **sem** organização ainda (a 1ª empresa é adicionada depois, num passo separado de onboarding, ver mockup tela 3).
4. Caso de uso `CreateOrganization`: valida a trava — se `account.account_type == 'individual'` e já existe 1 organização ativa, rejeita antes de tocar o banco. Este é o único lugar do sistema onde essa regra deve existir; não duplicar a checagem em outro caso de uso.
5. Endpoints: `POST /v1/auth/register` (cobre os dois tipos de conta conforme payload).

**Critério de pronto:** teste automatizado prova que uma 2ª tentativa de `CreateOrganization` numa conta Individual é rejeitada, e que a mesma operação numa conta Multiempresa é aceita.

## Fase 3 — Autenticação e autorização do dashboard

**Ref:** `fase5-seguranca.md` seção 2.

1. `POST /v1/auth/login` com `argon2id`, JWT de 15 min + refresh token rotativo.
2. Rate limiting no login (5 tentativas/15min por IP+email, `slowapi`).
3. Middleware/dependency do FastAPI que resolve `user → account → organizations acessíveis` a partir do JWT — este é o ponto único de autorização multi-tenant citado no CLAUDE.md, implemente-o uma vez e reuse em toda rota, nunca repita a lógica.

**Critério de pronto:** teste de integração prova isolamento cross-tenant: usuário da Organization A nunca recebe dado da Organization B, mesmo manipulando o parâmetro de URL.

## Fase 4 — Cadastro de firewall + token de ingestão

**Ref:** `fase8-design-api.md` seção 3 (Firewalls), `fase4-banco-de-dados.md` seção 2.4 (`agent_tokens`).

1. `POST /v1/firewalls` — cria firewall, gera `agent_token`, retorna em claro **uma única vez**.
2. `POST /v1/firewalls/{id}/rotate-token` — revoga o atual, gera novo.
3. Garantir que `token_hash` (nunca o token em claro) é o que persiste.

**Critério de pronto:** teste prova que o token não é recuperável em texto claro por nenhum outro endpoint além do de criação/rotação.

## Fase 5 — Endpoint de ingestão + verificação HMAC + fila

**Ref:** `fase8-design-api.md` seção 2, `fase5-seguranca.md` seção 4, `fase3-arquitetura.md` seção 6 (fila via Postgres).

1. `POST /v1/ingest/snapshot`: valida `agent_token`, recalcula HMAC do header `X-Signature` e compara, salva `raw_payload` em `snapshots` com `processing_status='queued'`, responde `202` com `snapshot_id`.
2. Worker separado (mesmo código-base, processo distinto) faz polling da tabela `snapshots` filtrando pelo índice parcial `WHERE processing_status='queued'`.

**Critério de pronto:** teste prova que payload com HMAC inválido é rejeitado com `422` e nunca chega a ser enfileirado; teste prova que token revogado é rejeitado com `401`.

## Fase 6 — Motor de análise: 1 checagem ponta a ponta, depois as outras 5

**Ref:** `fase3-arquitetura.md` seção 5 (Strategy Pattern), `fase2-prd.md` seção 6 (**6** tipos de achado), `fase11-qualidade-testes.md` seção 3.

Implementar **apenas a checagem `agent_offline` primeiro** (é a mais simples — não depende de parsear regras de firewall, só de comparar `last_seen_at` com um limiar). Isso prova o fluxo completo (worker → `AnalysisCheck.run()` → `Finding` salvo) antes de investir nas outras 5, que são mais complexas de parsear corretamente.

1. Interface `AnalysisCheck.run(snapshot) -> List[Finding]`.
2. Implementação de `AgentOfflineCheck`.
3. Worker chama todas as estratégias registradas (hoje, só uma) após processar um snapshot.

**Critério de pronto:** teste unitário do `AgentOfflineCheck` roda sem banco (prova que a Clean Architecture está de fato desacoplada); teste de integração prova que um firewall sem check-in há mais do que o limiar gera exatamente 1 `Finding`, não duplicado em execuções repetidas.

**Só depois de validar este ciclo completo**, implementar as outras 5 checagens (`risky_rule`, `expiring_cert`, `known_cve`, `config_drift`, **`duplicate_rule`**) — cada uma como uma nova classe, sem tocar nas anteriores (é exatamente o requisito que justificou o Strategy Pattern). `duplicate_rule` compara a tupla efetiva de regras na mesma interface (ignorando campos irrelevantes como comentário/nome) — caso de borda mais importante: duas regras que só diferem no comentário devem ser tratadas como duplicadas.

## Fase 7 — Dashboard mínimo (frontend)

**Ref:** `fase6-7-ux-ui.md` seções 3.3 e 3.4, `docs/specs/mockup-completo-telas.html` telas 6-9, `CLAUDE.md` seção "Biblioteca de componentes e padrões visuais" (lista de componentes shadcn/ui a instalar).

1. Tela de login consumindo `POST /v1/auth/login` — usar `form`/`input`/`label`/`button` do shadcn/ui, não markup cru.
2. Dashboard Individual: lista de firewalls com status e contagem de achados, estados de loading (skeleton)/vazio/erro conforme a tabela da Fase 6-7 seção 3.3 — usar `card`/`skeleton`/`badge`/`alert` do shadcn/ui.
3. Tela de detalhe do firewall com achados agrupados por severidade — usar `tabs` para as abas (Visão Geral/Achados/Regras & VPN/Configurações nesta fase — Histórico de Alterações entra na Fase 11 abaixo, junto com escrita remota) e `badge` com variante por severidade (crítico/alto/médio/baixo), não classes Tailwind soltas repetidas por tela.

**Critério de pronto:** fluxo manual completo funciona: registrar conta Individual → criar firewall → simular 1 POST de ingestão via curl/Postman → ver o achado `agent_offline` aparecer no dashboard depois do limiar de tempo.

## Fase 8 — Billing (Free/Pro, Individual)

**Ref:** `fase2-prd.md` seção 6, `fase8-design-api.md` seção 3 (Billing).

1. Stripe Checkout para upgrade Free→Pro.
2. Webhook do Stripe (`POST /v1/webhooks/stripe`) atualizando `subscriptions.tier`.
3. Middleware de tier: rotas de dado sensível retornam `403 UPGRADE_REQUIRED` para Free.

**Critério de pronto:** teste E2E (modo de teste do Stripe) prova o fluxo completo de upgrade e a liberação de acesso imediata via webhook.

## Fase 9 — 2FA (TOTP) e step-up authentication

**Ref:** `fase5-seguranca.md` seções 2 e 11.

Pré-requisito de toda a Fase 11 (escrita remota) — implementar antes, não em paralelo, porque a escrita remota depende deste controle existir e estar testado.

1. Habilitação de 2FA por usuário: geração de secret TOTP, QR code, confirmação de código antes de marcar `two_factor_enabled=true`.
2. Endpoint/dependency de step-up: qualquer rota que exigir 2FA (a única no v1 é a confirmação de `firewall_command`, mas desenhar a dependency de forma reutilizável) aceita um `totp_code` no body e valida contra o secret armazenado, **mesmo com JWT de sessão válido**.
3. Middleware de tier: rotas de escrita remota checam `tier == 'premium'` e `two_factor_enabled == true`, retornando `403 UPGRADE_REQUIRED`/`403 TWO_FACTOR_REQUIRED` conforme o caso — nunca um caminho que aceite sem 2FA mesmo sendo Premium.

**Critério de pronto:** teste prova que uma tentativa de ação step-up sem 2FA habilitado é sempre rejeitada, mesmo com JWT válido e mesmo sendo tier Premium.

## Fase 10 — Criador de alertas customizados (`alert_rules`)

**Ref:** `fase8-design-api.md` seção 3 (Regras de alerta customizadas), `fase3-arquitetura.md` seção 6, `fase6-7-ux-ui.md` seções 2.5 e 3.7.

Implementar antes da escrita remota (Fase 11) porque é mais simples e não depende de 2FA nem do agente — bom próximo corte vertical depois do billing.

1. CRUD `alert_rules` (`GET`/`POST`/`PATCH`/`DELETE /v1/alert-rules`), com validação de tier na criação (métrica fora do tier → `403 UPGRADE_REQUIRED`).
2. Worker de avaliação: passo **separado** do worker de `AnalysisCheck` (não uma 7ª estratégia) — roda depois do processamento do snapshot, compara métrica×operador×limiar×duração, gera `AlertDelivery` direto se disparar.
3. `POST /v1/alert-rules/{id}/test` — avalia contra o snapshot mais recente sem esperar o próximo ciclo.
4. Tela "Regras customizadas" (aba dentro de Alertas) com o exemplo "RAM > 50%" pré-preenchido no estado vazio.
5. Comportamento de downgrade: regra cuja métrica ficou fora do tier após um downgrade para de disparar silenciosamente (sem erro visível), não deleta a regra — testar isso explicitamente.

**Critério de pronto:** teste prova que `POST /v1/alert-rules/{id}/test` avalia corretamente contra o snapshot mais recente; teste prova que uma regra pré-existente cujo tier caiu para de disparar sem erro visível ao usuário.

## Fase 11 — Escrita remota de regra (tier Premium) — a funcionalidade de maior risco do produto

**Ref:** `fase3-arquitetura.md` seções 3, 5 e 7.1, `fase5-seguranca.md` seção 11, `fase8-design-api.md` seções 2 e 3, `fase6-7-ux-ui.md` seções 2.4 e 3.4, `fase11-qualidade-testes.md` seções 1 e 3 (ler por completo antes de começar — esta fase tem a maior densidade de casos de teste obrigatórios do documento).

Depende da Fase 9 (2FA) já estar implementada e testada. Não paralelizar com a Fase 9.

1. Domínio: `FirewallCommand` imutável (Command Pattern) com `command_type` restrito a `create_rule`/`update_rule`/`delete_rule`, e `RemoteChangeLog` com `record_hash` calculado a partir do registro anterior da mesma cadeia (hash-chain).
2. `POST /v1/firewalls/{id}/commands` — cria comando (`status=pending_confirmation`), calcula e retorna `preview` em texto humano gerado pelo backend. Adicionar header `Idempotency-Key` desde a primeira versão deste endpoint (item pendente identificado na Fase 8 de especificação — não deixar para depois).
3. `POST /v1/firewalls/{id}/commands/{id}/confirm` — exige `totp_code`, muda status para `confirmed`, retorna `409 COMMAND_EXPIRED` se `expires_at` (15 min) já passou.
4. `DELETE /v1/firewalls/{id}/commands/{id}` — cancela comando em `pending_confirmation`.
5. `GET /v1/firewalls/{id}/commands/pending` — **autenticado por `agent_token`, nunca por JWT** — retorna no máximo 1 comando `confirmed` não expirado (checagem de expiração na própria query, não só no job de limpeza). Implementar num módulo/dependency **separado** do usado para criar/confirmar comando, para eliminar por construção o risco de reusar o middleware de ingestão nessa rota de escrita.
6. `POST /v1/firewalls/{id}/commands/{id}/result` — recebe resultado do agente, grava `remote_change_logs` (único ponto de escrita nessa tabela em todo o sistema), atualiza status para `applied`/`failed`. Idempotência garantida pela `UNIQUE` de `firewall_command_id` (Fase 1 deste plano) — segundo `POST` para o mesmo `command_id` é no-op ou rejeitado, nunca gera um segundo log.
7. Job periódico de expiração: marca comandos `pending_confirmation`/`confirmed` vencidos como `expired`.
8. Agente (ver Fase 12 abaixo): no mesmo ciclo do push de snapshot, faz `GET .../commands/pending`; se houver comando, busca regra atual via API local do pfSense, aplica usando a API key local (que nunca sai da rede do cliente), reporta via `POST .../result`.
9. Frontend: fluxo de criação/edição de regra (Fase 6-7 seção 2.4) com preview, gate de 2FA, tela de status explícita sobre o intervalo de até 15 min, botão cancelar; aba "Histórico de Alterações" com diff simples e botão "Desfazer" (cria novo comando inverso, nunca edita o log original).

**Critério de pronto — não avançar sem todos estes testes passando:** `agent_token` não consegue criar/confirmar comando (só ler via polling); confirmação sem `totp_code` válido é sempre rejeitada; comando expirado nunca aparece em `GET .../commands/pending` mesmo antes do job de limpeza rodar; dois `POST .../result` para o mesmo `command_id` nunca geram dois `remote_change_logs`; adulterar um registro de `remote_change_logs` quebra a verificação da cadeia a partir daquele ponto; usuário Premium sem 2FA não consegue criar nem confirmar comando.

## Fase 12 — Agente: polling de comandos + rollout sem canário

**Ref:** `fase3-arquitetura.md` seção 7, `fase12-operacao-manutencao.md` seções 1 e 3.

1. Estender o agente (script que já faz push de snapshot) para, no mesmo ciclo, fazer `GET .../commands/pending` e processar o comando conforme Fase 11 item 8 acima.
2. Processo obrigatório antes de publicar qualquer nova versão do agente em `latest.sh`: testar manualmente contra pelo menos uma instância pfSense real (ambiente do próprio Eduardo) — nunca publicar direto para todos os clientes como primeiro teste. Não implementar rollout gradual/canário agora (decisão explícita de adiar).

**Critério de pronto:** teste manual prova que o agente aplica um comando `create_rule` de teste contra um pfSense real e reporta sucesso corretamente; teste manual prova que um comando `delete_rule` mal formado é reportado como `failed` com mensagem de erro legível, sem quebrar o próximo ciclo do agente.

## Fase 13 — Filtros de dashboard

**Ref:** `fase6-7-ux-ui.md` seção 3.8, `fase8-design-api.md` seção 3 (`GET /v1/findings` agregado cross-firewall).

Pode ser implementada em paralelo com qualquer fase acima a partir da Fase 7 (não tem dependência de escrita remota nem de alertas) — colocada por último neste plano só porque é a de menor risco/complexidade, não porque depende de algo anterior.

1. `GET /v1/findings?severity=...&status=...&firewall_status=...` (+ `organization_id` em Multiempresa).
2. Barra de filtros combináveis no dashboard, persistindo estado como query params na URL (`?severity=critical&status=offline`).
3. Estado "nenhum resultado após filtro" distinto do estado vazio geral (Fase 6-7 seção 3.8) — botão "Limpar filtros".

**Critério de pronto:** recarregar a página com filtros na URL mantém o mesmo resultado filtrado; combinar 2+ filtros retorna a interseção correta, não a união.

## O que fica para depois deste corte inicial (não implementar ainda sem revisitar este plano)

- Fluxo de Multiempresa completo (seletor de empresas, billing por volume) — a Fase 2 deste plano já cria a `Account` multiempresa, mas a experiência completa de múltiplas organizações por conta é o próximo corte vertical depois que o corte Individual estiver funcionando ponta a ponta.
- Alertas por email/webhook (canais, não as regras customizadas da Fase 10 — canais e disparo básico de `Finding` podem já existir antes, mas o fluxo completo de configuração de canal é priorizado depois do motor de análise estar confiável).
- Relatório PDF.
- Qualquer coisa da lista "O que explicitamente NÃO existe no v1" do `CLAUDE.md` (RBAC multiusuário, OPNsense, staging dedicado, testes de carga formais/pentest pago, particionamento, rollout gradual do agente, alerta dedicado para fila travada, status page pública).

## Regra geral entre passos

Ao final de cada fase deste plano, rode a suíte de testes completa antes de avançar — não acumule fases sem rede de segurança, já que não há staging (decisão da Fase 9-10) e os testes automatizados são a única validação antes de produção.
