#!/usr/bin/env bash
# Formata automaticamente o arquivo que acabou de ser editado/criado.
# Silencioso e tolerante a falha: se a ferramenta (ruff/prettier) ainda não
# estiver instalada nesta fase do projeto, não bloqueia o fluxo.

set -uo pipefail

FILE_PATH="${CLAUDE_TOOL_INPUT_FILE_PATH:-}"
[ -z "$FILE_PATH" ] && exit 0
[ -f "$FILE_PATH" ] || exit 0

case "$FILE_PATH" in
  backend/*.py)
    if command -v ruff >/dev/null 2>&1; then
      ruff format "$FILE_PATH" >/dev/null 2>&1
      ruff check --fix "$FILE_PATH" >/dev/null 2>&1
    fi
    ;;
  frontend/*.ts|frontend/*.tsx|frontend/*.js|frontend/*.jsx)
    if [ -f frontend/node_modules/.bin/prettier ]; then
      frontend/node_modules/.bin/prettier --write "$FILE_PATH" >/dev/null 2>&1
    fi
    ;;
esac

exit 0
