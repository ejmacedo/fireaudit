# Prompt de abertura — colar no Fable / Claude Code

Copie o texto abaixo (a partir de "Você vai construir...") como primeira mensagem na ferramenta que for codificar este projeto.

---

Você vai construir o FireAudit, um SaaS de auditoria e compliance de firewalls pfSense. Este repositório já contém a especificação completa do produto — não é um MVP incremental, é o produto completo desde o v1 (inclui escrita remota de regra, 2FA step-up, criador de alertas customizados e filtros de dashboard).

**Antes de escrever qualquer código:**

1. Leia `CLAUDE.md` na raiz — é o resumo executivo: stack fechada, modelo de dados, regras de negócio não-negociáveis, padrões de arquitetura e a lista explícita do que NÃO implementar sem me confirmar antes (RBAC multiusuário, OPNsense, staging dedicado, testes de carga, particionamento).
2. Leia `PLANO-DESENVOLVIMENTO.md` na raiz — é o plano de execução em 14 fases (Fase 0 a Fase 13), cada uma com um "critério de pronto" verificável. **Regra fixa: siga a ordem exata do plano, uma fase por vez, e não avance para a próxima sem o critério de pronto da fase atual estar satisfeito.** Se alguma fase revelar que uma decisão anterior estava errada, pare e me avise em vez de corrigir silenciosamente.
3. Cada fase do plano referencia o documento correspondente em `docs/specs/` (as 12 fases de especificação completas, mais o mockup HTML). Leia o trecho relevante da spec antes de implementar aquela fase — não confie só no resumo do plano.

**Sobre uso do Git/GitHub, já que este repositório ainda não tem controle de versão iniciado:**

- Inicialize o repositório Git local e crie um repositório no GitHub (privado — este código terá segredos de arquitetura de um produto comercial ainda não lançado).
- Estratégia de branch: trunk-based simples — `main` sempre estável e implantável, uma branch por fase do plano (ex: `fase-0-esqueleto`, `fase-1-schema-migrations`), merge para `main` só quando o critério de pronto daquela fase passar.
- Commits seguindo Conventional Commits (`feat:`, `fix:`, `chore:`, `test:`, `docs:`) — isso facilita gerar changelog depois e entender o histórico numa base solo.
- Nunca commitar `.env` nem qualquer segredo em texto plano — o `.gitignore` já está configurado para isso, mas confirme antes de cada commit que nenhuma credencial (API key do pfSense, secrets de JWT/HMAC, senha do Postgres) foi incluída.
- Ao final de cada fase, antes de abrir o merge para `main`: rodar a suíte de testes completa (não é opcional — não há ambiente de staging neste projeto, então os testes automatizados são a única rede de segurança antes de produção, conforme `docs/specs/fase9-10-performance-infra.md`).
- CI/CD via GitHub Actions (pipeline: lint → testes → build de imagem Docker → push para GitHub Container Registry → deploy via SSH na VPS) — configure isso a partir da Fase 0, mesmo que o deploy real só aconteça depois; não precisa estar 100% funcional cedo, mas a estrutura do workflow deve existir.

**Convenções de código a manter (detalhado em `CLAUDE.md`):** Clean Architecture leve com pastas `domain/application/infrastructure/api/workers`; Strategy Pattern para as 6 checagens do motor de análise; Command Pattern para os comandos remotos de firewall; shadcn/ui + lucide-react no frontend, sem CSS solto reinventando componentes.

**Se qualquer instrução deste prompt conflitar com o que está em `docs/specs/`, o conteúdo de `docs/specs/` é a fonte da verdade** — este prompt é só o guia de abertura, não substitui a especificação.

Comece pela Fase 0 do `PLANO-DESENVOLVIMENTO.md`.
