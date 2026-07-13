# CLAUDE.md — FireAudit

Este arquivo é o ponto de entrada obrigatório. Leia-o por completo antes de escrever qualquer código. Ele resume as decisões já fechadas em um processo de especificação de 12 fases (documentos completos em `docs/specs/`) — **não reabra decisões já tomadas sem justificativa explícita e sem avisar o usuário**, especialmente as marcadas como "decisão fechada" abaixo. Se algo parecer contraditório ou insuficiente, pare e pergunte antes de assumir.

**Atualização de escopo — 2026-07-08 (leia antes de qualquer outra coisa):** o "MVP" deixou de ser um recorte read-only faseado. O v1 agora é o **produto completo**: inclui escrita remota de configuração (criação/edição/exclusão de regra, tier Premium, com preview + confirmação 2FA), criador de alertas customizados por limiar (`alert_rules`), uma 6ª estratégia de análise (`duplicate_rule`), e filtros combináveis de dashboard. Nenhuma dessas quatro funcionalidades é "futuro" — são parte do primeiro lançamento. Qualquer trecho abaixo que ainda mencionar essas funcionalidades como "v5", "Premium reservado" ou "fora do MVP" está desatualizado; os documentos em `docs/specs/` são a fonte de verdade mais recente e já refletem essa mudança em todas as 12 fases.

## O que é o FireAudit

SaaS de auditoria e compliance contínua para firewalls **pfSense** (v1 não cobre OPNsense). Um agente leve instalado no próprio pfSense coleta dados via API local e faz *push* (HTTPS) para o backend na nuvem no mesmo ciclo em que também faz *poll* de comandos remotos pendentes — nunca é o backend que abre conexão para o cliente, mesmo para escrita (ver seção de escrita remota abaixo). O backend roda um motor de análise sobre cada snapshot recebido e gera "achados" (findings) de **6 tipos**: regra arriscada, certificado expirando, CVE conhecido pela versão, drift de configuração, agente offline, e regra duplicada (`duplicate_rule`).

O v1 **inclui escrita remota de configuração** (criar/editar/excluir regra de firewall), reservada ao tier Premium, sempre por trás de um fluxo de preview + confirmação com 2FA obrigatório (step-up authentication) — nunca é o backend agindo direto sobre o firewall do cliente sem esse consentimento explícito por comando. Ver seção "Escrita remota" mais abaixo para o desenho completo; `docs/specs/fase3-arquitetura.md` (seção 7.1), `fase5-seguranca.md` (seção 11) e `fase8-design-api.md` (seção 3) têm o racional e contrato completos.

Público-alvo: administradores de TI e consultores/MSP que operam pfSense, majoritariamente fora do Brasil, self-service, cobrança em USD via Stripe.

## Stack técnica (decisão fechada — Fase 3)

| Camada | Escolha | Não usar |
|---|---|---|
| Backend | Python + FastAPI (async) | Node, Go, Django |
| Banco | PostgreSQL | MongoDB ou qualquer NoSQL |
| Fila/jobs | Tabela de jobs no próprio Postgres (ou Redis+`arq` se o orçamento permitir) | RabbitMQ, Kafka — overengineering neste estágio |
| Frontend | Next.js (React), majoritariamente client-side rendering na área autenticada | Vue, Svelte, SPA sem framework |
| Estado no frontend | Estado local de componente + React Query/SWR para cache de requisição | Redux ou state management complexo |
| Estilo | Tailwind CSS | CSS-in-JS complexo, styled-components |
| Componentes UI | shadcn/ui (Radix UI + Tailwind) + `lucide-react` para ícones | Material UI, Ant Design, Chakra, Bootstrap — trazem CSS/tema próprio que conflita com Tailwind |
| Hospedagem | Docker Compose em VPS única (OCI) | Kubernetes |
| CI/CD | GitHub Actions (lint → testes → build → push registry → deploy via SSH) | Pipelines blue-green/canary |

Orçamento de infraestrutura alvo: ~USD 2-13/mês (teto USD 20/mês). Isso deve pesar em qualquer escolha de dependência nova: prefira a opção mais simples e barata que resolve o problema real, não a mais "correta" em teoria. Ver `docs/specs/fase3-arquitetura.md` e `fase9-10-performance-infra.md` para o racional completo, incluindo os pontos onde essas escolhas **vão precisar evoluir** (documentados de propósito — não "descobertos" depois).

## Arquitetura de código (decisão fechada — Fase 3)

Monólito modular, não microsserviços. Clean Architecture leve (não dogmática) dentro de `backend/app/`:

```
backend/app/
  domain/          → entidades e regras de negócio puras (Account, Organization, Firewall, Finding, User)
                     SEM import de framework, banco ou HTTP. Se um arquivo aqui importar FastAPI
                     ou SQLAlchemy, é sinal de que a camada foi violada.
  application/      → casos de uso (RegisterAccount, CreateOrganization, IngestSnapshot,
                     RunComplianceCheck, UpgradeSubscription) — orquestram o domínio.
                     Toda verificação de "recurso pertence a esta organization_id" vive aqui,
                     centralizada — nunca deixada para o endpoint decidir individualmente.
  infrastructure/    → implementações concretas: repositórios Postgres, cliente Stripe,
                     envio de email/webhook, KMS/secrets.
  api/               → rotas FastAPI, schemas Pydantic de request/response, autenticação.
  workers/           → jobs assíncronos (processar snapshot, enviar alerta, gerar PDF).
```

Não criar abstrações/interfaces para tudo (ex: um `IEmailSender` só se cogitarmos trocar provedor de fato). Aplique SOLID nos pontos que importam: Single Responsibility nos casos de uso, Dependency Inversion na fronteira domínio↔infraestrutura. Não é checklist obrigatório por classe.

Padrões de projeto já decididos e com motivo real (não decorativos):
- **Repository Pattern** para acesso a dados.
- **Strategy Pattern** para o motor de análise — cada um dos **6** tipos de checagem (incluindo `duplicate_rule`) implementa uma interface comum `AnalysisCheck.run(snapshot) -> List[Finding]`. Adicionar uma 7ª checagem não deve exigir tocar nas outras 6.
- **Adapter Pattern** para absorver diferenças de formato entre versões do pacote RESTAPI do pfSense — também usado para o payload de escrita (criação/edição de regra), não só leitura.
- **Command Pattern** para escrita remota — cada operação (`create_rule`/`update_rule`/`delete_rule`) é um `FirewallCommand` imutável, serializado e enfileirado, só executado pelo agente depois de confirmado com 2FA. Não implementar escrita remota como chamada de função direta/síncrona — o objeto de comando precisa sobreviver ao intervalo entre "usuário confirma" e "agente executa no próximo polling", e precisa ser auditável como entidade própria (ver `FirewallCommand`/`RemoteChangeLog` abaixo).

A avaliação de `alert_rules` (criador de alertas customizados) roda como um passo separado do worker de snapshot, **não** como uma 7ª `AnalysisCheck` — ela produz `AlertDelivery` direto a partir de comparação métrica×limiar, um conceito diferente do que `Finding`/`AnalysisCheck` representam. Ver `docs/specs/fase3-arquitetura.md` seção 6.

## Modelo de dados e regras de negócio críticas (decisão fechada — Fase 2/4)

**Hierarquia de tenancy (mudou em 2026-07-08, é a versão atual — não usar nenhum desenho anterior):**

```
Account  1───N Organization   (exatamente 1 se account_type='individual'; 1..N se 'multiempresa')
Account  1───N User            (login pertence à conta, não direto à organização)
Account  1───1 Subscription    (billing agregado na conta)
Organization 1───N Firewall
Firewall 1───N Snapshot → N Finding
Firewall 1───N FirewallCommand 1───1 RemoteChangeLog   (escrita remota, tier Premium)
Organization 1───N AlertRule 1───N AlertDelivery       (criador de alertas customizados)
```

Dois tipos de conta, declarados no cadastro e não alternáveis livremente depois:
- **Individual**: 1 empresa só. Tiers por profundidade de acesso: Free (métricas básicas) / Pro (achados completos, regras, VPN) / **Premium (escrita remota + histórico de alterações — vendável desde o v1, não é mais reservado para versão futura)**. A trava de "exatamente 1 organization" é **de aplicação, não do banco** (nenhum `CHECK`/`UNIQUE` físico) — validar em `application/CreateOrganization`, rejeitando antes de chegar ao banco se a conta já tem 1 organização ativa.
- **Multiempresa**: N empresas-cliente, cada uma sempre em profundidade total (equivalente a Pro). Não existe tier Free para Multiempresa. Preço da 1ª empresa = preço do Individual-Pro; empresas adicionais com desconto por volume (ver `fase2-prd.md` seção 6.1 para a tabela — valores são placeholder, não cobrar como se fossem finais).

Regra que NUNCA deve ser violada, mesmo que pareça conveniente numa implementação futura: **a API key do pfSense do cliente nunca é armazenada no backend**, nem em texto plano nem criptografada. O agente usa a API key localmente, só o *resultado* sobe. O que o backend guarda é `agent_tokens.token_hash` — uma credencial diferente, gerada pelo backend, com escopo único de "aceitar POST deste firewall". Se você (Claude Code) se deparar com alguma tarefa que pareça exigir guardar a API key do pfSense no backend, pare e avise — é sinal de que algo foi mal entendido, não uma necessidade real.

Schema completo, DDL, índices e o racional de cada decisão (inclusive o que foi deliberadamente adiado, como particionamento de `snapshots`) está em `docs/specs/fase4-banco-de-dados.md`. Leia antes de escrever a primeira migration.

## Segurança — pontos não-negociáveis (decisão fechada — Fase 5)

- Senha de usuário: `argon2id`. JWT curto (15 min) + refresh token rotativo e revogável.
- Ingestão do agente: `Authorization: Bearer <agent_token>` + header `X-Signature` com HMAC-SHA256 do body, calculado com chave derivada do `agent_token`. Backend recalcula e compara antes de aceitar.
- `alert_channels.config` (segredos de webhook) precisa de criptografia reversível via KMS (não hash — o valor precisa ser lido de volta para enviar o alerta).
- Toda query de dado de organização filtra por `organization_id` do usuário autenticado, centralizado na camada de `application` — nunca decisão pontual de endpoint. Isso é o ponto de maior risco do produto (vazamento cross-tenant); trate como tal.
- Rate limiting em memória de processo no MVP (ex: `slowapi`) é aceitável — não introduzir API Gateway dedicado agora.
- CORS restrito ao domínio oficial do frontend, sem wildcard.
- **2FA é opcional no login geral, mas obrigatório (step-up authentication) no momento de confirmar qualquer `firewall_command`** — mesmo com JWT de sessão válido, `POST .../commands/{id}/confirm` sem `totp_code` correto é sempre rejeitado, e um usuário Premium sem 2FA habilitado não consegue nem criar nem confirmar comando (`403 TWO_FACTOR_REQUIRED`), sem caminho alternativo.
- **Separação de escopo do `agent_token` é um dos controles mais importantes do produto e não deve ser implementado por engano com o mesmo middleware genérico:** o `agent_token` (mesmo usado na ingestão) só autoriza *leitura* de comandos já confirmados via polling (`GET .../commands/pending`) — ele nunca pode criar nem confirmar um `firewall_command`. Criação/confirmação exigem JWT de usuário + tier Premium + 2FA. Um teste que provasse que `agent_token` consegue criar/confirmar comando é falha de segurança crítica, não bug funcional comum (ver `docs/specs/fase11-qualidade-testes.md` seção 1).
- `remote_change_logs` usa hash-chain (`record_hash` depende do conteúdo do registro anterior) para detectar adulteração do histórico de auditoria — é o único mecanismo de tamper-detection do produto e a única tabela em que a gravação é centralizada num único ponto do código (o handler de `POST .../commands/{id}/result`), nunca duas rotas diferentes escrevendo nela.

Detalhe completo (modelo de ameaças, LGPD/GDPR, backup, seção 11 "Segurança da escrita remota") em `docs/specs/fase5-seguranca.md`.

## API — convenções (decisão fechada — Fase 8)

- REST sobre HTTPS, JSON, prefixo `/v1/` desde o primeiro endpoint.
- Formato de erro padronizado: `{"error": {"code": "SCREAMING_SNAKE_CASE", "message": "...", "details": null}}`. Nunca vazar stack trace/nome de tabela/query em `details` em produção.
- Paginação cursor-based em listagens que crescem (nunca offset-based).
- Datas sempre ISO 8601 UTC no payload; conversão de timezone é responsabilidade do frontend.
- `GET /v1/firewalls/{id}/findings` (e rotas equivalentes de dado sensível) retornam `403 UPGRADE_REQUIRED` para tier Free — nunca `404`. O frontend usa esse código específico para acionar o teaser de upgrade.
- `agent_token` só é retornado em texto claro uma única vez, no momento de criação/rotação — nunca de novo depois.
- Endpoint de ingestão responde `202 Accepted` (processamento é assíncrono via fila), não `200`.
- **Escrita remota (Premium):** `POST /v1/firewalls/{id}/commands` cria o comando e retorna um `preview` em texto humano gerado pelo backend (nunca o frontend monta esse texto) — `403 UPGRADE_REQUIRED` se não for Premium, `403 TWO_FACTOR_REQUIRED` se sem 2FA. `POST .../commands/{id}/confirm` exige `totp_code` no body, `409 COMMAND_EXPIRED` se `expires_at` (15 min) já passou. O agente só lê comandos já confirmados via `GET /v1/firewalls/{id}/commands/pending` (no máximo 1 por ciclo, nunca em lote) e reporta resultado via `POST .../commands/{command_id}/result` — este último é o único ponto do sistema que grava em `remote_change_logs`. Adicionar header `Idempotency-Key` em `POST .../commands` antes de codificar o endpoint (evita retry de rede duplicando comando) — item pendente identificado na Fase 8, ainda não refletido no contrato formal, mas obrigatório na implementação.
- **Criador de alertas:** CRUD completo em `/v1/alert-rules` + `POST /v1/alert-rules/{id}/test` (avalia contra o snapshot mais recente sem esperar o próximo ciclo). Métrica fora do tier da organização é rejeitada na criação (`403 UPGRADE_REQUIRED`), nunca aceita e ignorada silenciosamente depois.

Contrato completo de cada endpoint em `docs/specs/fase8-design-api.md`.

## UX/UI — princípios que toda tela deve seguir (decisão fechada — Fase 6-7)

- Público tecnicamente cético, não iniciante — pode usar terminologia técnica direta, mas nunca esconder o que o produto faz com os dados do cliente.
- Todo estado vazio tem uma ação clara de próximo passo, nunca é só uma mensagem passiva.
- Todo erro é acionável (diz o que fazer), nunca só "algo deu errado".
- Dashboard ordenado por urgência (achados críticos primeiro), não alfabético/cronológico.
- Todo alerta (email/webhook) leva a um deep link direto ao contexto do problema, nunca só "faça login para ver".
- Loading usa skeleton screens em listas/cards, spinner só em ações pontuais de botão.
- Existe um mockup HTML navegável cobrindo as 14 telas principais em `docs/specs/mockup-completo-telas.html` — abra no navegador antes de implementar qualquer tela para entender o layout, fluxo e nomenclatura esperados. Use-o como referência visual, mas não como verdade absoluta de detalhe de implementação — ele é wireframe funcional (Tailwind via CDN, `showScreen()` JS simples), não o código final do Next.js.
- **Edição remota de regra nunca implica aplicação instantânea na UI:** a tela de status pós-confirmação é explícita sobre o intervalo de até 15 minutos até o próximo polling do agente — não criar copy que sugira tempo real. Botão "Cancelar" visível enquanto o comando está em `pending_confirmation`.
- **Criador de alertas customizados** usa o exemplo "RAM > 50%" (do próprio Eduardo) como placeholder pré-preenchido no formulário vazio, não só em documentação.
- **Filtros de dashboard** (severidade, status do firewall, empresa-cliente em Multiempresa) são combináveis e persistem como query params na URL (`?severity=critical&status=offline`).

Fluxos completos (edição remota, criador de alertas, filtros, histórico de alterações com diff e rollback) em `docs/specs/fase6-7-ux-ui.md` seções 2.4, 2.5, 3.4, 3.7, 3.8.

## Biblioteca de componentes e padrões visuais (decisão fechada — 2026-07-08)

O mockup e a Fase 6-7 definem fluxo, estados e comportamento — mas nenhum dos dois trava **qual biblioteca de componentes usar**. Sem essa decisão, cada tela seria implementada com botão/modal/tabela/input reinventados do zero, o que produz inconsistência visual, retrabalho e mais superfície para bugs de acessibilidade. Esta seção fecha essa lacuna.

**Escolha: [shadcn/ui](https://ui.shadcn.com/)** (componentes baseados em Radix UI + Tailwind CSS, modelo "copy-paste" — o código do componente entra no próprio repositório em `frontend/components/ui/`, não é uma dependência de node_modules que se atualiza por fora).

Por que esta e não outra:
- Já é 100% compatível com a stack fechada na Fase 3 (Next.js + Tailwind) — não introduz um segundo sistema de estilo nem tema próprio para reconciliar com Tailwind, ao contrário de Material UI/Ant Design/Chakra/Bootstrap.
- Acessibilidade (foco de teclado, ARIA, contraste) vem por padrão via Radix UI — atende a exigência de acessibilidade pragmática da Fase 6-7 seção 5 sem esforço manual extra.
- É o padrão de fato mais usado em projetos Next.js gerados por ferramentas de IA (incluindo Claude Code/Fable) — reduz a chance de o modelo "inventar" markup divergente entre telas, que é exatamente o risco que motivou esta seção.
- Modelo copy-paste (não é um pacote npm de UI) permite customizar cada componente livremente sem lutar contra overrides de tema de uma lib fechada — importante porque o produto tem necessidades visuais específicas (badges de severidade, cores sev-critical/high/medium/low já definidas no mockup).

Componentes shadcn/ui a instalar já no Fase 0/7 do `PLANO-DESENVOLVIMENTO.md` (mapeados a partir das telas do mockup, não é lista teórica): `button`, `input`, `label`, `form`, `card`, `table`, `badge`, `dialog` (modais, ex: comparação de planos), `dropdown-menu`, `tabs` (abas do detalhe de firewall), `skeleton` (loading, Fase 6-7 seção 4), `alert` (banners de erro/agente offline), `toast`/`sonner` (feedback de ações como "copiar comando", "teste de webhook enviado"), `select`, `separator`, `avatar`.

Regras de uso, para manter consistência entre telas:
- Nunca escrever HTML de botão/input/modal "cru" com classes Tailwind soltas quando existir o componente shadcn/ui equivalente — usar o componente, mesmo que pareça mais rápido escrever a div na hora.
- Cores de severidade (`sev-critical`/`sev-high`/`sev-medium`/`sev-low`, já definidas como paleta no mockup) devem ser centralizadas como variante do componente `badge` (ex: `<Badge variant="critical">`), não repetidas como classes Tailwind soltas em cada tela onde um achado aparece.
- Ícones: `lucide-react` (biblioteca companion oficial do shadcn/ui, já usada nos artifacts) — não misturar com outra biblioteca de ícones no mesmo projeto.
- Se uma tela do mockup precisar de um componente fora dessa lista, adicionar via `npx shadcn@latest add <componente>` (traz só o componente pedido) em vez de instalar uma lib de UI paralela para resolver um caso pontual.

Isso não substitui a Fase 6-7 (`docs/specs/fase6-7-ux-ui.md`) — ela continua sendo a fonte de verdade para fluxo/comportamento/estados. Esta seção resolve apenas "com qual kit visual construir o que a Fase 6-7 descreve".

## O que explicitamente NÃO existe no v1 (por decisão, não por esquecimento)

**Atualizado em 2026-07-08:** escrita remota, criador de alertas, `duplicate_rule` e filtros de dashboard **saíram** desta lista — fazem parte do v1 (ver seções acima). Não implemente nada da lista abaixo sem confirmação explícita do usuário:

- RBAC multiusuário dentro da mesma organização (v2, renumerado) — diferente de Multiempresa, que já existe desde v1.
- Suporte a OPNsense (v3/v4, ver `fase2-prd.md` seção 12 para numeração atual).
- 2FA **funcional para o fluxo geral de login continua opcional** — mas 2FA é **obrigatório e deve ser implementado desde o v1** para o fluxo de confirmação de `firewall_command` (step-up authentication, ver seção de Segurança acima). Não confundir os dois: "2FA opcional no login" não significa "2FA não implementado" — o campo `two_factor_secret`/`two_factor_enabled` e o fluxo TOTP de confirmação são obrigatórios no v1 por dependerem da escrita remota.
- Ambiente de staging dedicado — mitigado por teste manual de Eduardo contra pfSense real antes de cada release que toque código de escrita (ver `fase11-qualidade-testes.md` seção 7).
- Testes de carga formais ou pentest pago.
- Particionamento de tabelas.
- Mecanismo de rollout gradual/canário para o agente (% de agentes, versão fixada por organização) — mitigado por teste manual prévio contra pelo menos uma instância pfSense real antes de publicar em `latest.sh` (`fase12-operacao-manutencao.md` seção 3).
- Alerta dedicado (push) para fila de snapshot travada ou fila de comandos remotos travada — mitigado por checagem manual periódica no v1; **gatilho de reconsideração é o primeiro cliente Premium pagante** para a fila de comandos (prioridade mais alta que a fila de snapshot equivalente, ver `fase12-operacao-manutencao.md` seção 1).
- Página de status pública (Statuspage) — comunicação de incidente é por email direto aos clientes afetados.

## Testes (decisão fechada — Fase 11)

Pirâmide invertida: maioria unitária (sobretudo as **6** estratégias do motor de análise, incluindo `duplicate_rule` — devem rodar sem banco, é o retorno prático da Clean Architecture), integração moderada (Postgres efêmero via `testcontainers`, isolamento multi-tenant testado com 2 organizações reais no mesmo teste; fluxo completo de comando remoto criação→confirmação 2FA→polling→resultado→`remote_change_logs` também entra aqui), poucos E2E (fluxo de ativação, upgrade Free→Pro, e **fluxo completo de edição remota** — este último é E2E crítico por ser a funcionalidade de maior risco do produto, não capricho de cobertura). `pytest`+`pytest-asyncio` no backend, `Vitest`/`Playwright` no frontend.

**A fila de comandos remotos é a maior prioridade de teste do projeto** (maior até que o motor de análise) — casos que não podem faltar, além dos já conhecidos (HMAC inválido, token revogado, tier Free acessando rota Pro, cross-tenant leak): `agent_token` não pode criar/confirmar `firewall_command` (só ler via polling); confirmação sem `totp_code` válido é sempre rejeitada; comando expirado nunca é entregue ao agente (checagem na query de leitura, não só no job de limpeza); comando não pode ser aplicado duas vezes (idempotência via `UNIQUE` em `remote_change_logs.firewall_command_id`); adulterar um registro de `remote_change_logs` quebra a verificação da cadeia de hash a partir daquele ponto; usuário sem 2FA não consegue usar escrita remota mesmo sendo Premium. Lista completa em `docs/specs/fase11-qualidade-testes.md` seção 3 — não pular esses.

## Como este repositório está organizado

```
FireAudit-App/
  CLAUDE.md                    → este arquivo
  PLANO-DESENVOLVIMENTO.md     → sequência de implementação recomendada, passo a passo
  docker-compose.yml           → esqueleto de infra local (api, worker, postgres, frontend)
  .env.example                 → variáveis necessárias, sem valores reais
  docs/specs/                  → as 12 fases de especificação completas + mockup HTML (fonte de verdade
                                  para qualquer decisão de produto/arquitetura/negócio — inclui escrita
                                  remota, criador de alertas, duplicate_rule e filtros desde o v1)
  backend/                     → API FastAPI + workers, estrutura Clean Architecture acima
  frontend/                    → Next.js
  agent/                       → script do agente que roda no pfSense (Cron, push HTTPS)
  infra/                       → Nginx, scripts de deploy, CI
```

Quando uma decisão de produto/negócio parecer ambígua ao implementar, a resposta provavelmente já existe em `docs/specs/` — leia o documento da fase relevante antes de assumir ou perguntar ao usuário. Quando não existir, pare e pergunte; não invente regra de negócio nova silenciosamente (ex: valores de preço, limites numéricos, nomes de campos de API).

## Nomenclatura e idioma

Código, nomes de variáveis, endpoints, mensagens de commit e comentários: **inglês**. Interface do produto (texto exibido ao usuário final): inglês no MVP — público é majoritariamente internacional (RNF03, Fase 2) — mas preparar i18n desde o início (nunca string fixa espalhada pelo código, usar arquivo de tradução mesmo com um único idioma). Documentos de especificação em `docs/specs/` estão em português porque foram escritos para o fundador (Eduardo); isso não deve influenciar o idioma do produto.
