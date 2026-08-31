#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

find_root() {
  if [[ -n "${GLEANER_ROOT:-}" ]]; then
    printf '%s\n' "$GLEANER_ROOT"
    return 0
  fi
  if [[ -f "$SKILL_DIR/.gleaner_root" ]]; then
    local pointed
    pointed="$(tr -d '\r\n' < "$SKILL_DIR/.gleaner_root")"
    if [[ -n "$pointed" && -f "$pointed/gleaner_cli.py" ]]; then
      printf '%s\n' "$pointed"
      return 0
    fi
  fi
  if [[ -f "$SKILL_DIR/../../../gleaner_cli.py" ]]; then
    (cd "$SKILL_DIR/../../.." && pwd)
    return 0
  fi
  echo "未找到 gleaner 仓库。请先 git clone https://github.com/liuqiaodongdong/gleaner.git 后执行 python gleaner_cli.py install-skill，或设置 GLEANER_ROOT。" >&2
  return 1
}

ROOT="$(find_root)"
cd "$ROOT"
PY="${GLEANER_PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  PY=python
fi
exec "$PY" "$ROOT/gleaner_cli.py" "$@"
