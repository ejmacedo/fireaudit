#!/usr/bin/env bash
# Roda a suite de testes antes de permitir um commit real.
# Regra do PLANO-DESENVOLVIMENTO.md: "rode a suíte de testes completa antes
# de avançar de fase" — este hook mecaniza essa regra no momento do commit.
#
# Tolerante nas fases iniciais: se ainda não existir suite de teste
# configurada (Fase 0-1), não bloqueia — passa a bloquear de fato a partir
# do momento em que pytest/npm test estiverem configurados no projeto.

set -uo pipefail

FAILED=0

if [ -f backend/pytest.ini ] || [ -f backend/pyproject.toml ]; then
  echo "[hook] Rodando pytest (backend)..."
  (cd backend && pytest -q) || FAILED=1
fi

if [ -f frontend/package.json ] && grep -q '"test"' frontend/package.json 2>/dev/null; then
  echo "[hook] Rodando npm test (frontend)..."
  (cd frontend && npm test -- --run) || FAILED=1
fi

if [ "$FAILED" -eq 1 ]; then
  echo "[hook] Testes falharam — commit bloqueado. Corrija antes de comitar." >&2
  exit 2
fi

exit 0
