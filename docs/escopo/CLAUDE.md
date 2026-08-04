Antes de aplicar qualquer regra deste documento, leia primeiro o Escopo Oficial em `docs/escopo/FireAudit-Escopo-Geral.md`. O Escopo é a visão do produto e tem precedência sobre qualquer detalhe técnico descrito aqui.

# FireAudit — CLAUDE.md

Documento técnico oficial do projeto. Todo desenvolvimento deve seguir fielmente o que está descrito abaixo.

---

## Stack oficial

### Backend
- Python 3.12
- FastAPI (`fastapi>=0.115.0`) + Uvicorn (`uvicorn[standard]`)
- SQLAlchemy 2.0 assíncrono (`sqlalchemy[asyncio]`) com driver `asyncpg`
- Alembic para migrações
- Pydantic v2 + `pydantic-settings` (configuração via `app/core/config.py`)
- Argon2 (`argon2-cffi`) para hash de senha
- `python-jose[cryptography]` para JWT (access token) + token de refresh opaco (SHA-256)
- `slowapi` para rate limiting
- `stripe` para billing (isolado em `app/infrastructure/stripe_client.py`)
- `httpx` (cliente HTTP para testes/integrações)
- `sentry-sdk[fastapi]` para observabilidade de erros (ativado apenas se `SENTRY_DSN` estiver configurado)
- `pyotp` e `qrcode[pil]` presentes nas dependências (`backend/pyproject.toml`)
- Dev/test: `pytest`, `pytest-asyncio`, `pytest-cov`, `testcontainers[postgres]`, `aiosqlite`, `ruff`, `mypy`

### Frontend
- Next.js 14 (App Router) + React 18 + TypeScript
- TailwindCSS + `tailwindcss-animate`
- Radix UI (avatar, dialog, dropdown-menu, label, select, separator, slot, tabs, toast)
- `@tanstack/react-query` para data fetching
- `react-hook-form` + `zod` + `@hookform/resolvers` para formulários/validação
- `axios` como cliente HTTP (`lib/api/client.ts`)
- `lucide-react` (ícones), `sonner` (toasts), `class-variance-authority` / `clsx` / `tailwind-merge`
- Testes: `vitest` (unitário) + `@testing-library/react` e `@playwright/test` (e2e)

### Banco de dados
- PostgreSQL 16 (`postgres:16-alpine`, definido em `docker-compose.yml`)
- Único banco de dados do sistema — string de conexão em `Settings.database_url` (`app/core/config.py`), padrão `postgresql+asyncpg://...`
- Acesso via SQLAlchemy assíncrono; schema versionado por Alembic (`backend/alembic/versions/`)

### Infraestrutura
- Docker Compose (`docker-compose.yml`) com 4 serviços: `postgres`, `api` (FastAPI via Uvicorn), `worker` (`python -m app.workers.snapshot_worker`), `frontend` (Next.js)
- CI/CD via GitHub Actions (`.github/workflows/ci.yml`):
  - `lint-backend` (ruff check + ruff format --check)
  - `lint-frontend` (npm run lint)
  - `test-backend` (pytest + cobertura via Codecov)
  - `build-backend` / `build-frontend` (build e push de imagens para `ghcr.io`, apenas na branch `main`)
  - `deploy` (SSH para VPS, `docker compose pull && docker compose up -d`)
- Registro de imagens: GitHub Container Registry (`ghcr.io`)
- Sentry para observabilidade de erros do backend (opcional, via `SENTRY_DSN`)

---

## Estrutura do repositório

- **Backend:** `backend/app/`, organizado em camadas de Clean Architecture:
  - `domain/` — entidades (`entities.py`) e erros de domínio; sem imports de framework
  - `application/` — `protocols.py` (interfaces/`Protocol`), `use_cases/`, `checks/` (motor de análise)
  - `infrastructure/` — implementações concretas: `repositories.py` (SQLAlchemy), `security.py`, `database.py`, `stripe_client.py`, `email_client.py`
  - `api/` — `main.py` (app FastAPI), `deps.py`, `deps_auth.py`, `routers/`, `schemas/`
  - `workers/` — `snapshot_worker.py` (processamento assíncrono de snapshots)
- **Frontend:** `frontend/` — Next.js App Router (`app/`), componentes (`components/`), integrações de API (`lib/api/`)
- **Agente:** `agent/agent.py` — script Python executado localmente no pfSense (via cron/`install.sh`)
- **Escopo:** `docs/escopo/FireAudit-Escopo-Geral.md`
- **Graphify:** `graphify-out/`
- **Skill:** `.claude/skills/fireaudit-architect/`

---

## Decisões arquiteturais permanentes

Decisões que dificilmente mudarão. Cada uma está fundamentada em evidência concreta do código atual.

1. **Monólito modular.** O backend é uma única aplicação FastAPI (`app/api/main.py`), organizada internamente em camadas (`domain`/`application`/`infrastructure`/`api`/`workers`) dentro do mesmo processo e deploy — não há microserviços.

2. **Comunicação via agente.** O backend nunca se conecta diretamente ao firewall. Um agente (`agent/agent.py`) roda localmente no pfSense e empurra snapshots para `POST /v1/ingest/snapshot`, assinando o payload com HMAC-SHA256 (`agent.py::sign_payload`, verificado em `ingest.py` via `HMACVerifier.verify`).

3. **Multi-tenant.** Hierarquia `Account` → `Organization` → `Firewall`. Todo acesso a dados é escopado por tenant (`AuthContext.organization_ids` em `deps_auth.py`; `FirewallRepository.list_active_for_org` filtra por `organization_id`).

4. **PostgreSQL como banco principal.** Único banco de dados do sistema, definido em `Settings.database_url` e provisionado como `postgres:16-alpine` no `docker-compose.yml`; schema versionado via Alembic.

5. **Backend nunca inicia conexão com o firewall.** O agente é a única parte do sistema que fala com o pfSense; a chave da API do pfSense nunca é armazenada no backend (docstring explícito em `agent.py`: "Never stores pfSense API key on the backend — used locally only.").

6. **Separação de escopo de credencial.** Autenticação de usuário (JWT → `AuthContext`) e autenticação de agente (`agent_token` → `AgentContext`) são mecanismos distintos e não-intercambiáveis (`deps_auth.py`). Endpoints de ingestão só aceitam `AgentContext` (`get_current_agent`), nunca `AuthContext`.

7. **Domínio livre de framework (Clean Architecture).** `domain/entities.py` não importa FastAPI/SQLAlchemy. As `checks` de análise reforçam essa regra explicitamente (`agent_offline.py`: "No FastAPI/SQLAlchemy imports here on purpose — this is pure domain logic").

8. **Repository Pattern via `Protocol`.** Toda persistência é acessada por interfaces definidas em `application/protocols.py` (`AccountRepository`, `FirewallRepository`, `FindingRepository`, etc.), implementadas em `infrastructure/repositories.py`. Casos de uso dependem apenas dessas interfaces.

9. **Strategy Pattern para o motor de análise.** Cada verificação de segurança (`agent_offline`, `risky_rule`, `expiring_cert`, `known_cve`, `duplicate_rule`, `config_drift`) é uma classe independente que implementa `AnalysisCheck.run()`, registrada em lista no worker (`snapshot_worker.py::_build_analyze_snapshot`).

10. **Fila baseada em Postgres, sem broker dedicado.** Processamento assíncrono via `Snapshot.processing_status` (`queued` → `processing` → `done`), consumido por polling com `SELECT ... FOR UPDATE SKIP LOCKED` (`SqlAlchemySnapshotRepository.list_queued`). Não há Redis/RabbitMQ/Celery no sistema.

11. **Gateway de pagamento isolado.** `infrastructure/stripe_client.py` é o único módulo do backend autorizado a importar o SDK `stripe` diretamente (docstring explícito: "This module is the ONLY place in the backend allowed to import `stripe` directly"). Todo o restante do código depende apenas do protocolo `PaymentGateway`.

---

## Regras de processo

Regras operacionais válidas para todo desenvolvimento neste repositório, independente da funcionalidade sendo construída.

1. **Bloqueios de infraestrutura/rede: avisar, nunca insistir.** Quando um erro for claramente de infraestrutura/rede que exige ação fora do alcance do agente (porta bloqueada, firewall corporativo, domínio/CDN inacessível, proxy), é aceitável rodar 1-2 testes de diagnóstico para confirmar a causa. Uma vez confirmado que é bloqueio de infra, a ação correta é parar e perguntar como proceder — nunca ficar retentando a mesma operação, nem aplicar unilateralmente uma correção de arquitetura/dependência (remover pacote, mudar base image) sem aprovação.

2. **Lint obrigatório antes de commit/push.** O CI (`.github/workflows/ci.yml`) roda `ruff check .` e `ruff format --check .` como etapa obrigatória de lint do backend (`line-length = 100` em `pyproject.toml`) e `npm run lint` no frontend. Rodar essas mesmas checagens localmente antes de qualquer commit/push evita reprovação de CI e retrabalho. Se falhar, aplicar `ruff format .` + `ruff check --fix .` (backend) antes de comitar.

3. **Cobertura de testes completa e obrigatória.** Toda funcionalidade implementada ou alterada precisa de testes automatizados cobrindo integralmente seu fluxo de processamento — da entrada (schema/validação) à saída (regra de negócio, persistência, resposta, efeito colateral) — incluindo casos de erro/borda relevantes (tenant errado, tier insuficiente, payload malformado, falha de dependência externa, etc.). Cobertura só do caminho feliz não é considerada completa.

4. **Fluxo de entrega: testes 100% → GitHub → Graphify.** Siga esta ordem, sem pular etapas, para qualquer entrega de funcionalidade:
   1. Escreva/atualize os testes cobrindo o fluxo inteiro da funcionalidade (regra 3 acima). Se faltar teste em qualquer etapa do processamento, complete antes de seguir.
   2. Rode a suíte completa localmente:
      - Backend: `cd backend && ruff check . && ruff format --check . && pytest -q`
      - Frontend (quando houver mudança de frontend): `cd frontend && npm run lint && npm run build && npm run test`
   3. Confirme explicitamente 100% dos testes passando e zero erros de lint. Se algo falhar, corrija e rode tudo de novo do zero — não avance com testes falhando, pendentes ou pulados.
   4. Só então faça commit/push/PR para o GitHub. Nunca subir código com testes falhando, mesmo sob pressão de prazo — avisar e perguntar antes de contornar esta regra.
   5. Só depois do push confirmado, atualize o Graphify (`graphify-out/`, via `/graphify --update` ou equivalente). Se os testes não estavam 100% verdes nas etapas 2-3, não atualizar o Graphify — o grafo de conhecimento não deve refletir um estado de código não validado.
