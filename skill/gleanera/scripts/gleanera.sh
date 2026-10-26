#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

find_root() {
  if [[ -n "${GLEANERA_ROOT:-}" ]]; then
    printf '%s\n' "$GLEANERA_ROOT"
    return 0
  fi
  if [[ -f "$SKILL_DIR/.gleanera_root" ]]; then
    local pointed
    pointed="$(tr -d '\r\n' < "$SKILL_DIR/.gleanera_root")"
    if [[ -n "$pointed" && -f "$pointed/gleanera_cli.py" ]]; then
      printf '%s\n' "$pointed"
      return 0
    fi
  fi
  if [[ -f "$SKILL_DIR/../../../gleanera_cli.py" ]]; then
    (cd "$SKILL_DIR/../../.." && pwd)
    return 0
  fi
  echo "未找到 gleaner 仓库。请先 git clone --branch feature/cnki-institution-session --single-branch https://github.com/liuqiaodongdong/gleaner.git gleanera 后执行 python gleanera_cli.py install-skill，或设置 GLEANERA_ROOT。" >&2
  return 1
}

ROOT="$(find_root)"
cd "$ROOT"
PY="${GLEANERA_PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  PY=python
fi
exec "$PY" "$ROOT/gleanera_cli.py" "$@"
