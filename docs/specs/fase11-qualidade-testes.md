# Fase 11 — Estratégia de Qualidade e Testes
## Produto: FireAudit — v1 (produto completo, inclui escrita remota — ver nota abaixo)

Restrição que guia esta fase: uma pessoa, 10-20h/semana, sem QA dedicado. A estratégia de testes precisa maximizar confiança por hora investida — não é sobre atingir uma métrica de cobertura, é sobre testar primeiro o que quebra silenciosamente e mais caro de debugar depois.

**Atualização de 2026-07-08 — escopo do v1 passou a incluir escrita remota:** a versão original desta fase tratava a mudança de categoria de teste que a escrita remota exigiria como algo "quando o tier Premium (v5) chegar" (seção 7). Isso deixou de ser futuro — as seções 1 e 3 foram atualizadas com os novos componentes de risco alto (fila de comandos, hash-chain de auditoria, isolamento de escopo de token) e os casos de teste críticos correspondentes.

---

## 1. Onde o risco de bug é mais caro — prioridade de teste

| Componente | Por que é prioridade alta |
|---|---|
| Motor de análise (6 estratégias de checagem, Fase 3) | É o produto. Um falso positivo destrói confiança (Fase 1, seção 2.3); um falso negativo é pior — cliente acredita estar seguro quando não está. |
| Endpoint de ingestão + validação HMAC (Fase 5, Fase 8) | Se aceitar payload adulterado ou rejeitar payload legítimo por bug de assinatura, o cliente perde visibilidade sem saber. |
| Isolamento multi-tenant (toda query filtrada por `organization_id`, Fase 5 seção 2) | Um bug aqui é o pior cenário possível do produto: cliente A vendo dado do cliente B. |
| Lógica de billing/tier (Fase 8, seção 5 e regras de negócio da Fase 2) | Cobrar errado ou liberar acesso Pro para conta Free tem impacto financeiro e de confiança direto. |
| Fila de processamento (Postgres job table, Fase 3) | Job perdido ou processado duas vezes gera achado ausente ou duplicado. |
| **Fila de comandos remotos (`firewall_commands`) — novo, 2026-07-08** | **Maior prioridade de teste do documento desde esta atualização.** Diferente de todos os itens acima (onde o pior caso é vazamento/inconsistência de dado), um bug aqui pode alterar de fato a configuração de segurança do firewall do cliente. Cobre especificamente: comando só é entregue ao agente depois de `status = confirmed`; comando expirado (`expires_at` passado) nunca é entregue mesmo que ainda esteja `pending_confirmation`; um comando nunca é aplicado duas vezes (idempotência, Fase 8 seção 7). |
| **Separação de escopo `agent_token` — novo, 2026-07-08** | O `agent_token` de ingestão nunca deve conseguir criar ou confirmar um `firewall_command` (Fase 5, seção 2) — só ler comandos já confirmados via polling. Um teste que provasse o contrário seria uma falha de segurança crítica, não um bug funcional comum. |
| **Hash-chain de `remote_change_logs` — novo, 2026-07-08** | Se a cadeia de hash puder ser recalculada/adulterada sem detecção, a auditoria de escrita remota (RNF05, Fase 2) não cumpre sua função — testar que alterar um registro histórico quebra a verificação da cadeia a partir daquele ponto. |

Componentes de risco mais baixo (UI de configurações simples, textos estáticos) recebem cobertura de teste proporcionalmente menor — não é negligência, é alocação de esforço coerente com o tempo disponível.

## 2. Pirâmide de testes adotada (proporção deliberada)

```
        /\
       /  \      E2E (poucos, críticos)
      /----\
     /      \    Integração (moderado)
    /--------\
   /          \  Unitários (a maioria)
  /____________\
```

- **Unitários — a maioria do esforço:** cada uma das 6 estratégias do motor de análise (`AnalysisCheck.run()`, Fase 3) testada isoladamente com snapshots de entrada sintéticos cobrindo caso positivo, caso negativo, e casos de borda (ex: certificado expirando exatamente no limiar de dias de alerta, regra "any-any" disfarçada por alias, `duplicate_rule` com regras que diferem só em campo irrelevante como comentário/nome mas têm a mesma tupla efetiva). Como o domínio não depende de infraestrutura (Clean Architecture, Fase 3), esses testes rodam em milissegundos sem precisar de banco — o principal retorno prático da decisão de arquitetura da Fase 3 aparece exatamente aqui.
- **Integração — moderado:** testar o fluxo real contra um Postgres de teste (container efêmero): ingestão → fila → processamento → achados salvos; e a camada de repositório (queries com filtro de `organization_id`) para garantir isolamento multi-tenant com dados reais de duas organizações diferentes no mesmo teste. **Novo (2026-07-08):** o fluxo completo de comando remoto (criação → confirmação com 2FA → polling do agente simulado → resultado → gravação em `remote_change_logs`) também entra aqui, por envolver múltiplas tabelas e transições de estado reais.
- **E2E — poucos, só os críticos:** fluxo de cadastro→primeiro firewall→primeiro snapshot→dashboard populado (o "caminho de ativação", Fase 6-7 seção 2.1); fluxo de upgrade Free→Pro via Stripe (usando o modo de teste do Stripe); **novo (2026-07-08)** fluxo completo de edição remota (criar regra → preview → confirmar com 2FA → simular polling do agente → verificar `remote_change_logs` gravado) — este último entra na lista de poucos E2E críticos por ser a funcionalidade de maior risco do produto (seção 1), não por capricho de cobertura. Poucos porque são caros de escrever/manter — só os que, se quebrarem, tiram o produto do ar para o usuário de forma direta.

## 3. Casos de teste específicos que não podem faltar (derivados de decisões já tomadas nas fases anteriores)

- Assinatura HMAC inválida → snapshot rejeitado com `422`, nunca processado (Fase 5/8).
- Token de agente revogado → ingestão rejeitada com `401`, mesmo com payload e assinatura corretos.
- Usuário do tier Free tentando acessar `GET /v1/firewalls/{id}/rules` → `403 UPGRADE_REQUIRED`, nunca os dados nem um `404` (Fase 8, seção 3).
- Query de listagem de firewalls de uma organização nunca retorna firewall de outra organização, mesmo com manipulação de parâmetros na request.
- Achado gerado por uma checagem específica não deve duplicar entre snapshots consecutivos sem mudança real na configuração (evita "achado infinito" enchendo a tela e a caixa de entrada de alertas do cliente).
- Job de snapshot que falha no meio do processamento (ex: erro inesperado numa das 6 estratégias) não trava a fila para os próximos jobs — outro snapshot deve continuar sendo processado normalmente.
- Webhook de teste (Fase 6-7, seção 3.5) reporta corretamente o código HTTP retornado pelo endpoint do cliente, incluindo timeout e erro de DNS.
- **(Novo, 2026-07-08) `agent_token` não pode criar nem confirmar `firewall_command`** — só JWT de usuário autenticado com tier Premium e 2FA habilitado pode; tentar criar/confirmar com `agent_token` deve ser rejeitado com `401`/`403`, nunca aceito silenciosamente.
- **(Novo, 2026-07-08) Confirmação de comando sem código 2FA válido é sempre rejeitada** — mesmo com JWT de sessão válido e o comando existente em `pending_confirmation`, `POST .../confirm` sem `totp_code` correto retorna erro e o `status` do comando permanece inalterado.
- **(Novo, 2026-07-08) Comando expirado nunca é entregue ao agente** — um `firewall_command` com `expires_at` no passado não aparece em `GET /v1/firewalls/{id}/commands/pending`, mesmo que seu `status` ainda não tenha sido atualizado para `expired` pelo job de limpeza (a checagem de expiração é feita na query de leitura, não só no job periódico — defesa em profundidade contra atraso do job).
- **(Novo, 2026-07-08) Um comando não pode ser aplicado duas vezes** — simular dois `POST .../result` para o mesmo `command