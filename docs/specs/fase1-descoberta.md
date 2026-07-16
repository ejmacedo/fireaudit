# Fase 1 — Descoberta e Crítica do Escopo
## Produto: FireAudit (nome provisório) — Compliance e Auditoria Contínua para pfSense

Antes de aceitar o escopo definido nas conversas anteriores, esta fase existe para pressionar a ideia: onde ela quebra, o que está faltando, e o que deveria mudar antes de qualquer linha de planejamento detalhado ser escrita como definitiva.

**Nota de 2026-07-08 — este documento é um artefato histórico, mantido sem reescrita retroativa:** o escopo do v1 mudou depois desta fase — deixou de ser "somente leitura no MVP" e passou a incluir escrita remota de configuração desde o lançamento (ver `fase2-prd.md` nota de escopo, e `fase3/5/8/11-...md` para o desenho completo). Este documento não foi reescrito porque seu valor é justamente ter sido a primeira crítica ao escopo original — inclusive, a seção 2.1 abaixo **já havia previsto** boa parte do risco de segurança que a escrita remota agora precisa mitigar (backend como alvo de alto valor), então a crítica permanece válida e é a origem direta do desenho de segurança em camadas (2FA step-up, separação de escopo do `agent_token`, hash-chain) adotado depois. Onde este documento menciona "somente leitura no MVP" ou "5ª checagem futura", leia como contexto histórico, não como decisão vigente.

---

## 1. Recapitulando o que já foi decidido (para não recomeçar do zero)

- Produto: SaaS que audita configuração de firewalls pfSense (regras arriscadas, certificados expirando, versão x CVE, drift de configuração), somente leitura no MVP **(decisão histórica, revertida em 2026-07-08 — ver nota acima)**.
- Público inicial: gestor de TI individual com 1+ firewalls próprios, self-service. MSP multi-tenant é expansão futura, não o público de entrada.
- Distribuição: 100% remota, sem venda presencial, aquisição via conteúdo técnico e comunidades (Reddit, fórum Netgate), cobrança em USD.
- Coleta de dados: agente leve instalado no próprio pfSense (via Cron), que faz *push* de dados para a nuvem via HTTPS — não pull, porque a API do pfSense normalmente só responde na LAN.
- Concorrência mapeada: PFMonitor e PFSense Manager (plugin ConnectWise), ambos focados em métricas de infraestrutura (CPU/RAM/latência), nenhum focado em compliance/CVE/auditoria de regras.

## 2. Problemas e inconsistências no escopo atual

### 2.1 — "Somente leitura" não elimina o risco de segurança, só o risco de disponibilidade
A decisão de read-only no MVP foi para evitar que um bug no software derrube a rede de um cliente. Correto. Mas isso **não resolve o problema de segurança de um tipo diferente**: o próprio agente e o próprio backend agora se tornam um alvo de altíssimo valor. Se alguém comprometer o backend do FireAudit, ele terá em um único lugar: as regras de firewall, topologia de rede, versões de software e (pior) potencialmente a API key de acesso de centenas de firewalls de clientes diferentes. Isso é uma central de inteligência para um atacante — uma violação nesse produto é ordens de magnitude piorque uma violação de um único cliente.

**Implicação de arquitetura:** a API key do cliente nunca pode ser armazenada em texto plano no banco, precisa ser criptografada em repouso com uma chave gerenciada separadamente (KMS), e idealmente o agente não deveria nem precisar enviar a API key para a nuvem — ele já a usa localmente para consultar a API; o que sobe para a nuvem é o *resultado* da consulta, não a credencial. Vou formalizar isso na Fase 5, mas o ponto crítico é: **o modelo de dados e o fluxo do agente precisam ser desenhados considerando isso desde a Fase 3/4**, não como um retrofit de segurança depois.

### 2.2 — "Push do agente" tem uma lacuna: quem inicia a atualização/comando de configuração do agente?
Um agente cron simples funciona bem para *enviar* dados. Mas o que acontece quando você (o produto) precisa mudar o comportamento do agente — por exemplo, adicionar uma 5ª checagem, ou corrigir um bug no script? Sem canal de volta, você depende do cliente atualizar manualmente o script no Cron de cada firewall. Em escala (10, 100, 1000 clientes) isso é operacionalmente inviável.

**Pergunta que precisa de decisão:** o agente deve ter auto-update (ex: baixa a versão mais nova do script antes de rodar, de uma URL fixa controlada por você) ou vamos aceitar que updates de agente são manuais no início e resolver isso só quando a base crescer? Isso é uma decisão de trade-off legítima para o MVP, mas precisa ser uma decisão consciente, não um buraco esquecido.

### 2.3 — "Versão x CVE" é a checagem de maior valor percebido e a mais arriscada de fazer mal
Anunciar "seu firewall tem uma vulnerabilidade conhecida" e estar errado (falso positivo, ou peor, falso negativo — dizer que está seguro quando não está) destrói confiança rapidamente num produto de segurança. Isso exige uma fonte de dados de CVE mantida e atualizada (ex: NVD feed, ou parceria com uma base como VulnDB), e um processo de mapeamento versão→CVE que precisa de manutenção contínua — não é "escreve uma vez e esquece". Isso é subestimado no plano informal que tínhamos até agora.

**Implicação:** este recurso deve ser tratado com um "disclaimer" de confiabilidade desde o dia 1 (ex: "baseado no CVE database público, pode não cobrir 100% dos casos") e a lista curada manualmente proposta anteriormente precisa de um processo de atualização recorrente definido — não pode ser "faço uma vez no lançamento".

### 2.4 — Multi-tenancy: decidir agora ou depois custa caro se decidido tarde
Foi decidido que MVP é "single firewall por conta" e multi-tenant MSP é fase 2/3. Isso é razoável para escopo, mas **multi-tenancy é uma decisão de banco de dados e de modelo de permissões que é dolorosa de adicionar depois** se o esquema inicial não já tiver o conceito de "organização" versus "usuário" desde o início. Ou seja: podemos (e devemos) **atrasar a funcionalidade** de multi-tenant, mas não devemos atrasar a **modelagem** que a suporta. Vou desenhar o banco de dados já com `organizations` como entidade de primeira classe desde a Fase 4, mesmo que o MVP só permita 1 usuário por organização — isso custa quase nada agora e evita uma migração dolorosa depois.

### 2.5 — O modelo de precificação sugerido (Free / Starter $19 / MSP $49) não tem uma métrica de valor clara
Cobrar "por firewall" é comum, mas é fácil de simplesmente evitar do lado do cliente (ex: um cliente com 6 firewalls no plano de 5 só... não cadastra o 6º, ou cria 2 contas grátis). Além disso, "Free = 1 firewall" compete diretamente com o "Starter" sem uma razão forte para o cliente fazer upgrade além de quantidade — não há gancho de valor (ex: funcionalidade travada) que empurre a conversão.

**Pergunta que precisa de decisão:** qual é o gatilho real de upgrade — quantidade de firewalls, funcionalidades premium (ex: relatório PDF, retenção de histórico, alertas via Slack/Telegram), ou ambos? Isso muda o desenho de billing e de feature flags no backend.

### 2.6 — Falta um requisito não-funcional crítico: o que acontece quando o agente para de enviar dados?
Se um firewall para de mandar check-in (rede caiu, script quebrou, cliente desinstalou), isso **é em si um evento de risco** — "seu firewall está sem visibilidade há X horas" é tão importante quanto uma regra insegura. Isso não estava explicitamente no escopo do wedge original (as 4 checagens eram todas sobre o *conteúdo* da configuração, nenhuma sobre a *ausência* de dados). Vou adicionar isso como o 5º tipo de achado no PRD.

### 2.7 — Falta considerar timezone e formato de dados para público internacional
Já foi decidido que o público é internacional (USD, conteúdo em inglês). Isso tem implicações concretas: timestamps devem ser armazenados em UTC e exibidos no timezone do usuário; datas de expiração de certificado/relatórios não podem assumir formato brasileiro (DD/MM/AAAA); e o produto final não deveria ter nenhum texto fixo em português no código (usar i18n desde o início, mesmo que só um idioma exista por ora, evita retrabalho).

### 2.8 — Risco de negócio não mapeado: dependência de uma única tecnologia de firewall
100% da tese de receita depende do ecossistema pfSense continuar popular e da Netgate não lançar uma funcionalidade nativa equivalente (eles já têm "Netgate Cloud" para gestão centralizada de dispositivos Netgate — vale investigar até que ponto isso já compete ou pode vir a competir diretamente). Isso não invalida o produto, mas é um risco de plataforma que deveria ser monitorado, e reforça a necessidade de eventualmente suportar OPNsense (fase 4 do roadmap) como diversificação, não só como expansão de mercado.

## 3. Funcionalidades ocultas que aumentam valor percebido sem inflar demais o escopo

- **Health check do próprio agente** (ver 2.6): "última vez visto" já vira feature de valor imediato, quase gratuita de implementar junto com o resto.
- **Assinatura/verificação de integridade dos dados enviados pelo agente**: evita que dados corrompidos ou adulterados gerem falsos achados — simples de adicionar (hash/HMAC) e evita dor de cabeça de debugging depois.
- **Modo "somente ler uma vez" (snapshot manual) antes de configurar o Cron**: permite ao usuário ver o valor do produto imediatamente após colar a API key, sem esperar o primeiro ciclo do Cron — reduz fricção de ativação (time-to-value).
- **Webhook de saída para alertas** (Slack, Discord, Telegram, genérico): público técnico internacional valoriza isso mais que email na maioria dos casos, e é relativamente barato de implementar de forma genérica.

## 4. Riscos técnicos a monitorar (não bloqueiam o MVP, mas devem estar no radar)

- Mudança de formato de endpoints entre versões do pacote RESTAPI do pfSense (já observado na sua própria experiência) — precisa de uma camada de "adapter" versionada, não parsing rígido.
- Rate limiting / carga no backend se muitos agentes fizerem check-in no mesmo intervalo de Cron (ex: todos configurados para rodar exatamente no minuto 0) — mitigável com jitter no agente (pequeno atraso aleatório).
- Confiabilidade da lista de CVE (ver 2.3) — risco de reputação, não só técnico.

## 5. Riscos de negócio a monitorar

- Ciclo de confiança em produto de segurança vendido self-service para um público altamente tecnicamente cético (comunidade pfSense/homelab tende a desconfiar de SaaS fechado, prefere open-source). Isso sugere considerar, como estratégia futura (não MVP), abrir o código do **agente** (não do backend) como open-source — aumenta confiança sem comprometer o modelo de negócio, que está no backend/dashboard, não no agente.
- Dependência de plataforma única (pfSense) — ver 2.8.

## 6. Decisões que preciso que você tome antes de eu avançar para a Fase 2

Essas não são perguntas retóricas — elas mudam o desenho do PRD e da arquitetura de forma material.