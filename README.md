# FireAudit

SaaS de auditoria e compliance contínua para firewalls pfSense. Ver `CLAUDE.md` para a
arquitetura e as decisões de produto/negócio fechadas — este arquivo cobre apenas o
básico de rodar o projeto localmente.

## Rodando localmente

```bash
cp .env.example .env   # preencher com valores reais (nunca commitar .env)
docker compose up -d
```

- Backend: `http://localhost:8000` (`GET /v1/health` para smoke test)
- Frontend: `http://localhost:3000` (redireciona para `/login` ou `/dashboard`)

## Atenção: mudar o `.env` exige recriar os containers

O `docker compose up` normal (sem flags) **não recarrega variáveis de `.env` em containers
já existentes** — o container continua rodando com as variáveis que tinha no momento em que
foi criado, mesmo depois de editar o `.env` e rodar `docker compose up` de novo. Isso já
causou confusão real durante o desenvolvimento (Fase 8, billing/Stripe): trocar uma chave no
`.env` e reiniciar não bastou, a chave antiga continuava em uso.

**Sempre que editar o `.env`**, recriar os containers afetados em vez de apenas reiniciar:

```bash
docker compose up -d --force-recreate
# ou, para recriar só um serviço específico (mais rápido):
docker compose up -d --force-recreate api worker
```

Se depois disso o comportamento ainda parecer "antigo" (ex: chave errada, `403` inesperado
onde não devia), confirmar que a variável realmente está dentro do container antes de suspeitar
de outra coisa:

```bash
docker compose exec api env | grep STRIPE
```

## Testes e lint (rodar antes de qualquer commit/push)

```bash
# Backend
cd backend && ruff check . && ruff format --check . && pytest -q

# Frontend
cd frontend && npm run lint && npm run build
```

O CI do GitHub Actions roda os mesmos comandos — rodar local primeiro evita um round de CI
falho por lint (já aconteceu antes neste projeto).
