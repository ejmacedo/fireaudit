# Fase 6-7 — UX e UI Detalhado
## Produto: FireAudit — v1 (produto completo, inclui escrita remota — ver nota abaixo)

Este documento parte do wireframe já existente (`wireframe-dashboard.html` — login, onboarding, dashboard, detalhe de firewall, billing) e adiciona o que um wireframe estático não cobre: fluxos completos, estados de cada tela (loading, vazio, erro, sucesso), decisões de UX justificadas, e especificação de UI suficiente para quem for implementar (Fable ou outro dev) não precisar adivinhar comportamento.

**Atualização de 2026-07-08 — escopo do v1 passou a incluir o produto completo (`fase2-prd.md`, nota de escopo no topo):** a versão original desta fase tratava edição remota de regra como "quando o tier Premium chegar" (seção 6) e filtros de dashboard como "mapeado para v2/v3, não no MVP de firewall único" (seção 6). Ambos entram no v1. Esta atualização adiciona a seção 2.4 (fluxo de edição de regra remota), 2.5 (fluxo de criador de alertas customizados), 3.4 é estendida com a especificação real da aba "Regras & VPN" com controles de escrita, 3.7 (novo — criador de alertas) e 3.8 (novo — filtros de dashboard), além de corrigir a seção 6.

---

## 1. Princípios de UX que guiam as decisões desta fase

- **Time-to-value rápido:** a Fase 1 (seção 3) já identificou que "snapshot manual antes do Cron" reduz fricção de ativação — isso vira requisito explícito de fluxo nesta fase (seção 3.2).
- **Público tecnicamente cético, não iniciante:** a persona primária (Marcos, Fase 2) é administrador de TI, não usuário final leigo. Isso significa: pode-se usar terminologia técnica direta (não precisa "traduzir" para linguagem leiga), mas a interface não pode escamotear o que o produto faz com os dados — transparência sobre coleta/uso de dados é parte da confiança que esse público exige (Fase 1, seção 5).
- **Estado vazio nunca é um beco sem saída:** todo estado vazio (sem firewalls, sem achados, sem alertas configurados) tem uma ação clara de próximo passo, nunca é só uma mensagem passiva.
- **Erros são acionáveis:** mensagem de erro sempre inclui o que o usuário pode fazer a respeito, nunca só "algo deu errado".

## 2. Mapa de fluxos (jornadas completas)

### 2.1 Fluxo de cadastro → primeiro valor (ativação)
```
Landing → Cadastro (email/senha) → Confirmação de email
  → Tela "Adicionar primeiro firewall" (nome + geração de token)
  → Tela de instruções (guia + vídeo embarcado + script Cron personalizado com token já embutido)
  → [usuário roda o script no pfSense]
  → Tela de espera ("aguardando primeiro check-in...") com polling
  → Primeiro snapshot recebido → redireciona automaticamente para Dashboard já populado
```
**Decisão de UX:** a tela de espera não é um spinner genérico — mostra o comando exato que o usuário rodou (para ele confirmar visualmente que copiou certo) e um link "não está funcionando?" que leva a um checklist de troubleshooting (baseado nos 10 pontos reais de erro documentados em `feedback_pfsense_api_setup.md` da memória do usuário) — isso transforma uma fonte real de fricção conhecida em conteúdo de ajuda proativo, não reativo.

### 2.2 Fluxo de upgrade Free → Pro
```
Dashboard (Free) → usuário vê card "3 achados críticos disponíveis no plano Pro" (teaser, já decidido na Fase 2, caso de uso 2)
  → clique → modal de comparação de planos (Free vs Pro, lado a lado)
  → "Assinar Pro" → Stripe Checkout (redirect)
  → retorno via webhook confirmado → Dashboard atualiza para visão Pro (sem precisar recarregar manualmente — ver seção 4, estado "upgrade em processamento")
```
**Decisão de UX:** o teaser mostra a *contagem* e a *severidade* dos achados bloqueados ("3 achados, incluindo 1 crítico") mas nunca o conteúdo do achado em si — isso é o gancho de conversão (Fase 1, seção 2.5) sem violar a regra de negócio de que dados sensíveis só existem para tiers pagos (Fase 2, seção 8).

### 2.3 Fluxo de "agente offline" (achado reativo)
```
Agente para de reportar → backend detecta ausência de check-in > limiar
  → Finding tipo `agent_offline` criado → AlertDelivery disparado (email/webhook)
  → Usuário abre o link do alerta → vai direto para a tela de detalhe do firewall específico, aba "Achados", já filtrado por esse achado
```
**Decisão de UX:** todo alerta (email/webhook) contém um link profundo (deep link) direto para o contexto exato do problema — nunca só "algo aconteceu, faça login para ver", que exigiria o usuário navegar manualmente até achar o que gerou o alerta.

### 2.4 Fluxo de edição remota de regra (Premium) — novo, 2026-07-08
```
Aba "Regras & VPN" (Premium) → usuário clica "Criar regra" (ou "Editar"/"Excluir" numa regra existente)
  → Formulário de regra (interface, ação, origem, destino, protocolo, porta)
  → Preview: "Esta alteração vai permitir tráfego de 203.0.113.0/24 para a porta 22 na interface WAN" (texto humano, gerado pelo backend a partir do payload, Fase 8 seção 3)
  → Se usuário não tem 2FA habilitado: bloqueio com CTA "Habilitar 2FA para continuar" (nunca deixa prosseguir sem isso, Fase 5 seção 11)
  → Confirmação: campo de código TOTP + botão "Confirmar alteração"
  → Tela de status: "Alteração confirmada — será aplicada no próximo check-in do agente (até 15 min)"
  → [até 15 min depois] Notificação/atualização de status: "Alteração aplicada com sucesso" ou "Falha ao aplicar: <motivo>"
```
**Decisão de UX crítica:** a tela de status pós-confirmação nunca implica aplicação instantânea — o texto é explícito sobre o intervalo de até 15 minutos (Fase 3, seção 10) para não criar expectativa de tempo real que o produto não entrega. Isso é coerente com a decisão de manter arquitetura de push periódico (não real-time) confirmada por Eduardo.

**Decisão de UX sobre cancelamento:** enquanto o comando está em `pending_confirmation` (ainda não confirmado), existe um botão "Cancelar" bem visível — evita que um comando criado por engano fique "pendurado" até expirar sozinho em 15 min.

### 2.5 Fluxo de criador de alertas customizados — novo, 2026-07-08
```
Tela "Alertas" → aba "Regras customizadas" → "Nova regra de alerta"
  → Seleciona: métrica (dropdown: uso de CPU/RAM/disco, temperatura, contagem de achados críticos, tunnels VPN caídos)
  → Seleciona: operador (maior que / menor que / igual a) + valor limiar + (opcional) "por pelo menos X minutos" (evita alertas de pico momentâneo)
  → Seleciona: aplicar a "todos os firewalls" ou a um firewall específico
  → Seleciona: canal de notificação (reaproveita os já configurados em Configuração de alertas, seção 3.5)
  → Botão "Testar regra agora" — avalia contra o snapshot mais recente e mostra o resultado (ex: "RAM atual: 62% — esta regra DISPARARIA")
  → Salvar
```
**Decisão de UX:** o exemplo de referência do próprio Eduardo ("alertar quando RAM > 50%") é usado como placeholder/exemplo pré-preenchido no formulário vazio, não só na documentação — reduz a barreira de "não sei o que colocar aqui" no primeiro uso.
**Decisão de UX sobre tier:** se a métrica escolhida exigir tier acima do atual (Fase 8, seção 3), o dropdown mostra a métrica com um ícone de cadeado e o mesmo padrão de teaser de upgrade (seção 2.2) ao tentar selecioná-la — nunca deixa selecionar e falhar só no submit.

## 3. Especificação de telas (complementando o wireframe existente)

### 3.1 Login / Cadastro
- Campos: email, senha (cadastro pede confirmação de senha).
- Validação inline (não só no submit): força de senha exibida enquanto digita; email com formato inválido marcado ao perder foco, não a cada tecla (evita "gritar erro" enquanto o usuário ainda está digitando).
- Erro de credencial inválida: mensagem genérica "email ou senha incorretos" (nunca revelar se o email existe ou não — mitigação de enumeração de contas, alinhado com Fase 5).

### 3.2 Onboarding — Adicionar firewall
- Passo 1: nome do firewall (campo livre, ex: "Firewall Matriz SP").
- Passo 2: geração automática do token de ingestão + exibição do script Cron **já com o token embutido**, pronto para copiar (botão "copiar comando") — elimina o passo manual de o usuário substituir um placeholder, fonte comum de erro.
- Passo 3 (a funcionalidade "snapshot manual" da Fase 1, seção 3): botão "Testar agora" que instrui o usuário a rodar o comando uma vez manualmente no terminal do pfSense (fora do Cron) — isso dá feedback imediato de sucesso/erro sem esperar o próximo ciclo agendado, resolvendo diretamente o time-to-value.
- Vídeo embarcado (gravado por Eduardo, decisão já tomada) posicionado ao lado do script, não abaixo — para quem prefere assistir em vez de ler, sem precisar rolar a página.

### 3.3 Dashboard (lista de firewalls)
Estados possíveis:
| Estado | Comportamento |
|---|---|
| Vazio (0 firewalls) | Card central único: "Adicione seu primeiro firewall" com CTA direto para o fluxo 2.1 — nunca uma tabela vazia sem contexto |
| Carregando | Skeleton screens (placeholders cinza no formato dos cards reais), não spinner genérico — comunica estrutura antes do conteúdo carregar |
| Populado | Grid/lista de cards por firewall: nome, status (online/offline/pending — cores: verde/vermelho/cinza), contagem de achados abertos por severidade, "última visto há X" |
| Erro ao carregar | Mensagem + botão "tentar novamente" — nunca tela branca |

**Decisão de UX sobre ordenação:** firewalls com achados críticos abertos aparecem primeiro, independente de ordem alfabética/data de cadastro — o dashboard é uma ferramenta de triagem, não um catálogo; a informação mais urgente deve estar no topo sem o usuário precisar ordenar manualmente.

**Filtros do dashboard — novo, 2026-07-08 (ver seção 3.8 para detalhe):** a ordenação por urgência acima continua sendo o comportamento padrão sem filtro nenhum aplicado; os filtros são um refinamento opcional sobre essa mesma lista, nunca uma tela/rota diferente.

### 3.4 Detalhe do firewall
- Abas: Visão Geral (métricas básicas, todos os tiers) / Achados (Pro+) / Regras & VPN (Pro+, leitura; Premium, leitura + escrita) / Histórico de Alterações (Premium, novo — 2026-07-08) / Configurações (nome, token, exclusão).
- Aba Achados: lista agrupada por severidade (crítico primeiro), cada achado expansível mostrando `details` (JSONB do schema da Fase 4) formatado de forma legível — não é para mostrar o JSON bruto ao usuário, é para a camada de apresentação traduzir cada `check_type` em um template de texto humano (ex: `risky_rule` → "Regra permite tráfego de qualquer origem para qualquer destino na interface WAN"; `duplicate_rule` → "Esta regra é idêntica à regra #N na mesma interface — considere removê-la").
- Botão "marcar como resolvido" por achado (usa o campo `status` da tabela `findings`, Fase 4) — permite ao usuário reconhecer que já tratou algo sem esperar o próximo snapshot confirmar a correção automaticamente (que pode levar até o próximo ciclo de Cron).
- **Achado `duplicate_rule` tem um botão adicional (Premium): "Corrigir agora"** — atalho que pré-preenche o fluxo de edição remota (seção 2.4) com um comando `delete_rule` da regra duplicada, poupando o usuário de navegar manualmente até a aba Regras & VPN para o caso mais comum (apagar a redundante). Continua passando pelo fluxo normal de preview + confirmação 2FA — o atalho é de navegação, não de bypass de segurança.
- Estado "agente offline há X horas": banner de destaque no topo da tela de detalhe (não só um item na lista de achados) — é informação crítica o suficiente para merecer destaque visual próprio.
- **Aba Regras & VPN — especificação de escrita (Premium), novo 2026-07-08:** lista de regras (mesma visualização que já existia para Pro+ read-only) ganha, por linha, os botões "Editar" e "Excluir" quando o tier é Premium; acima da lista, botão "Criar regra". Todos os três disparam o fluxo 2.4. Tiers Pro (sem Premium) veem a mesma lista sem esses botões, mais um banner sutil "Upgrade para Premium para editar regras diretamente" — mesmo padrão de teaser já estabelecido (seção 2.2), não uma tela diferente.
- **Aba Histórico de Alterações (Premium), nova — 2026-07-08:** lista cronológica de `remote_change_logs` (Fase 8, `GET /v1/firewalls/{id}/change-log`) — cada entrada mostra quem fez a alteração, quando, um diff visual simples (antes/depois) e um botão "Desfazer esta alteração" que aciona o fluxo de rollback (Fase 8, `POST .../rollback`) — que por sua vez passa pelo mesmo fluxo de preview+confirmação 2FA da seção 2.4, nunca uma reversão de um clique sem novo consentimento.

### 3.5 Configuração de alertas
- Lista de canais configurados (email sempre existe por padrão, webhooks adicionados manualmente).
- Ao adicionar webhook: campo de URL + botão "Testar" que dispara um alerta de teste imediatamente — confirma que a integração funciona antes do usuário depender dela em um incidente real (mesma lógica de "snapshot manual" aplicada a alertas).
- Erro de teste de webhook: mostra o código de erro HTTP retornado pelo endpoint do cliente (ex: Slack retornou 404) — informação técnica é apropriada aqui dado o público (seção 1).

### 3.6 Billing
- Estado atual do plano sempre visível no topo (não escondido em "configurações") — usuário nunca deveria precisar procurar para saber o que está pagando.
- Ao cancelar: nunca cancelamento imediato de um clique — confirmação explícita com resumo do que será perdido (acesso a regras/VPN, histórico de achados) antes de confirmar. Isso é consistente com a regra geral de "ações destrutivas exigem confirmação explícita" já usada para o tier Premium (Fase 2, regra de negócio).

### 3.7 Criador de alertas customizados (tela) — novo, 2026-07-08
- Nova aba dentro de "Alertas" (ao lado de "Canais", que já existia — seção 3.5): "Regras customizadas".
- Tabela de regras existentes: métrica, condição em texto legível ("RAM > 50% por 5 min"), firewall(s) afetado(s), canal, toggle ativo/inativo (desativar sem excluir — útil para pausar temporariamente sem perder a configuração).
- Estado vazio: CTA "Criar sua primeira regra de alerta", com o exemplo do Eduardo (RAM > 50%) como sugestão de texto no botão ou subtítulo — reduz a barreira de "não sei o que configurar".
- Componentes shadcn/ui reaproveitados: `select` (métrica/operador/canal), `input` (valor limiar/duração), `switch` ou toggle (ativo/inativo), `table` (listagem) — nenhum componente novo fora da lista já mapeada em CLAUDE.md.

### 3.8 Filtros de dashboard — novo, 2026-07-08
- Barra de filtros acima da lista de firewalls/achados (dashboard principal, seção 3.3): severidade (crítico/alto/médio/baixo, multi-seleção), status do firewall (online/offline/pending, multi-seleção), e — só em Conta Multiempresa — empresa-cliente (seletor, reaproveitando a lista já usada no seletor de empresas do mockup).
- Filtros são combináveis (ex: "crítico" + "offline" ao mesmo tempo) e persistem na URL como query params (`?severity=critical&status=offline`) — permite ao usuário salvar/compartilhar um link filtrado, e mantém o filtro ao recarregar a página.
- Estado "nenhum resultado após filtro": mensagem "Nenhum firewall corresponde a estes filtros" + botão "Limpar filtros" — distinto do estado vazio geral (seção 4), porque aqui o problema é o filtro, não a ausência de dados reais.

## 4. Estados transversais (aplicam-se a múltiplas telas)

- **Loading:** skeleton screens em listas/cards; spinners apenas em ações pontuais (botão de submit).
- **Vazio:** sempre com CTA de próximo passo, nunca mensagem passiva isolada.
- **Erro de rede/servidor:** mensagem + ação de retry; nunca expor stack trace ou erro técnico bruto ao usuário final (log técnico vai para observability — Fase 9-10/12, não para a tela).
- **Ação em processamento (ex: upgrade de plano, geração de relatório PDF):** feedback otimista com possibilidade de acompanhar status, evitando o usuário clicar múltiplas vezes por falta de feedback (ex: desabilitar botão + indicador de "processando" imediatamente ao clique).
- **Permissão insuficiente (ex: usuário Free tentando acessar dado Pro via URL direta):** nunca uma tela de erro genérica — redireciona para o mesmo teaser de upgrade do dashboard (seção 2.2), mantendo a experiência de conversão consistente em qualquer ponto de entrada.

## 5. Responsividade e acessibilidade (nível pragmático para o MVP)

- Dashboard e telas administrativas: otimizadas primeiro para desktop (persona é administrador de TI trabalhando de estação de trabalho, não majoritariamente mobile) — responsividade mobile é "funcional, não primorosa" no MVP (ex: tabelas colapsam em cards, mas não há uma experiência mobile-first dedicada). Reconsiderar se dados de uso mostrarem acesso mobile relevante.
- Acessibilidade básica não é opcional mesmo no MVP: contraste de cor adequado (especialmente nas cores de severidade — vermelho/amarelo/verde não podem ser o único indicador, sempre acompanhadas de texto/ícone para usuários com daltonismo), navegação por teclado funcional nos formulários principais (login, cadastro de firewall). Não é sobre compliance formal (WCAG completo é esforço desproporcional ao estágio), é sobre não excluir usuários por descuido barato de corrigir desde o início.

## 6. Onde esta UX vai precisar evoluir (documentado de propósito)

- A tela de espera do onboarding (seção 2.1) assume ciclo de Cron relativamente rápido para o teste manual — se o produto expandir para dispositivos com conectividade instável (ex: filiais remotas), esse fluxo de "aguardando primeiro check-in" precisa de um estado de timeout mais informativo do que hoje.
- **(Resolvido em 2026-07-08)** Filtros de dashboard, antes mapeados para "v2/v3, não implementado no MVP de firewall único", agora existem desde o v1 (seção 3.8) — a necessidade ainda cresce com o volume (cenário MSP, Priya, com centenas de firewalls), mas a base já está no lançamento, não é mais uma lacuna conhecida.
- **(Resolvido em 2026-07-08)** A aba "Regras & VPN" antes era somente leitura, com escrita prevista só para "quando o tier Premium (v5) chegar". Isso já está especificado (seção 3.4, 2.4) — a decisão de onde os controles de edição entram foi tomada (inline na mesma aba, não uma aba separada), não fica mais pendente.
- **Novo (2026-07-08):** busca textual (não só filtro por categoria) na lista de firewalls/achados ainda não foi especificada — útil quando o número de firewalls crescer muito (cenário MSP com dezenas/centenas de clientes); os filtros combináveis da seção 3.8 cobrem o caso mais comum agora, busca por nome/texto livre é o próximo incremento natural quando o volume justificar.
- **Novo (2026-07-08):** a tela de "Histórico de Alterações" (seção 3.4) especifica um diff "antes/depois" simples — para regras de firewall complexas com muitos campos, um diff visual mais sofisticado (lado a lado, campos alterados destacados) pode ser necessário; a versão simples é suficiente para o volume de mudança esperado no lançamento, não antecipar complexidade de UI que ainda não tem um caso de uso real que a justifique.