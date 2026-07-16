# Fase 12 — Operação e Manutenção (SDLC)
## Produto: FireAudit — v1 (produto completo, inclui escrita remota — ver nota abaixo)

**Atualização de 2026-07-08 — escopo do v1 passou a incluir escrita remota:** esta fase não previa nenhum processo operacional específico para comandos remotos (a funcionalidade não existia no escopo original). As seções 1 e 4 foram atualizadas com o sinal de monitoramento e a severidade de incidente correspondentes — comando remoto travado/falho é tratado com o mesmo rigor operacional que fila de snapshot travada, pelo mesmo motivo (falha silenciosa é o pior caso).

Esta fase fecha o ciclo de vida completo do software: as Fases 9-10 já desenharam a infraestrutura e a observabilidade técnica (o quê está instrumentado); esta fase desenha o **processo humano** em torno disso — o que Eduardo faz quando um alerta dispara, como uma versão nova chega em produção sem drama, como um cliente é atendido, e como uma mudança de API não quebra um agente que já está instalado em produção há meses. Restrição que domina tudo aqui, igual às fases anteriores: uma pessoa, 10-20h/semana, sem equipe de operações — todo processo precisa sobreviver a isso sem depender de disciplina heroica constante.

---

## 1. Monitoramento em produção — do sinal à ação

A Fase 9-10 (seção 2.3) já definiu o que é instrumentado (Sentry para exceções, UptimeRobot para health check, stack TIG/Grafana reaproveitada para infraestrutura). Esta seção define o que fazer quando esses sinais disparam.

| Sinal | Onde chega | Ação esperada |
|---|---|---|
| `GET /v1/health` falha (UptimeRobot) | Email/SMS imediato (plano gratuito do UptimeRobot já notifica) | Verificar se é a VPS, o container `api`, ou o Postgres — `docker compose ps` primeiro, logs depois |
| Exceção não tratada em produção (Sentry) | Email/dashboard do Sentry | Triagem manual: é um bug real recorrente ou um caso de borda isolado? Vira item de backlog se não for urgente, hotfix se estiver quebrando ingestão |
| CPU/RAM/disco da VPS acima do limiar (Grafana, stack já existente) | Dashboard existente, sem alerta push configurado ainda no MVP | Checagem periódica manual (não é uma métrica que precisa de resposta em minutos no volume atual) |
| Fila de snapshots (`snapshots.processing_status = 'queued'`) crescendo sem processar | Não há alerta dedicado ainda — **lacuna aceita conscientemente no MVP** | Reconsiderar assim que houver múltiplos clientes pagantes: um worker parado sem alerta significa "todo cliente perde achados novos" silenciosamente, é o tipo de falha que este produto não pode se dar ao luxo de descobrir tarde (coerente com o princípio da Fase 1, seção 2.6, sobre ausência de dado ser em si um risco) |
| **Comandos remotos presos em `confirmed`/`sent_to_agent` além do esperado (novo, 2026-07-08)** | Não há alerta dedicado ainda — mesma lacuna aceita conscientemente da fila de snapshots, acima | **Prioridade de resolução mais alta que a fila de snapshots equivalente**, pelo motivo já descrito na Fase 11 (seção 1): aqui o cliente não só "perde visibilidade", ele pode achar que uma correção de segurança foi aplicada quando não foi (ex: confirmou remover uma regra `any-any` há 20 minutos, ainda não foi aplicada, e o cliente segue exposto acreditando o contrário). Checagem manual periódica é o mitigador atual; alerta dedicado deve ser o primeiro item de observabilidade a sair da lista de "lacuna aceita" quando houver o primeiro cliente Premium pagante — gatilho mais cedo que o da fila de snapshot. |

**Por que não existe um alerta dedicado para a fila ainda:** é a lacuna mais importante desta seção e está documentada aqui de propósito, não escondida — no volume do MVP (poucos firewalls, checagem manual ocasional já detectaria isso a tempo), o custo de configurar um alerta específico compete com tempo mais escasso ainda (10-20h/semana). **Gatilho de reconsideração:** primeiro cliente pagante real — a partir daí, "não notei que a fila travou" deixa de ser um risco aceitável e passa a ser um risco de churn direto.

## 2. Rotina operacional periódica (o que não é reativo)

Nem toda manutenção é resposta a um alerta — existem tarefas de calendário que, se ignoradas, geram incidentes evitáveis:

- **Verificação de backup restaurável:** a Fase 5 (seção 8) já define backup diário automático, mas um backup que nunca foi restaurado em teste é uma suposição, não uma garantia. Rotina mínima: um teste de restauração manual (`pg_restore` em ambiente local/temporário) a cada troca de trimestre — não precisa ser automatizado no MVP, precisa apenas *acontecer*, com uma data marcada para não ser esquecido indefinidamente.
- **Atualização da base de CVE curada:** já sinalizado como risco de negócio na Fase 1 (seção 2.3) — a checagem `known_cve` (Fase 3, Strategy Pattern) depende de uma fonte de dados que precisa de manutenção recorrente, não é "escreve uma vez e esquece". Rotina mínima: revisão mensal da fonte de CVE usada (ex: feed do NVD) e atualização do mapeamento versão→CVE no código/dado do motor de análise.
- **Atualização de dependências e patches de segurança:** bibliotecas Python/Node e a imagem base do Docker recebem patches de segurança continuamente — rotina mínima: revisão mensal de dependências com vulnerabilidade conhecida (ex: `pip-audit`, `npm audit`, já baratos de rodar no CI existente da Fase 9-10) antes que vire um incidente descoberto por terceiros.
- **Revisão de segurança pré-release:** para releases que tocam autenticação, ingestão ou billing (as áreas de maior risco já mapeadas na Fase 11, seção 1), uma passada de revisão de segurança do próprio código antes do deploy — mencionada na Fase 11 (seção 4) como substituto pragmático a um pentest formal fora de orçamento.

## 3. Versionamento e processo de release

- **Backend/API:** versionamento semântico informal do próprio serviço (tags Git, ex: `v0.3.0`), não necessariamente do contrato de API em si — o contrato de API já tem seu próprio versionamento de URL (`/v1/...`, Fase 8, seção 1), que é o que realmente importa para clientes externos (o agente). Uma nova versão do backend pode sair sem qualquer mudança de contrato de API.
- **Agente (o componente mais sensível a versionar mal):** como o agente faz auto-update a partir de uma URL fixa (Fase 3, seção 7), toda nova versão publicada em `latest.sh` passa a ser adotada automaticamente por **todos** os agentes instalados no próximo ciclo de Cron — isso significa que um bug numa nova versão do agente se propaga para todos os clientes de uma vez, sem canário e sem rollback automático do lado do cliente. **Processo obrigatório antes de publicar uma nova versão do agente:** testar manualmente contra pelo menos uma instância pfSense real (ambiente próprio de Eduardo) antes de atualizar a URL de distribuição — nunca publicar direto para todos os clientes como primeiro teste. Reconsiderar um mecanismo de rollout gradual (ex: % de agentes, ou versão fixada por organização) apenas quando a base de clientes justificar esse investimento; no MVP, o teste manual prévio é o controle de risco proporcional.
- **Changelog:** mudanças relevantes para o usuário final (novo tipo de achado, nova opção de alerta) registradas em um changelog simples visível no dashboard ou em release notes — mudanças puramente internas (refactor, dependência) não precisam de changelog voltado ao cliente.
- **Cadência:** sem cadência fixa obrigatória (ex: não é "toda sexta") — release quando uma mudança está testada e pronta (Fase 11, quality gates), coerente com o ritmo de uma pessoa em poucas horas por semana; forçar uma cadência artificial aqui adicionaria pressão sem benefício real.

## 4. Gestão de incidentes

Sem uma equipe de operações, "gestão de incidentes" para um fundador solo é sobretudo triagem e comunicação, não um processo formal de guerra:

| Severidade | Exemplo | Resposta esperada |
|---|---|---|
| Crítica | Backend fora do ar; ingestão rejeitando todos os snapshots; vazamento de dados suspeito | Resposta assim que notado (alerta do UptimeRobot/Sentry), mesmo fora do horário de trabalho de TI declarado (7h-18h) — disponibilidade do produto não pode esperar o próximo bloco de 10-20h agendado |
| **Alta, com tratamento equivalente a crítica no fundo (novo, 2026-07-08)** | Comando remoto confirmado (`status = confirmed`/`sent_to_agent`) que não avança para `applied`/`failed` depois de múltiplos ciclos de polling esperados; ou agente reporta `status: "failed"` num comando de segurança (ex: remoção de regra `any-any`) | Verificação manual assim que notado (checagem periódica, seção 1) — não é tecnicamente "backend fora do ar", mas o impacto no cliente é do mesmo tipo (ele acredita estar protegido e não está); tratar com a mesma urgência de resposta da linha "Crítica" acima, não esperar o próximo bloco agendado se o comando envolver remoção de exposição de segurança |
| Alta | Um cliente específico não recebe alertas (bug no envio de webhook); achado com falso positivo recorrente | Resposta no mesmo dia ou próximo bloco de trabalho disponível |
| Baixa | Bug cosmético de UI; typo em mensagem de erro | Vira item de backlog, sem urgência de resposta |

- **Comunicação com clientes durante incidente:** no MVP, não existe página de status pública dedicada (ex: Statuspage) — seria overengineering de comunicação para a base de clientes inicial; comunicação direta por email para os afetados é suficiente. Reconsiderar uma status page pública quando o volume de clientes tornar comunicação individual impraticável.
- **Pós-incidente:** para incidentes de severidade crítica ou alta, um registro informal (o que aconteceu, causa raiz, o que foi corrigido) guardado como nota — não um post-mortem formal de equipe, mas o suficiente para não repetir o mesmo erro sem ter documentado por que ele aconteceu.

## 5. Suporte ao cliente

Já estabelecido como restrição na Fase 2 (seção 11): suporte assíncrono/best-effort, sem SLA formal, sem chamadas de vídeo fora do expediente exceto pontualmente. Esta seção formaliza o canal:

- **Canal único no MVP:** email de suporte (ou caixa compartilhada simples) — não introduzir uma ferramenta de helpdesk dedicada (Zendesk, Intercom) enquanto o volume de tickets não justificar o custo/aprendizado de uma ferramenta nova; um cliente com dúvida no MVP não gera volume que uma caixa de email não resolva.
- **Triagem:** perguntas de "como fazer X" vs. bugs reais vs. solicitações de feature — só a segunda categoria (bug real) compete com o tempo de desenvolvimento imediatamente; as outras entram no fluxo normal (documentação/FAQ para a primeira, backlog priorizado para a terceira).
- **Caso especial — reporte de vulnerabilidade de segurança:** dado que este é um produto de segurança (Fase 1, seção 2.1, "alvo de alto valor"), precisa existir um canal claro e visível (ex: `security@` ou página de "responsible disclosure") para pesquisadores reportarem falhas antes de divulgação pública — isso é barato de configurar agora e caro de não ter no dia em que alguém encontrar algo e não souber a quem avisar.

## 6. Política de deprecação de API e mudanças que quebram compatibilidade

- O prefixo `/v1/` (Fase 8, seção 1) existe exatamente para isolar o momento em que uma mudança incompatível for necessária — nesse momento, um novo prefixo (`/v2/`) é criado, e `/v1/` continua funcionando durante um período de transição anunciado, não desligado da noite para o dia.
- **O agente é o cliente mais crítico de versionar com cuidado:** diferente de um cliente de API tradicional (que um desenvolvedor externo atualiza no próprio ritmo), o agente do FireAudit se auto-atualiza (seção 3) e o backend não tem controle direto sobre quando cada instalação específica vai rodar a versão nova — isso significa que o backend precisa manter compatibilidade retroativa com pelo menos a versão anterior do payload de ingestão por um período de transição sempre que o formato do payload mudar, mesmo depois de publicar uma nova versão do agente (nem todo agente atualiza no mesmo ciclo de Cron).
- **Regra prática:** nenhuma mudança de campo obrigatório ou remoção de campo no payload de ingestão sem um período de compatibilidade dupla (backend aceita formato antigo e novo simultaneamente) — adicionar campo novo opcional não exige essa cautela, remover ou tornar obrigatório exige.

## 7. Onde esta operação vai doer no futuro (documentado de propósito)

- A ausência de alerta dedicado para a fila travada (seção 1) é a lacuna mais perigosa desta fase — está documentada e não esquecida, com gatilho claro (primeiro cliente pagante) para ser resolvida antes que gere um incidente real de "cliente sem visibilidade sem saber". **(Reforçado em 2026-07-08):** dentro dessa mesma lacuna, a variante de comando remoto travado é a de maior risco — o gatilho de resolução para ela é o primeiro cliente **Premium** pagante especificamente, mais cedo do que o gatilho geral de "primeiro cliente pagante" da fila de snapshot, porque o custo de descobrir tarde não é só "perdeu visibilidade", é "acreditou estar protegido sem estar".
- O rollout de agente sem canário (seção 3) é aceitável para poucos clientes early-adopters tecnicamente tolerantes (Persona 3/Alex, Fase 2) mas se tornará inaceitável assim que a base incluir clientes pagantes (Persona 1/Marcos) que não esperam ser o teste de uma versão nova — o teste manual prévio é a mitigação atual, um mecanismo de rollout gradual é a evolução natural.
- Suporte via email único (seção 5) não escala além de um volume pequeno de tickets simultâneos — o gatilho de migração para uma ferramenta de helpdesk é o mesmo tipo de sintoma já usado em outras decisões desta série de fases: resolver quando o volume real de tickets tornar a caixa de email difícil de triar, não antes.
- Sem página de status pública (seção 4), toda comunicação de incidente depende de Eduardo lembrar de notificar manualmente cada cliente afetado — funciona com poucos clientes, mas é o próximo processo a formalizar quando esse número crescer.