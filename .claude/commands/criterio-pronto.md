Verifique se a fase atual do projeto satisfaz completamente o seu critério de "pronto", conforme documentado em `PLANO-DESENVOLVIMENTO.md`.

1. Identifique qual fase está em andamento (pergunte ao usuário se não estiver claro pelo contexto da conversa).
2. Releia o critério de "pronto" exato dessa fase no `PLANO-DESENVOLVIMENTO.md`.
3. Rode de fato os comandos/testes necessários para verificar cada item do critério — não é suficiente ler o código e assumir que funciona; execute e mostre a evidência (saída de teste, resultado de query, resposta de endpoint, etc.).
4. Reporte item por item do critério: o que passou, o que falhou, o que não foi possível verificar e por quê.
5. Se algum item falhar, não diga que a fase está pronta. Liste exatamente o que falta corrigir antes de permitir merge para `main`.

Use este comando antes de qualquer merge para `main` — ele substitui a revisão de um segundo humano, já que este é um projeto solo.
