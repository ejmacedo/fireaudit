# Fase 9-10 — Performance e Infraestrutura
## Produto: FireAudit — v1 (MVP)

Restrição que domina toda decisão desta fase: orçamento de ~USD 20/mês (Fase 2, RNF07) e uma pessoa operando 10-20h/semana. Toda escolha aqui prioriza previsibilidade de custo e baixo esforço operacional sobre performance máxima teórica — o produto ainda não tem validação de mercado confirmada, então a infraestrutura certa é a mais barata que atende o RNF04 (dashboard <2s, até 20 firewalls), não a mais escalável.

---

## 1. Performance — onde otimizar e onde deliberadamente não otimizar

### 1.1 Caching
- **O que cachear:** resposta de `GET /v1/firewalls` (lista do dashboard) e contadores agregados de achados por severidade — são consultados a cada carregamento de tela e mudam com baixa frequência relativa (só mudam quando um novo snapshot é processado, não a cada request).
- **Onde:** cache em memória do próprio processo (ex: `cachetools` no FastAPI) no MVP, com TTL curto (30-60s) e invalidação ativa no momento em que um snapshot termina de ser processado (o worker, ao salvar achados, também invalida a entrada de cache daquele firewall) — evita a complexidade operacional de introduzir Redis só para cache neste estágio, quando o problema (poucos usuários simultâneos, Fase 2 seção 11) ainda não o justifica.
- **Reconsiderar quando:** se o backend rodar em mais de uma instância (necessário para HA/escala horizontal), cache em memória de processo para de funcionar corretamente (cada instância teria seu próprio cache desincronizado) — nesse momento, migrar para Redis compartilhado é o próximo passo natural, e é o mesmo gatilho já documentado para a fila (Fase 3) e rate limiting (Fase 5): as três migrações provavelmente acontecem juntas, na mesma leva de mudança de infraestrutura.

### 1.2 Otimização de queries
- Os índices definidos na Fase 4 (seção 4) já cobrem os padrões de acesso mais frequentes (listagem por organização, achados por firewall+status+severidade) — não há necessidade de otimização adicional de query no volume esperado do MVP.
- Consulta de contagem de achados críticos abertos por firewall (usada no card de resumo do dashboard) é candidata a N+1 query se implementada ingenuamente (uma query por firewall) — especificar explicitamente que a camada de aplicação deve fazer essa contagem em uma única query agregada (`GROUP BY firewall_id`), não em loop.

### 1.3 O que não vamos otimizar agora (documentado de propósito)
- Sem CDN para assets do frontend no MVP — Next.js/Vercel-style ou mesmo servido direto pelo Docker Compose já é suficientemente rápido para o volume de usuários esperado; adicionar CDN é otimização sem problema correspondente ainda.
- Sem read replica de banco — um único Postgres atende toda leitura e escrita no volume do MVP; réplica de leitura é a resposta certa quando leitura do dashboard competir por recursos com a ingestão de snapshots, não antes.
- Sem otimização de payload (compressão customizada, protocolo binário) na comunicação agente↔backend — JSON sobre HTTPS com gzip padrão do FastAPI já é suficiente para o volume por firewall (um payload não é grande, Fase 8 seção 7 já nota isso como ponto de atenção futura, não atual).

## 2. Infraestrutura — hospedagem e deploy

### 2.1 Topologia
```
VPS única (OCI, tier gratuito ou o mais barato pago)
├── Docker Compose orquestra:
│   ├── container: api (FastAPI)
│   ├── container: worker (mesmo código-base, processo separado — Fase 3)
│   ├── container: postgres
│   └── container: frontend (Next.js)
├── Nginx (reverse proxy + TLS via Let's Encrypt/Certbot)
└── Backup agendado (cron do próprio host) → OCI Object Storage
```

**Por que uma VPS única com Docker Compose, não Kubernetes (reforçando a decisão já justificada na Fase 3, seção 9):** K8s exige um cluster (múltiplos nós ou complexidade de single-node), um control plane para operar, e conhecimento operacional que consome tempo desproporcional para uma pessoa em 10-20h/semana — sem nenhum benefício correspondente no volume atual (não há necessidade de auto-scaling, self-healing complexo, ou orquestração multi-nó para dezenas/centenas de firewalls). Docker Compose num único VPS entrega isolamento de processo, facilidade de deploy e portabilidade suficientes por uma fração do custo operacional.

### 2.2 CI/CD
- Pipeline simples (GitHub Actions, tier gratuito cobre o volume de um projeto solo): em push para `main`, roda testes (Fase 11) → build de imagens Docker → push para registry (ex: GitHub Container Registry, gratuito) → deploy via SSH que faz `docker compose pull && docker compose up -d` na VPS.
- **Por que não um pipeline de deploy mais sofisticado (blue-green, canary):** essas estratégias existem para minimizar downtime em produtos com tráfego contínuo alto e múltiplas instâncias — no MVP, um `docker compose up -d` com poucos segundos de indisponibilidade durante o restart do container `api` é um custo aceitável, não um problema real a ser resolvido com infraestrutura cara. Zero-downtime deploy é o próximo passo natural quando o volume de usuários simultâneos tornar essa janela de segundos perceptível/problemática.

### 2.3 Observabilidade
- **Logs:** stdout dos containers, agregados via `docker compose logs` ou redirecionados para arquivo com rotação (`logrotate`) — sem stack de logging centralizado (ELK, Loki) no MVP, seria overengineering de infraestrutura de observabilidade para o volume de um único host.
- **Métricas de infraestrutura:** já resolvido pelo próprio projeto anterior do usuário (stack TIG/Grafana já em uso para monitorar a OCI, conforme memória `project_oracle_monitoring` e `project_pfsense_monitoring`) — reaproveitar a stack existente para monitorar a VPS do FireAudit em vez de introduzir uma ferramenta nova é a escolha mais coerente com o que o usuário já opera e conhece.
- **Erros de aplicação:** integrar um serviço de error tracking (ex: Sentry, tier gratuito cobre volume baixo) no backend e frontend — isso é a peça que falta na stack TIG (que monitora infraestrutura, não exceções de código da aplicação) e é desproporcionalmente valiosa para uma pessoa só: alerta automático de erro em produção substitui a necessidade de "ficar olhando logs manualmente".
- **Health check:** endpoint simples `GET /v1/health` (verifica conexão com banco) consumido por um monitor externo simples (ex: UptimeRobot, gratuito) — para saber se o backend caiu antes que um cliente reporte.

### 2.4 Ambientes
- Produção e um ambiente de desenvolvimento local (Docker Compose local, mesmo arquivo com overrides) — **sem ambiente de staging dedicado no MVP** (custaria outra VPS, contra o orçamento de USD 20/mês); testes automatizados (Fase 11) e teste manual local cobrem a lacuna que staging cobriria em uma equipe maior. Reconsiderar quando houver orçamento e/ou clientes pagantes suficientes para justificar o custo de validar mudanças antes de produção real.

## 3. Estimativa de custo mensal (documentado para não perder o controle do orçamento)

| Item | Custo estimado |
|---|---|
| VPS OCI (Always Free tier ou instância pequena paga) | USD 0-10 |
| Domínio | ~USD 1/mês (anualizado) |
| OCI Object Storage (backups) | ~USD 1-2 |
| Sentry (tier gratuito) | USD 0 |
| GitHub Actions (tier gratuito) | USD 0 |
| Let's Encrypt (certificados) | USD 0 |
| **Total** | **~USD 2-13/mês**, dentro do orçamento de USD 20/mês com margem |

A margem restante do orçamento é reservada de propósito para o primeiro gasto real quando a base de usuários crescer (ex: upgrade de instância OCI, ou introdução de Redis) — não alocada a nada agora.

## 4. Onde esta infraestrutura vai doer no futuro (documentado de propósito)

- Uma única VPS é um ponto único de falha — aceitável para o estágio atual (Fase 2, RNF02 já aceita 99.5% como meta inicial), mas será o primeiro ponto de dor real de disponibilidade quando houver clientes pagantes com expectativa maior de uptime.
- Ausência de staging significa que todo bug de deploy é descoberto em produção — mitigado por testes automatizados (Fase 11) e pela baixa frequência de deploy de uma equipe solo, mas é uma dívida técnica consciente, não esquecida.
- Cache em memória de processo e rate limiting em memória de processo (Fase 5) compartilham o mesmo gatilho de migração para Redis — quando esse momento chegar, vale fazer as duas migrações juntas em vez de resolver uma e deixar a outra pra depois, já que a infraestrutura nova (Redis) serve as duas necessidades ao mesmo tempo.
- Logs em arquivo local sem agregação centralizada vai ficar inviável de debugar no momento em que houver mais de uma instância de `api` rodando — nesse ponto, um Loki simples (leve, mais barato que ELK) é a evolução natural, coerente com a filosofia de escolher a ferramenta mais simples que resolve o problema real, não a mais robusta em teoria.
