# Fase 2 — Documento de Planejamento (PRD)
## Produto: FireAudit (nome provisório) — Plataforma de Visibilidade, Auditoria e Gestão Remota para pfSense

**Decisão incorporada em 2026-07-08 (mudança de escopo mais importante do documento):** o produto deixou de ser "MVP read-only primeiro, Premium/write depois" — o lançamento (v1) agora entrega **o produto completo**, incluindo edição remota de regras (antigo tier Premium/v5), um **criador de alertas customizados por limiar de métrica** (nova funcionalidade, não existia antes), detecção de **regras duplicadas** (6ª checagem do motor de análise) e **filtros no dashboard**. O faseamento antigo (v1 read-only → v5 write, anos de roadmap) é substituído por um único corte funcional completo, testado e lançado de uma vez. Isso é uma decisão explícita do fundador, ciente do risco de segurança/engenharia envolvido em escrita remota (ver `fase5-seguranca.md`, seção sobre escrita remota) — **não é uma correção minha, é a direção nova**. O modelo de tiers (Free/Pro/Premium) e de conta (Individual/Multiempresa) **continua existindo** como estratégia de monetização — a mudança é que toda a funcionalidade é construída e lançada junto, não que os tiers deixam de existir. Ver seção 12 (Roadmap) e seção 13 (Definição do v1) para o detalhamento completo desta mudança.

**Decisões incorporadas em rodadas anteriores:** agente com auto-update; modelo de planos em 3 camadas por profundidade de acesso (não por quantidade de firewalls); agente open-source, backend proprietário.

**Decisão incorporada em 2026-07-08 — dois modelos de conta:** o produto passa a oferecer, desde o cadastro, dois tipos de conta declarados pelo usuário — **Conta Individual** (1 empresa, tiers Free/Pro/Premium por profundidade de acesso, como já desenhado) e **Conta Multiempresa** (para consultores/MSPs que administram várias empresas, cada uma com seus próprios firewalls nomeados, sempre em profundidade total, cobrado por empresa). Ver detalhamento completo na seção 6.1. Isso formaliza e antecipa para o desenho de produto algo que antes estava mapeado só como "multi-tenant, fora do MVP" — a distinção importante é que **isto não é o RBAC multiusuário da v3** (Fase 1, item 2.4): é um usuário só administrando várias empresas, não várias pessoas dentro da mesma empresa. As duas features são independentes e podem evoluir em momentos diferentes.

---

## 1. Objetivo do sistema

Dar a qualquer administrador de pfSense — de um gestor de TI solo até um MSP com múltiplos clientes — visibilidade centralizada, auditoria de segurança contínua e, no tier mais avançado, capacidade de gerenciar remotamente as configurações do firewall através de uma interface visual, sem depender de acesso VPN/local a cada dispositivo individualmente.

## 2. Visão de produto

Ser o "painel de controle" que o ecossistema pfSense nunca teve nativamente: hoje cada instalação é uma ilha, gerenciada isoladamente via GUI local. FireAudit conecta essas ilhas por um agente leve e seguro, e oferece uma camada de inteligência (compliance, CVE, drift) e, progressivamente, uma camada de controle (visualização e edição remota de regras) — se tornando indispensável tanto para quem tem 1 firewall quanto para quem tem 200.

## 3. Personas

**Persona 1 — "Marcos", Analista/Gestor de TI solo (persona primária do MVP).**
Administra a infraestrutura de uma empresa de porte pequeno/médio, incluindo 1-3 pfSense. Não tem tempo de entrar em cada firewall regularmente para checar saúde/segurança. Já usa Grafana/Zabbix para outras coisas, mas achou complexo replicar isso especificamente para o firewall. Valoriza tempo economizado e redução de risco de ser pego de surpresa.

**Persona 2 — "Priya", Consultora de TI/MSP (persona de expansão, fase 2/3).**
Administra pfSense/OPNsense de 5 a 50 clientes diferentes. Precisa provar valor para os clientes (relatórios) e reduzir o tempo que gasta em tarefas repetitivas de auditoria manual. Já paga por ferramentas de RMM genéricas, mas nenhuma tem profundidade em pfSense.

**Persona 3 — "Alex", Homelab enthusiast / early adopter técnico.**
Não é o comprador principal (baixa propensão a pagar), mas é um canal de validação e advocacy importante — participa de comunidades, testa produtos novos, e se convencido, recomenda para o público profissional (Persona 1 e 2). Importante para o agente open-source e para tração inicial de conteúdo.

## 4. Público-alvo

Administradores e gestores de TI, consultores/MSPs e entusiastas técnicos que operam pfSense, majoritariamente fora do Brasil (mercado primário: EUA, Europa, Oceania — onde a cultura de pagar por SaaS técnico em USD é mais madura), descobrindo o produto via comunidades técnicas e conteúdo (não via prospecção ativa).

## 5. Dores resolvidas

- Falta de visibilidade consolidada quando existe mais de um firewall.
- Auditoria de segurança manual, esporádica ou inexistente (regras arriscadas, protocolos deprecated, certificados vencendo passam despercebidos).
- Ausência de alerta proativo — descoberta do problema é reativa (só quando já causou impacto).
- Necessidade de VPN/acesso local só para consultar configuração — friccional mesmo para tarefas simples de leitura.
- (Tier avançado) necessidade de entrar na GUI nativa, tela por tela, para fazer alterações simples de regra — lento e propenso a erro humano quando repetido em múltiplos firewalls.

## 6. Funcionalidades por tier (atualizado em 2026-07-08 — todas as funcionalidades abaixo fazem parte do v1/lançamento, ver nota de escopo no topo do documento)

### Tier Free — "Monitor"
Visão de infraestrutura básica: CPU, RAM, armazenamento, uptime, temperatura, status de interfaces (up/down), versão instalada. Sem acesso a regras de firewall, VPN ou dados de configuração sensíveis. Health-check do agente (última vez visto). Alertas por email apenas para "agente offline" e para regras de alerta customizadas (seção 6.2) sobre as métricas básicas já disponíveis neste tier (CPU/RAM/armazenamento/temperatura).

**Racional:** ainda entrega valor real (monitoramento básico já resolve uma dor), mas deliberadamente não expõe a informação mais sensível (regras, VPN) — isso é reservado para planos pagos, e reduz a superfície de dados sensíveis armazenados para usuários não-pagantes (bom também do ponto de vista de segurança/custo).

### Tier Pro — "Auditor" (paga, self-service, cartão)
Tudo do Free, mais: leitura completa de regras de firewall e aliases, túneis VPN (IPsec/OpenVPN/WireGuard) e usuários conectados, os 6 tipos de achados (regra arriscada, certificado expirando, CVE de versão, drift de configuração, agente offline prolongado, **regra duplicada** — nova, ver seção 6.3), relatório exportável em PDF, retenção de histórico de 90 dias, alertas via email + webhook (Slack/Discord/Telegram/genérico), **criador de alertas customizados** (seção 6.2) com qualquer métrica/achado disponível neste tier, filtros de dashboard (seção 6.4).

### Tier Premium — "Controller" (paga, ticket mais alto, com fricção de ativação proposital)
Tudo do Pro, mais: interface visual para criar, editar e excluir regras de firewall remotamente, com fluxo de confirmação explícita, simulação/preview de impacto antes de aplicar, log de auditoria detalhado de toda alteração (quem, quando, o quê, de onde), e rollback de uma alteração recente. **Este tier faz parte do v1/lançamento** (decisão de 2026-07-08, ver nota de escopo no topo do documento) — é tratado como o componente de maior risco de engenharia/segurança do produto e recebe atenção proporcional nas Fases 3/4/5/8/11 (arquitetura, banco, segurança, API, testes), mas não é mais adiado para uma fase posterior de roadmap.

### 6.2 Criador de alertas customizados (nova funcionalidade, 2026-07-08)
Além dos 6 achados automáticos do motor de análise (seção 6.3), o usuário pode criar suas próprias regras de alerta baseadas em limiar de métrica — ex: "se uso de RAM do firewall X passar de 50%, por mais de 10 minutos consecutivos, notificar o canal Y". Isso é uma funcionalidade nova, distinta e complementar aos achados automáticos: achados automáticos são *conhecimento embutido do produto* (o que é "arriscado" já vem definido); alertas customizados são *regras que o próprio usuário define* sobre qualquer métrica que seu tier já tem acesso (CPU, RAM, armazenamento, temperatura no Free; adicionalmente contagem de achados por severidade, status de VPN, uso de interface no Pro+). Ver `fase4-banco-de-dados.md` (nova tabela `alert_rules`) e `fase8-design-api.md` (CRUD `/v1/alert-rules`) para o desenho técnico completo.

**Regra de negócio:** um usuário só pode criar regra de alerta sobre métrica/dado que seu tier atual já expõe — não é uma forma de contornar a trava de profundidade de acesso por tier (ex: conta Free não pode criar alerta sobre "regra arriscada apareceu", porque esse dado nem é retido para contas Free).

### 6.3 Motor de análise — 6 tipos de achado (atualizado, 2026-07-08)
Aos 5 achados já especificados (regra arriscada, certificado expirando, CVE de versão, drift de configuração, agente offline), soma-se: **regra duplicada** (`duplicate_rule`) — duas ou mais regras de firewall na mesma interface com a mesma tupla efetiva de origem/destino/porta/protocolo/ação, tornando uma delas redundante (impacto: nenhum, mas indica falta de higiene de configuração e é fácil de detectar e corrigir). Ver `fase3-arquitetura.md` para a implementação como 6ª estratégia do `AnalysisCheck`.

### 6.4 Filtros no dashboard (nova funcionalidade, 2026-07-08)
Dashboard (Individual e Multiempresa) recebe filtros combináveis: por severidade de achado (crítico/alto/médio/baixo), por status do firewall (online/offline/pendente), e — na Conta Multiempresa — por empresa-cliente. Isso passa a ser necessário porque o produto completo (não mais só read-only single-firewall) espera volumes maiores de firewalls e achados por conta desde o lançamento. Ver `fase6-7-ux-ui.md` seção 3.3 (atualizada) para o desenho de UI.

### Fora do escopo do v1, mas mapeado
O RBAC multiusuário da v3 (múltiplas pessoas dentro da mesma empresa, com papéis/permissões diferentes — ver Fase 1, item 2.4, e roadmap seção 12) continua fora do v1. **Isto é diferente da Conta Multiempresa** (seção 6.1): Multiempresa é um usuário só administrando várias empresas; RBAC é várias pessoas administrando a mesma empresa. Suporte a OPNsense também continua fora do v1 (permanece v4 no roadmap, seção 12) — é uma dimensão de escopo diferente (outra plataforma de firewall), não relacionada à profundidade de funcionalidade que mudou nesta rodada.

### 6.1 Dois modelos de conta — Individual vs. Multiempresa

**Decisão de 2026-07-08:** desde o cadastro, o produto pede ao usuário que declare que tipo de conta quer abrir. Essa escolha define a estrutura de dados, o fluxo de onboarding e a cobrança — não é um upgrade posterior dentro do mesmo tipo de conta, é um tipo de conta diferente desde o início (ver Fase 4 para o impacto no schema).

**Conta Individual** — pensada para o "Marcos" (persona 1): um coordenador/analista de TI CLT, empregado de uma única empresa, que administra o(s) firewall(s) *dessa* empresa. No cadastro, informa os dados da própria empresa. A conta fica **estruturalmente travada a exatamente 1 empresa** (não é um limite de quantidade de firewall — quantidade de firewall continua ilimitada dentro dessa 1 empresa, mantendo a decisão já tomada na seção 6 de não usar contagem de firewall como gatilho de upgrade). Dentro da Conta Individual, os 3 tiers por profundidade continuam existindo como já desenhado: Free, Pro, Premium.

**Conta Multiempresa** — pensada para a "Priya" (persona 2): consultor/MSP que atende várias empresas-cliente, cada uma com seu próprio conjunto de firewalls nomeados. No cadastro, em vez de dados de uma empresa própria, informa o identificador fiscal da própria empresa de consultoria (CNPJ no Brasil, EIN/VAT/equivalente em outros países — ver nota de internacionalização abaixo) para confirmação de que se trata de uma pessoa jurídica prestando serviço a terceiros. A primeira empresa cadastrada já vem em profundidade total (equivalente ao tier Pro); cada empresa adicional é cobrada por empresa, também sempre em profundidade total — **não existe um tier "Free" dentro do modelo Multiempresa**, porque cobrar por profundidade não faz sentido quando o cliente final (a empresa gerenciada) já está pagando um consultor para ter visibilidade completa.

**Por que a trava é estrutural (1 empresa por conta Individual) e não um limite de contagem de firewall:** um limite artificial de firewalls (ex: "máximo 2 por conta Individual") entraria em conflito direto com a decisão já registrada na seção 6 de que o gatilho de upgrade é profundidade de acesso, não quantidade — um cliente legítimo com 5 firewalls na mesma empresa não deveria ser empurrado para o plano errado. A trava de 1 empresa resolve o problema de abuso (um MSP comprando uma única conta Individual-Pro para atender vários clientes diferentes) sem penalizar o cliente legítimo com muitos firewalls dentro de uma única empresa.

**UX/UI decorrente (a integrar na Fase 6-7 quando revisitada):** a Conta Multiempresa precisa de uma camada de navegação acima do dashboard por firewall já desenhado — seletor de empresa, cada empresa com seu próprio nome e conjunto de firewalls nomeáveis pelo usuário, visualmente separados (cards ou árvore empresa → firewalls), coerente com o pedido original de "bem gráfico e dividido, separado por nome de empresa e firewall".

**Nota de internacionalização:** como o público-alvo é majoritariamente fora do Brasil (seção 4), o campo de confirmação da Conta Multiempresa deve ser genérico ("identificador fiscal da empresa") e aceitar formatos variáveis (CNPJ, EIN, VAT number, etc.), não assumir CNPJ como formato único.

**Tabela de preços (ilustrativa — valores placeholder para orientar a estrutura, não são os valores finais):**

| Conta | Tier/faixa | Preço ilustrativo |
|---|---|---|
| Individual | Free | $0/mês |
| Individual | Pro | ~$19/mês |
| Individual | Premium | ~$39/mês |
| Multiempresa | 1ª empresa (profundidade total) | ~$19/mês |
| Multiempresa | Empresa adicional (2ª–5ª) | ~$15/empresa/mês |
| Multiempresa | Empresa adicional (6ª–15ª) | ~$12/empresa/mês |
| Multiempresa | Empresa adicional (16ª+) | ~$10/empresa/mês |

**Princípio de precificação que guia essa tabela:** o preço da 1ª empresa no Multiempresa é igual ao do Individual-Pro (não existe penalidade por se categorizar corretamente como consultor desde a 1ª empresa) e cada empresa adicional custa sempre menos do que abrir uma conta Individual separada para ela — isso remove qualquer incentivo racional para contornar a trava estrutural abrindo múltiplas contas Individual em vez de uma Multiempresa.

**Migração entre modelos:** um usuário Individual que começa a atender uma segunda empresa precisa migrar para Multiempresa (a conta não comporta uma 2ª empresa por desenho) — o fluxo de migração exato (self-service vs. suporte manual) fica como item de backlog, não bloqueante para o MVP.

## 7. Casos de uso principais

1. Marcos cadastra sua conta, adiciona o primeiro firewall, segue o guia de onboarding, instala o agente, e em minutos vê o snapshot inicial de saúde básica (Free).
2. Marcos faz upgrade para Pro após ver um teaser de "3 achados críticos disponíveis no plano Pro" na tela, paga com cartão, e imediatamente desbloqueia a visão completa de regras e os achados de segurança.
3. O agente de um firewall de Marcos para de reportar por 6 horas; o sistema gera um achado de severidade alta ("agente offline") e dispara alerta por email e webhook configurado.
4. Priya (MSP) cadastra uma **Conta Multiempresa** informando o identificador fiscal da sua consultoria, adiciona a 1ª empresa-cliente já em profundidade total, depois adiciona mais 11 empresas-clientes (cada uma com seus próprios firewalls nomeados), sendo cobrada por empresa adicional conforme seção 6.1, e gera relatórios mensais separados por empresa. (O convite de equipe/RBAC multiusuário dentro da mesma empresa continua fora do v1, ver v2 no roadmap seção 12.)
5. (Tier Premium, já no v1) Marcos identifica uma regra insegura no dashboard, clica em "corrigir", vê uma prévia da mudança, confirma, e a alteração é aplicada remotamente com log de auditoria completo.
6. (Nova, 2026-07-08) Marcos cria uma regra de alerta customizada: "se uso de RAM do firewall X passar de 50% por mais de 10 minutos, notificar por email e Slack" — sem precisar esperar o produto ter esse limiar como achado nativo.
7. (Nova, 2026-07-08) Priya, com 12 empresas-clientes na Conta Multiempresa, usa os filtros do dashboard para ver só os firewalls com achado crítico aberto, cruzando com uma empresa-cliente específica, sem precisar rolar a lista completa.
8. (Nova, 2026-07-08) O motor de análise identifica 2 regras redundantes na mesma interface WAN de um firewall (achado `duplicate_rule`) — Marcos remove a duplicata direto pela interface de edição remota do tier Premium, com preview mostrando que nenhum tráfego legítimo depende da regra removida.

## 8. Regras de negócio

- Um usuário pertence a uma conta (não direto a uma organização — ver hierarquia `Account → Organization` em `fase4-banco-de-dados.md`).
- Um firewall pertence a exatamente uma organização.
- O tier de acesso é definido por organização, não por firewall individual (não é possível ter 1 firewall no Pro e outro no Free na mesma conta).
- **Conta Individual está estruturalmente limitada a exatamente 1 organização** — não há fluxo de UI ou dado que permita adicionar uma 2ª empresa a uma Conta Individual; quem precisa de mais de 1 empresa deve usar Conta Multiempresa (ver seção 6.1 e Fase 4).
- **Conta Multiempresa não possui tier Free** — toda organização sob uma Conta Multiempresa opera sempre em profundidade total (equivalente Pro), cobrada por organização conforme a tabela de preços da seção 6.1.
- **O tipo de conta (Individual ou Multiempresa) é declarado no cadastro e não é alternável livremente** — migrar de Individual para Multiempresa (ao passar a atender uma 2ª empresa) é um fluxo de migração de conta, não uma mudança de tier.
- Ações do tier Premium exigem confirmação explícita de duas etapas (visualizar prévia → confirmar) e nunca são aplicadas de forma totalmente automática/silenciosa. Isso vale desde o v1 (não é mais uma ressalva "quando o tier existir").
- Dados de configuração sensíveis (regras, VPN) só são retidos/exibidos para organizações em tier Pro ou Premium — organizações em Free não têm esses dados armazenados além do necessário para o próprio dashboard básico (minimização de dados).
- A API key do pfSense de um cliente nunca é exposta na interface após o cadastro inicial (write-only do ponto de vista de exibição) — e nunca é armazenada no backend em nenhuma hipótese, nem mesmo para viabilizar a edição remota do Premium (ver seção 6, Premium, e `fase5-seguranca.md`): a escrita remota é executada pelo agente local usando a API key que só ele possui, a partir de um comando que o agente busca do backend via polling (RF12) — o backend nunca toca a API key do cliente para nenhuma operação, leitura ou escrita.
- **(Nova, 2026-07-08) Criação de regra de alerta customizada (seção 6.2) só é permitida sobre métrica/dado que o tier atual da organização já expõe** — não é uma forma de contornar a trava de profundidade de acesso por tier.
- **(Nova, 2026-07-08) Achado `duplicate_rule` (seção 6.3) nunca é corrigido automaticamente** — segue a mesma regra de qualquer ação de escrita remota (edição manual do usuário no tier Premium, com preview e confirmação).

## 9. Requisitos funcionais (resumo — detalhamento por tela na Fase 6/7; todos fazem parte do v1)

- RF01: Cadastro/login de usuário e organização.
- RF02: Fluxo de onboarding com geração de script de agente personalizado por firewall.
- RF03: Ingestão de dados via endpoint de API autenticado por token.
- RF04: Motor de análise que gera "achados" a partir de cada snapshot recebido (6 tipos, seção 6.3).
- RF05: Dashboard com listagem de firewalls e status agregado, com filtros combináveis (seção 6.4).
- RF06: Tela de detalhe por firewall com achados categorizados por severidade.
- RF07: Sistema de billing com os 3 tiers e upgrade/downgrade self-service.
- RF08: Sistema de alertas configurável (email, webhook), incluindo criador de regras de alerta customizadas por limiar de métrica (seção 6.2).
- RF09: Exportação de relatório em PDF (Pro+).
- RF10: Interface de edição remota de regras com preview, confirmação em duas etapas e rollback (tier Premium — faz parte do v1, não é mais fase futura).
- RF11: Auto-update do agente antes de cada execução.
- RF12: (Novo, 2026-07-08) Agente passa a fazer polling de comandos remotos pendentes (não só push de snapshot), para viabilizar RF10 — ver `fase3-arquitetura.md` e `fase8-design-api.md`.

## 10. Requisitos não-funcionais

- RNF01 — Segurança: API keys de clientes criptografadas em repouso (AES-256, chave gerenciada via KMS); toda comunicação agente↔backend via TLS 1.2+; ver Fase 5 para detalhamento completo.
- RNF02 — Disponibilidade: backend com meta inicial de 99.5% (razoável para MVP com orçamento restrito; revisar para 99.9% quando a base crescer).
- RNF03 — Internacionalização: timestamps em UTC internamente, exibidos no timezone do navegador do usuário; strings de interface preparadas para i18n desde o início mesmo com um único idioma (inglês) no lançamento.
- RNF04 — Performance: tempo de resposta do dashboard < 2s para contas com até 20 firewalls (P95).
- RNF05 — Auditabilidade: toda ação de escrita remota (tier Premium, já no v1) gera log imutável.
- RNF06 — Portabilidade do agente: compatível com as 3 últimas versões estáveis do pfSense CE.
- RNF07 — Custo operacional: infraestrutura do MVP deve operar dentro de ~USD 20/mês (orçamento do fundador, ~R$100), o que direciona fortemente as escolhas de hospedagem na Fase 10.

## 11. Restrições

- Orçamento de infraestrutura inicial limitado (~USD 20/mês).
- Equipe de 1 pessoa, 10-20h/semana, fora do horário comercial (7h-18h ocupado).
- Sem orçamento de marketing pago — aquisição depende de conteúdo/comunidade.
- Suporte ao cliente é assíncrono/best-effort no início (sem SLA formal, chamadas de vídeo pontuais fora do expediente).

## 12. Roadmap do produto (reescrito em 2026-07-08 — mudança de escopo mais importante do documento)

**Decisão do fundador (2026-07-08):** o faseamento antigo (v1 read-only limitado → v5 edição remota, ao longo de anos) foi substituído por um único lançamento completo. O "v1" abaixo é o produto completo, não um recorte read-only. Justificativa e riscos assumidos: edição remota é o componente de maior risco de segurança do produto (ver `fase5-seguranca.md`), e ao entrar desde o lançamento, exige que a Fase 5 (segurança) e Fase 11 (testes) tratem esse componente com o mesmo rigor que teriam se ele fosse lançado "com calma" depois de anos de maturação do resto do produto — isso é um risco de cronograma e de qualidade que o fundador optou por assumir conscientemente, e não algo que deva ser suavizado ou reintroduzido como faseamento posterior sem confirmação explícita dele.

- **v0 — Validação (atual):** wireframes prontos, validação de dor em comunidades ainda pendente.
- **v1 — Lançamento completo:** cadastro (Individual + Multiempresa, seção 6.1, com experiência completa de seletor de empresa desde o início — não mais adiada para "v2"), onboarding, agente com auto-update e polling de comandos remotos (RF12), 6 tipos de achado (seção 6.3, incluindo `duplicate_rule`), dashboard com filtros (seção 6.4), billing Free/Pro/Premium via Stripe, alertas email+webhook **e criador de alertas customizados** (seção 6.2), relatório PDF, **edição remota de regras com preview/confirmação/rollback** (tier Premium, antigo RF10/v5). Multi-firewall por organização já no v1 (não é mais uma evolução de v2).
- **v2 — RBAC multiusuário:** múltiplos usuários dentro da **mesma** organização, papéis/permissões (antigo "v3"). **Distinto da Conta Multiempresa** (que já existe desde v1 e é sobre 1 usuário administrando várias organizações) — isto é sobre várias pessoas administrando a mesma organização. Permanece fora do v1 porque é uma dimensão de complexidade independente (multiusuário dentro da mesma empresa), não uma funcionalidade de auditoria/controle do firewall em si.
- **v3 — Suporte a OPNsense** (antigo "v4"). Permanece fora do v1 porque é uma dimensão de escopo diferente (outra plataforma de firewall inteira, com API/formato de regra próprios), não uma funcionalidade adicional sobre pfSense.

## 13. Definição do v1 — produto completo (reescrito em 2026-07-08)

Escopo do v1 (lançamento): conta Individual (1 organização) ou Multiempresa (N organizações, seção 6.1) com múltiplos usuários por conta (mas 1 organização visível por vez por conta Individual — RBAC multiusuário dentro da mesma organização é v2, ver seção 12) e N firewalls por organização (sem limite artificial — gatilho de upgrade é profundidade de acesso, não quantidade). Tiers Free/Pro/Premium operacionais com cobrança via Stripe desde o lançamento, incluindo o fluxo completo de edição remota do Premium (preview, confirmação em duas etapas, log de auditoria, rollback). Agente open-source com auto-update e polling de comandos remotos. 6 tipos de achado automático (seção 6.3). Criador de alertas customizados por limiar de métrica (seção 6.2), alertas email + webhook genérico. Filtros de dashboard (seção 6.4). Relatório PDF no Pro+.

**O que continua fora, mesmo do v1 completo (ver seção 12):** RBAC multiusuário dentro da mesma organização (v2) e suporte a OPNsense (v3). Estes dois continuam fora porque resolvem problemas estruturalmente diferentes do que foi ampliado nesta rodada (colaboração multiusuário e suporte a outra plataforma, respectivamente) — não são "mais uma funcionalidade de auditoria/controle", são dimensões novas de produto.

## 14. Backlog priorizado (top do backlog, não exaustivo — atualizado em 2026-07-08)

1. Definir schema de banco com `organizations`/`accounts` desde o início (Fase 4).
2. Especificar contrato do endpoint de ingestão e do payload do agente (Fase 8).
3. Especificar mecanismo de auto-update do agente (script verifica versão, baixa nova versão de URL fixa, compara hash antes de substituir).
4. Especificar as 6 checagens do motor de análise em detalhe (regras de detecção, incluindo `duplicate_rule`).
5. Especificar fluxo de billing/upgrade Free→Pro→Premium (Stripe Checkout + webhook de confirmação).
6. Especificar processo de curadoria/atualização da base de CVE (ver risco 2.3 da Fase 1).
7. Onboarding: guia + vídeo + geração de script personalizado.
8. Dashboard e tela de detalhe, incluindo filtros (seção 6.4) — especificação de estados: loading, vazio, erro.
9. Especificação de segurança do tier Premium — **agora prioridade do v1, não mais adiada** (ver `fase5-seguranca.md`, seção dedicada a escrita remota).
10. (Novo) Especificar schema e API do criador de alertas customizados (seção 6.2).
11. (Novo) Especificar protocolo de polling de comandos remotos entre agente e backend (RF12).

---

## Observação sobre o novo prompt-mestre recebido

O prompt que você trouxe pede um nível de profundidade equivalente ao de uma equipe de engenharia completa (arquitetura, banco, segurança, UX, API, performance, infra, qualidade) antes de qualquer código. Vou seguir essa estrutura fase por fase, como as tasks já organizadas mostram. Uma nota de calibração honesta: para um produto no estágio de "validação de mercado ainda pendente, fundador solo, 10-20h/semana", uma parte desse rigor (ex: CQRS, event-driven, microsserviços) provavelmente será **avaliada e descartada por overengineering** nas fases seguintes — vou justificar cada decisão de arquitetura com esse contexto em mente, não aplicar padrões de Big Tech por padrão só porque o prompt os menciona. Isso é consistente com a própria filosofia que o prompt pede ("evite overengineering quando ele não gerar benefícios reais").