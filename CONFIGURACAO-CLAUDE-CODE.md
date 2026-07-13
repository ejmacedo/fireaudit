# Configurando o Claude Code para o FireAudit — guia de boas práticas

Este guia é específico para o seu caso: projeto solo, seguindo o `PLANO-DESENVOLVIMENTO.md` fase por fase com critério de pronto, orçamento baixo, sem equipe para revisar código, e você quer produtividade alta sem abrir mão de segurança básica (nunca vazar segredo, nunca aplicar mudança destrutiva sem querer).

Tudo abaixo assume que você vai rodar o Claude Code dentro da pasta `FireAudit-App/`.

---

## 1. CLAUDE.md — o que revisar no seu

Você já tem um `CLAUDE.md` bem denso (13KB) — isso é bom, mas tem um risco: arquivo grande demais é lido por completo em toda sessão nova, o que consome contexto e dinheiro a cada conversa. Duas melhorias práticas:

- **Divida se crescer mais.** O Claude Code suporta `@caminho/para/arquivo.md` dentro do `CLAUDE.md` para importar outros arquivos por referência. Se o seu `CLAUDE.md` continuar crescendo conforme o projeto avança, considere mover seções muito específicas (ex: detalhe fino de schema) para `docs/specs/` (que já existe) e deixar no `CLAUDE.md` só o resumo + link, referenciando com `@docs/specs/fase4-banco-de-dados.md` quando for realmente necessário carregar aquele contexto.
- **Crie um `CLAUDE.local.md`** (ou use `.claude/settings.local.json`, ver seção 2) para anotações pessoais que não fazem sentido versionar — por exemplo, lembretes seus tipo "minha VPS de teste é X.X.X.X" ou preferências de estilo pessoais. Esse arquivo deve entrar no `.gitignore` (adicione `CLAUDE.local.md` lá, ele ainda não está na sua lista atual).
- **Mantenha a hierarquia em mente**: o Claude Code lê `CLAUDE.md` em cascata — de um `~/.claude/CLAUDE.md` (global, todos os projetos) até o `CLAUDE.md` da pasta atual. Se você trabalha em mais projetos pfSense/infra além deste, vale colocar preferências genéricas suas (tom de resposta, como você gosta de revisar diffs, etc.) no `~/.claude/CLAUDE.md` global, e deixar o deste repositório só com o que é específico do FireAudit.
- O aviso que você já colocou no topo ("leia por completo antes de qualquer código", "não reabra decisões sem avisar") é exatamente o tipo de instrução que funciona bem — mantenha.

## 2. Permissions em `.claude/settings.json` — o ponto mais importante para produtividade

Isso é o que evita ficar aprovando cada `Read`/`Bash` manualmente, sem abrir a porta para comandos perigosos. Crie `.claude/settings.json` na raiz do repo (esse arquivo pode e deve ser commitado — ele é o "contrato de permissões do projeto"):

```json
{
  "permissions": {
    "allow": [
      "Read(**)",
      "Edit(backend/**)",
      "Edit(frontend/**)",
      "Edit(agent/**)",
      "Edit(docs/**)",
      "Bash(git status)",
      "Bash(git diff:*)",
      "Bash(git log:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git checkout -b:*)",
      "Bash(pytest:*)",
      "Bash(ruff:*)",
      "Bash(npm test:*)",
      "Bash(npm run lint:*)",
      "Bash(docker compose up:*)",
      "Bash(docker compose logs:*)",
      "Bash(alembic:*)"
    ],
    "deny": [
      "Read(.env)",
      "Read(.env.*)",
      "Read(**/*secret*)",
      "Read(**/*credentials*)",
      "Bash(git push --force:*)",
      "Bash(git push -f:*)",
      "Bash(rm -rf:*)",
      "Bash(curl:*)",
      "Bash(docker compose down -v:*)"
    ]
  }
}
```

Pontos-chave sobre esse modelo:

- **`allow` reduz as interrupções** para as ações repetitivas e seguras do seu fluxo (rodar teste, lint, ver diff, commitar). **`deny` bloqueia de forma absoluta** — mesmo que você peça, mesmo que uma instrução vinda de um arquivo/PR tente induzir isso, essas ações nunca executam sem você mudar o arquivo manualmente.
- Tudo que não está em `allow` nem `deny` cai no modo de pergunta padrão (ele te pergunta na hora). Isso é o comportamento certo para ações de maior impacto — por exemplo, deixe `git push` (sem force) fora do allow, para aprovar manualmente cada push real para o GitHub.
- **Nunca coloque `Bash(*)` genérico no allow.** É tentador para "parar de ser perguntado", mas anula a proteção — um comando malicioso (inclusive vindo de conteúdo externo, tipo texto colado de um erro do Stack Overflow) rodaria sem fricção.
- Existe um modo `--dangerously-skip-permissions` (ou permission mode "bypass") que desliga tudo isso. **Não use isso neste projeto** — ele existe para sandboxes efêmeras/CI isoladas, não para uma máquina com seu `.env` de produção e chave da OCI por perto.
- Segredos: como reforço ao `deny` acima, vale também impedir leitura do `.env` real mesmo que ele tente "ajudar a debugar" — se precisar debugar variável de ambiente, peça para ele ler o `.env.example` (que não tem valor real) e você confirma manualmente os valores.
- Crie também um `.claude/settings.local.json` (esse sim vai para o `.gitignore`) para permissões só suas, específicas da sua máquina (ex: liberar um comando de deploy que só faz sentido no seu ambiente local).

## 3. Hooks — automatizar o que hoje seria manual

Hooks vivem também em `.claude/settings.json` (seção `hooks`). Os mais úteis para o seu fluxo de "fase por fase com critério de pronto":

- **`PostToolUse` em `Edit`/`Write` no backend** → rodar `ruff format` e `ruff check` automaticamente depois de qualquer edição de arquivo Python. Isso garante que o código já sai formatado, sem você (ou o próprio Claude) ter que lembrar de rodar lint manualmente a cada troca.
- **`PostToolUse` em `Edit`/`Write` no frontend** → rodar `npm run lint -- --fix` ou `prettier --write` no arquivo tocado.
- **`PreToolUse` em `Bash(git commit:*)`** → um hook que roda a suíte de testes antes de permitir o commit passar. Isso mecaniza a regra que já está no seu `PLANO-DESENVOLVIMENTO.md` ("rodar a suíte de testes completa antes de avançar") — em vez de depender do Claude lembrar, o hook bloqueia o commit se o teste falhar.
- **`Notification` hook** → como é projeto solo e você provavelmente vai deixar rodando enquanto faz outra coisa, um hook de notificação (som, ou webhook para o seu Telegram/Slack pessoal) quando o Claude termina uma tarefa longa ou quando precisa da sua aprovação evita você ficar checando a tela toda hora.

Exemplo de trecho de hook (formato simplificado, o essencial é o padrão):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{ "type": "command", "command": "bash .claude/hooks/format-on-save.sh" }]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash(git commit:*)",
        "hooks": [{ "type": "command", "command": "bash .claude/hooks/run-tests-before-commit.sh" }]
      }
    ]
  }
}
```

## 4. Slash commands customizados — feitos sob medida para o seu plano de fases

Coloque em `.claude/commands/*.md` (cada arquivo é um comando, o nome do arquivo é o nome do comando). Os mais valiosos para o seu fluxo:

- **`/proxima-fase`** — instrução: "Leia `PLANO-DESENVOLVIMENTO.md`, identifique a última fase marcada como concluída, confirme comigo qual é a próxima, leia a(s) seção(ões) de `docs/specs/` referenciadas por ela, e resuma o que vai ser implementado antes de começar." Isso mecaniza exatamente a regra que você já documentou ("uma fase por vez, sem pular").
- **`/criterio-pronto`** — instrução: "Verifique se a fase atual satisfaz completamente seu critério de pronto documentado no PLANO-DESENVOLVIMENTO.md, rodando os testes e comandos necessários. Reporte item por item, não diga apenas 'está pronto' sem evidência." Use isso antes de cada merge para `main`.
- **`/resumo-fase`** — gera um resumo do que foi feito na fase atual, útil para você colar como descrição de Pull Request.

## 5. Subagentes — quando valem a pena aqui

Subagentes (`.claude/agents/*.md`) rodam em contexto isolado — bons para tarefas que não devem "sujar" o contexto principal da sessão onde você está construindo o produto. Para este projeto, os dois que trariam mais valor:

- **Um agente revisor de segurança**, focado especificamente nas Fases 9-11 (2FA, escrita remota) — que são, pelo seu próprio plano, a parte de maior risco. Antes de cada merge dessas fases, rode esse agente contra o diff para checar os pontos que o `PLANO-DESENVOLVIMENTO.md` já lista como critério de pronto (isolamento de `agent_token`, 2FA obrigatório sem exceção, idempotência via `UNIQUE`, hash-chain). Você já tem acesso ao skill `security-review` (aparece na sua lista de skills disponíveis) — pode invocá-lo diretamente em vez de criar um agente do zero.
- **Um agente executor de testes/QA**, que só roda a suíte e reporta resultado sem poder editar código — útil para separar "quem implementa" de "quem valida", mesmo sendo você o único humano no processo.

Você também já tem o skill `review`, que serve bem para revisão de Pull Request antes de cada merge para `main` — vale usar isso como parte do ritual de fim de fase.

## 6. Git/GitHub — como configurar desde já

- O Claude Code tem consciência nativa de Git: ele lê `git status`/`git diff` no contexto, pode criar commits e branches quando autorizado (respeitando o `allow`/`deny` da seção 2), e sabe interpretar mensagens de erro de `git`.
- **Autentique o `gh` CLI (`gh auth login`) na sua máquina antes de começar.** Com isso configurado, o Claude Code consegue criar Pull Requests diretamente (`gh pr create`) quando você pedir, sem você ter que abrir o navegador toda vez.
- Fluxo recomendado, coerente com o que já está no seu `PROMPT-ABERTURA.md`: uma branch por fase (`fase-0-esqueleto`, `fase-1-schema-migrations`, ...), commits em Conventional Commits, PR para `main` só quando o critério de pronto passar. Peça ao Claude Code para abrir o PR com a descrição gerada pelo `/resumo-fase` (seção 4) — mantém histórico rastreável mesmo sendo você revisando sozinho.
- Configure um **CODEOWNERS** ou simplesmente o hábito de nunca fazer merge direto sem rodar `/criterio-pronto` antes — como não há um segundo humano revisando, esse comando é o seu "par" de revisão.

## 7. MCP servers relevantes para este projeto

MCP servers estendem o que o Claude Code consegue acessar além do sistema de arquivos/bash local. Os que fazem sentido aqui:

- **MCP do GitHub** — permite operações mais ricas que `gh` puro (ex: gerenciar issues vinculadas a cada fase do plano, comentar em PRs).
- **MCP do Postgres** — para consultar o schema/dados reais do banco Docker local durante o desenvolvimento (ex: "verifique se a migration da Fase 1 criou a constraint UNIQUE certa") sem precisar abrir um cliente SQL separado. Cuidado: aponte sempre para o Postgres **local** de desenvolvimento, nunca para produção.
- Evite adicionar MCP servers "por precaução" sem necessidade concreta — cada MCP conectado é superfície de acesso adicional (alguns podem ter escopo de leitura/escrita amplo), e no seu caso o ganho de produtividade de um MCP genérico de propósito duvidoso não compensa o risco. Prefira registrar (`claude mcp add`) só quando uma fase específica do plano justificar.

## 8. Eficiência de contexto e custo

- **Use `/clear` entre fases não relacionadas** (ex: ao terminar a Fase 4 e começar a Fase 5) — isso evita carregar tokens de contexto de trabalho já finalizado, mais barato e mais focado.
- **Use `/compact` em sessões longas** dentro da mesma fase, quando a conversa ficar longa mas você ainda precisa manter alguma continuidade.
- **Delegue exploração/investigação a subagentes** (ex: "investigue por que esse teste está falhando") em vez de fazer isso na conversa principal — o subagente devolve só a conclusão, sem poluir seu contexto principal com todo o processo de busca.
- Evite colar arquivos grandes manualmente no chat quando o Claude Code já tem acesso ao sistema de arquivos — deixe ele ler o arquivo diretamente, é mais barato e mais preciso que você copiar/colar.

## 9. Segurança geral ao dar acesso de bash/edição num projeto real

- Rode o Claude Code dentro do repositório do projeto, não a partir de um diretório mais amplo (`~` ou `/`) — limita o raio de ação por padrão.
- Mantenha `.env` **fora do Git** (já está no seu `.gitignore`) e fora do que o Claude Code pode ler livremente (seção 2, `deny`).
- Revise o diff (`git diff`) antes de cada commit real para produção — mesmo com hooks e permissions bem configurados, uma checada visual sua nos pontos de maior risco (Fases 9-11, principalmente) é a camada final de segurança que nenhuma configuração substitui.
- Se em algum momento você for testar o agente contra um pfSense real (Fase 12 do seu plano), faça isso manualmente fora do fluxo automatizado do Claude Code — nunca dê à ferramenta acesso direto e irrestrito à API key de produção do seu firewall real.

---

### Checklist rápido antes de começar a Fase 0

1. `git init` + criar repo privado no GitHub + `gh auth login`.
2. Criar `.claude/settings.json` com o modelo da seção 2 (ajuste os comandos de `allow` conforme for descobrindo o que usa com frequência).
3. Adicionar `CLAUDE.local.md` e `.claude/settings.local.json` ao `.gitignore`.
4. Criar os hooks de lint/teste da seção 3 (pode começar simples e evoluir).
5. Criar os slash commands `/proxima-fase` e `/criterio-pronto` da seção 4.
6. Colar o conteúdo de `PROMPT-ABERTURA.md` como primeira mensagem.
