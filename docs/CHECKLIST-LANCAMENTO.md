# Checklist de lançamento (go-live) — FireAudit

Este arquivo existe porque alguns passos de ir ao ar **não são código** — são configuração
manual em painéis externos (Stripe, DNS, VPS) que só o Eduardo pode fazer, e que não têm
como ser cobertos por CI/testes automatizados. Cada item abaixo diz claramente **quem faz**
e **por quê existe** (referência à decisão original), para não depender de lembrança solta.

Regra de uso: antes de apontar o domínio de produção para a VPS e anunciar o produto,
percorrer esta lista de cima a baixo. Marcar `[x]` conforme for concluindo. Se um item
tiver dependência de outro, a ordem já reflete isso.

---

## 1. Stripe — modo live (produção)

- [ ] **Ativar conta Stripe em modo live** (hoje só existe em modo teste). Dashboard Stripe →
  ativar conta (dados bancários, verificação de identidade/empresa).
- [ ] **Recriar produto/preço em modo live**: `Product "FireAudit Pro"` + `Price` mensal —
  os IDs de teste (`price_...`) **não existem** em modo live, é preciso recriar
  (mesmo script/processo usado na Fase 8, seção 7 do plano de billing, mas com a chave live).
  Copiar o novo `price_...` para `STRIPE_PRICE_ID_PRO` no `.env` de produção.
- [ ] **Trocar `STRIPE_SECRET_KEY`** de `sk_test_...` para `sk_live_...` no `.env` de produção.
  **Nunca commitar essa chave** — só no `.env` do servidor, fora do git (já coberto pelo
  `.gitignore`, mas repetindo aqui porque é o tipo de erro que só precisa acontecer uma vez).
- [ ] **Criar o webhook endpoint real no dashboard Stripe** (modo live), apontando para
  `https://api.fireaudit.io/v1/webhooks/stripe`. Em desenvolvimento isso foi simulado com
  `stripe listen` — produção precisa do endpoint de verdade cadastrado no Stripe.
  Copiar o `whsec_...` gerado para `STRIPE_WEBHOOK_SECRET` no `.env` de produção (é um
  segredo **diferente** do de teste — não reaproveitar o de dev).
- [ ] **Ativar o Customer Portal em modo live**: `https://dashboard.stripe.com/settings/billing/portal`
  (a URL de teste é `/test/settings/...` — são duas configurações independentes, ativar a de
  teste não ativa a de produção). Sem isso, `POST /v1/subscription/billing-portal-session`
  falha em produção mesmo funcionando em dev. Configurar também, nessa tela, quais campos o
  cliente pode editar (cartão, cancelamento) e a política de cancelamento (imediato vs fim do
  ciclo — decisão de produto do Eduardo, não tem padrão certo).
- [ ] **Testar 1 checkout real de ponta a ponta em produção** com o próprio cartão do Eduardo
  (ou reembolsar depois) antes de anunciar publicamente — nunca confiar que "funcionou
  em teste" é garantia de que a configuração live está correta (chaves trocadas, webhook
  configurado, portal ativado são 3 pontos de falha independentes).

## 2. Ambiente / infraestrutura

- [ ] **DNS**: `api.fireaudit.io` e o domínio do frontend apontando para a VPS OCI.
- [ ] **HTTPS/TLS**: certificado válido para os dois domínios (ex: Let's Encrypt via Nginx,
  conforme `docs/specs/fase9-10-performance-infra.md`).
- [ ] **`.env` de produção completo**: todas as vars de `.env.example` preenchidas com valores
  reais (não os placeholders) — usar o próprio `.env.example` como checklist de campos.
- [ ] **CORS**: `FRONTEND_ORIGIN` no `.env` de produção apontando para o domínio real do
  frontend, não `localhost` (`CLAUDE.md` — "CORS restrito ao domínio oficial, sem wildcard").
- [ ] **Backup do Postgres de produção configurado e testado** (`fase12-operacao-manutencao.md`
  seção 2 — rotina de restauração de teste a cada trimestre já é um débito conhecido, mas o
  primeiro backup automático precisa existir *antes* do primeiro cliente real, não depois).

## 3. Monitoramento mínimo antes de anunciar

- [ ] **UptimeRobot (ou equivalente) apontando para `GET /v1/health`** — é o único alerta de
  "backend fora do ar" que existe no plano (`fase12-operacao-manutencao.md` seção 1).
- [ ] **Sentry configurado** (`SENTRY_DSN` no `.env` de produção) — sem isso, exceções em
  produção não geram alerta, só aparecem se alguém for procurar log manualmente.

## 4. Itens que dependem de uma decisão de produto do Eduardo (não são só configuração)

- [ ] **Preço final do plano Pro** — o valor usado até agora (`$19/month`) é o que foi
  configurado no Stripe em modo teste; confirmar se é o preço final antes de recriar em modo
  live (mudar preço depois de ter clientes ativos é mais delicado — clientes existentes
  normalmente mantêm o preço antigo, o que exige atenção extra no Stripe).
- [ ] **Política de cancelamento**: imediato ou até o fim do ciclo pago? Isso é configurado no
  próprio Customer Portal (item 1 acima), mas é uma decisão de negócio, não técnica.
- [ ] **Baseline do `config_drift`** (6ª checagem do motor de análise, adiada desde a Fase 8) —
  decisão pendente de produto: o que conta como "configuração de referência" para detectar
  drift (snapshot anterior mais recente? um snapshot marcado manualmente como baseline?).
  Enquanto isso não for decidido, o produto continua com 5 das 6 checagens do motor de
  análise ativas — não é bloqueador de lançamento, mas é uma lacuna de feature conhecida.

---

**Como manter este arquivo útil:** sempre que uma decisão de configuração de produção for
tomada fora do código (ex: um valor no dashboard Stripe, um registro DNS), registrar aqui —
o objetivo é que ninguém precise reconstruir de memória "o que falta antes de ir ao ar".
