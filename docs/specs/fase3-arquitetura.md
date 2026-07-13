# Fase 3 — Arquitetura de Software
## Produto: FireAudit — v1 (produto completo, inclui escrita remota — ver nota abaixo)

Contexto que guia toda decisão desta fase: fundador solo, 10-20h/semana, orçamento de infraestrutura ~USD 20/mês, sem validação de mercado ainda confirmada. Toda escolha abaixo é otimizada para **velocidade de iteração e baixo custo de manutenção por uma pessoa**, com pontos explícitos de "onde isso vai precisar mudar quando crescer" — não para parecer sofisticada.

**Atualização de 2026-07-08 — escopo do v1 passou a incluir o produto completo (`fase2-prd.md`, nota de escopo no topo):** a Fase 3 original tratava a escrita remota (tier Premium) como um "bounded context separado a ser tratado quando/se for construído" (seção 3) — isso deixou de ser hipotético. As seções 3, 5 e 6 foram atualizadas para incorporar o motor de comandos remotos e a 6ª estratégia de análise (`duplicate_rule`) como parte do desenho desde o início, não como extensão futura.

---

## 1. Decisão macro: Monólito modular (não microsserviços)

**Escolha:** um único serviço backend (API + motor de análise + workers de fila), estruturado internamente em módulos bem definidos, não em serviços distribuídos separados.

**Por que não microsserviços:** microsserviços resolvem um problema que este produto não tem ainda — escalar times diferentes trabalhando em paralelo sem se atrapalhar, e escalar partes do sistema independentemente sob carga muito diferente. Com uma pessoa escrevendo todo o código, microsserviços só adicionam custo (múltiplos deploys, rede entre serviços, observabilidade distribuída, mais infraestrutura = mais dinheiro) sem nenhum benefício correspondente. Isso seria overengineering na definição literal do prompt-mestre: "evite quando não gerar benefícios reais".

**Quando reconsiderar:** se o motor de análise de compliance se tornar computacionalmente pesado (ex: análise de milhares de firewalls simultaneamente) a ponto de competir por recursos com a API de usuários, separar esse worker em um processo/serviço distinto (não necessariamente um "microsserviço" completo, apenas um processo separado rodando a mesma base de código) já resolve 90% do problema sem reescrever nada.

## 2. Arquitetura em camadas — Clean Architecture (adaptada, não dogmática)

Estrutura de pastas/módulos:

```
/app
  /domain          → entidades e regras de negócio puras (Organization, Firewall, Finding, User)
                      sem dependência de framework, banco, ou HTTP
  /application      → casos de uso (ex: RegisterFirewall, IngestSnapshot, RunComplianceCheck,
                      UpgradeSubscription) — orquestram o domínio, ainda sem detalhes de infra
  /infrastructure    → implementações concretas: repositórios Postgres, cliente Stripe,
                      envio de email/webhook, storage de secrets/KMS
  /api               → camada HTTP (FastAPI): rotas, schemas de request/response, autenticação
  /workers           → jobs assíncronos (processamento de snapshot, envio de alerta, geração de PDF)
```

**Por que Clean Architecture (mesmo que "levemente"):** a regra mais importante que se aproveita disso é a **inversão de dependência do domínio em relação à infraestrutura** — o motor de análise de compliance (a parte mais valiosa e diferenciada do produto) não deveria saber que existe um banco Postgres ou um FastAPI. Isso importa concretamente aqui porque: (a) facilita testar o motor de análise com dados falsos sem precisar de banco de dados rodando; (b) se algum dia trocar Postgres por outra coisa, ou adicionar suporte a OPNsense com um schema de dados diferente, o núcleo de regras de negócio não muda.

**Onde NÃO vou aplicar rigor máximo:** não vou criar interfaces abstratas para absolutamente tudo (ex: um `IEmailSender` só faz sentido se realmente cogitarmos trocar de provedor de email; se não, é indireção sem benefício). SOLID é seguido nos pontos que importam (Single Responsibility nos casos de uso, Dependency Inversion na fronteira domínio↔infra), não como checklist obrigatório em cada classe.

## 3. DDD — usado de forma leve (não "DDD tático completo")

Não há necessidade de Aggregates complexos, Value Objects extensivos, ou Domain Events sofisticados nesta fase — o domínio é relativamente simples (organizações, firewalls, snapshots, achados). O que se aproveita do DDD:

- **Linguagem ubíqua:** os termos usados no código (Organization, Firewall, Snapshot, Finding, Severity) são exatamente os mesmos usados no PRD e nas telas — evita a "tradução" mental entre negócio e código que gera bugs de entendimento.
- **Bounded context — atualizado (2026-07-08):** o tier Premium (edição remota) deixou de ser hipotético e passa a existir desde o v1. Tratamos como um sub-contexto dentro do mesmo monólito modular, não um contexto totalmente isolado: vive em `application/remote_commands/` e `domain/firewall_command.py` (nomes ilustrativos), com suas próprias regras de autorização (2FA obrigatório, tier Premium, ver Fase 5 seção 11) e seu próprio agregado de auditoria (`RemoteChangeLog`) — mas reaproveita a mesma infraestrutura de banco, autenticação de base e camada de API do resto do sistema. Não introduzir um serviço/deploy separado para isso agora seria o mesmo erro rejeitado na seção 1 (microsserviços prematuros); a separação que importa aqui é de módulo e de regra de negócio, não de processo.

## 4. CQRS e Event-Driven — avaliados e descartados para o MVP

**CQRS (separar modelos de leitura e escrita):** não se justifica agora. O volume de dados e a complexidade de consulta no MVP não geram o problema que CQRS resolve (leituras e escritas com necessidades de modelagem/performance muito diferentes). Reavaliar se o dashboard precisar de agregações pesadas sobre milhões de snapshots — nesse ponto, uma tabela de "leitura materializada" simples (não CQRS completo) provavelmente já resolve.

**Event-Driven (arquitetura baseada em eventos/message broker):** parcialmente aproveitado, não como arquitetura geral. Não vamos introduzir Kafka/RabbitMQ como espinha dorsal do sistema — isso é infraestrutura cara e complexa demais para o estágio atual. Mas o fluxo de "snapshot recebido → motor de análise roda → alerta é enviado" se beneficia de uma **fila simples** (ver seção 6), que é uma forma leve e pragmática do mesmo princípio sem a sobrecarga operacional de um broker dedicado.

## 5. Padrões de projeto aplicados (pontuais, não decorativos)

- **Repository Pattern:** encapsula acesso a dados (ex: `FirewallRepository`) — facilita testes e mantém a camada de aplicação sem SQL espalhado.
- **Strategy Pattern:** para o motor de análise — cada tipo de checagem (regra arriscada, certificado, CVE, drift, agente offline e, desde 2026-07-08, **regra duplicada**) é uma "estratégia" independente que implementa uma interface comum (`AnalysisCheck.run(snapshot) -> List[Finding]`). São 6 estratégias no v1, não 5 — o exemplo original da fase ("adicionar uma 6ª checagem no futuro não deve exigir tocar nas outras 5") deixou de ser hipotético: `DuplicateRuleCheck` é essa 6ª checagem, adicionada como uma nova classe sem tocar nas outras 5, exatamente como o padrão previa.
- **Adapter Pattern:** para lidar com diferenças de formato de API entre versões do pacote RESTAPI do pfSense (risco identificado na Fase 1) — um adapter por versão suportada, escondendo a diferença do resto do sistema. Reaproveitado também para a escrita remota: o payload de criação/edição de regra precisa do mesmo tratamento de diferença de formato entre versões do pfSense que a leitura já tinha, então o comando remoto passa pelo mesmo adapter antes de ser enviado ao agente.
- **Command Pattern — novo (2026-07-08):** cada operação de escrita remota (`create_rule`/`update_rule`/`delete_rule`) é modelada como um objeto de comando imutável (`FirewallCommand`, já refletido na tabela `firewall_commands`, Fase 4) que encapsula o quê fazer, mas não o executa diretamente — ele é serializado, enfileirado, e só executado pelo agente depois de confirmado. Esse é o padrão certo aqui (em vez de uma chamada de função direta) porque a operação precisa sobreviver a um intervalo de tempo entre "usuário pede" e "agente executa" (o agente só executa no próximo polling), precisa ser auditável como um objeto distinto (`RemoteChangeLog` referencia o comando, não uma chamada de função efêmera), e precisa suportar rejeição/expiração antes da execução (Fase 5, seção 11) — nenhuma dessas propriedades existe numa chamada de função síncrona comum.

## 6. Processamento assíncrono (fila leve, sem broker dedicado)

Escolha: usar o próprio Postgres como fila (padrão "job table" / ou biblioteca como `arq`/`Celery` com Redis, se o orçamento permitir um Redis pequeno). Justificativa de custo: evita a necessidade de operar RabbitMQ/Kafka, que seria desproporcional ao volume esperado no início (dezenas a centenas de firewalls, não milhões de eventos por segundo).

Fluxo: endpoint de ingestão salva o snapshot bruto e enfileira um job de "processar snapshot" → worker separado (mesmo código-base, processo distinto) pega o job, roda as 6 estratégias de análise, salva achados, e — desde 2026-07-08 — também avalia as regras de alerta customizadas (`alert_rules`) contra as métricas do snapshot processado. Essa avaliação de alertas customizados é deliberadamente **um passo separado das 6 `AnalysisCheck`**, não uma 7ª estratégia: as estratégias produzem `Finding` (achados de compliance/segurança, com semântica de "aberto/resolvido"), enquanto um alerta customizado é uma comparação simples de métrica × limiar que produz um disparo pontual (`AlertDelivery` direto, sem passar por `Finding`) — misturar os dois no mesmo pipeline forçaria o motor de análise a carregar um conceito (limiar numérico arbitrário definido pelo usuário) que não tem nada a ver com o que `AnalysisCheck` foi desenhado par