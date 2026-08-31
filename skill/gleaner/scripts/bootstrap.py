# skill/gleaner/scripts/bootstrap.py — 只装 Skill 时也要把仓库拉下来
"""无仓库则 git clone + pip，再跑 install-skill。有仓库则只注册 Skill。

用法：
  python bootstrap.py
  python bootstrap.py D:\\path\\gleaner
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/liuqiaodongdong/gleaner.git"


def _cli_in(root: Path) -> Path | None:
    cli = root / "gleaner_cli.py"
    return cli if cli.is_file() else None


def find_existing_cli() -> Path | None:
    env = (os.environ.get("GLEANER_ROOT") or "").strip()
    if env:
        found = _cli_in(Path(env).expanduser())
        if found:
            return found
    marker = Path(__file__).resolve().parent.parent / ".gleaner_root"
    if marker.is_file():
        text = marker.read_text(encoding="utf-8").strip()
        if text:
            found = _cli_in(Path(text).expanduser())
            if found:
                return found
    cwd = Path.cwd()
    found = _cli_in(cwd)
    if found:
        return found
    return _cli_in(cwd / "gleaner")


def default_dest() -> Path:
    override = (os.environ.get("GLEANER_BOOTSTRAP_DEST") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    cwd_g = Path.cwd() / "gleaner"
    if _cli_in(cwd_g):
        return cwd_g.resolve()
    return cwd_g.resolve()


def clone_repo(dest: Path) -> Path:
    dest = dest.expanduser()
    if _cli_in(dest):
        return dest.resolve()
    if dest.exists() and any(dest.iterdir()) and not (dest / ".git").exists():
        dest = dest / "gleaner"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if _cli_in(dest):
        return dest.resolve()
    print(f"[bootstrap] git clone {REPO_URL} -> {dest}", flush=True)
    subprocess.check_call(["git", "clone", REPO_URL, str(dest)])
    cli = _cli_in(dest)
    if not cli:
        raise SystemExit(f"[bootstrap] clone 后仍没有 gleaner_cli.py: {dest}")
    return dest.resolve()


def pip_and_register(root: Path) -> None:
    req = root / "requirements.txt"
    if req.is_file():
        print(f"[bootstrap] pip install -r {req}", flush=True)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(req)]
        )
    cli = root / "gleaner_cli.py"
    print("[bootstrap] python gleaner_cli.py install-skill", flush=True)
    subprocess.check_call([sys.executable, str(cli), "install-skill"])
    print(f"[bootstrap] 完成。请设置 GLEANER_ROOT={root}", flush=True)
    print("[bootstrap] 然后：python gleaner_cli.py status", flush=True)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    existing = find_existing_cli()
    if existing and not argv:
        root = existing.parent.resolve()
        print(f"[bootstrap] 已有仓库 {root}，只注册 Skill", flush=True)
        pip_and_register(root)
        return 0
    dest = Path(argv[0]).expanduser() if argv else default_dest()
    if existing and dest.resolve() == existing.parent.resolve():
        pip_and_register(existing.parent.resolve())
        return 0
    root = clone_repo(dest)
    pip_and_register(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
