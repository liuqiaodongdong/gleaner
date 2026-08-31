# acq/cli_support.py — Gleaner CLI 共用：ROOT / 凭据 / 子进程日志 / 批次摘要
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

# 默认使用当前代码所在仓库，确保解压到其它电脑/目录后仍可直接运行。
DEFAULT_ROOT = Path(__file__).resolve().parent.parent

_ENV_KEYS = (
    "CJY_USER", "CJY_PASS", "CJY_SOFTID",
    "ACQ_PROXY", "ACQ_HEADLESS", "ACQ_BROWSER_CHANNEL",
    "ELSEVIER_API_KEY",
)


def resolve_root(cli_root: str | None = None) -> Path:
    if cli_root and str(cli_root).strip():
        return Path(cli_root).expanduser().resolve()
    env = (os.environ.get("GLEANER_ROOT") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_ROOT.resolve()


def _parse_dotenv(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k:
            out[k] = v
    return out


def load_credentials(root: Path) -> dict[str, str]:
    """从 .env 与遗留 .mcp.json 收集凭据；.env 优先，mcp.json 仅 setdefault 补缺。

    不读密钥文件内容到日志。
    """
    creds: dict[str, str] = {}
    dotenv = root / ".env"
    if dotenv.is_file():
        creds.update(_parse_dotenv(dotenv.read_text(encoding="utf-8")))
    mcp_path = root / ".mcp.json"
    if mcp_path.is_file():
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8"))
            env = (
                data.get("mcpServers", {})
                .get("gleaner", {})
                .get("env")
                or {}
            )
            if isinstance(env, dict):
                for k, v in env.items():
                    if v is not None and str(v) != "":
                        # .env 已有的键不被 mcp.json 覆盖
                        creds.setdefault(str(k), str(v))
        except Exception:
            pass
    # 只返回白名单键 + 其它 ACQ_/CJY_/ELSEVIER_ 前缀
    filtered: dict[str, str] = {}
    for k, v in creds.items():
        if k in _ENV_KEYS or k.startswith(("ACQ_", "CJY_", "ELSEVIER_")):
            filtered[k] = v
    return filtered


def apply_credentials(creds: dict[str, str]) -> None:
    for k, v in creds.items():
        if v and not (os.environ.get(k) or "").strip():
            os.environ[k] = v


def run_logged(
    cmd: list[str],
    *,
    cwd: Path,
    log_path: Path,
    env: dict | None = None,
    timeout: float | None = None,
) -> int:
    """运行子进程，stdout/stderr 行级写入 log 并 print。默认 timeout=None（无硬杀）。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    merged = dict(os.environ)
    if env:
        merged.update(env)
    with log_path.open("w", encoding="utf-8", errors="replace") as logf:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=merged,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            logf.write(line)
            logf.flush()
        return int(proc.wait(timeout=timeout))


def summarize_batch(out_dir: Path, *, file_glob: str = "*.pdf") -> dict:
    out_dir = Path(out_dir)
    meta = out_dir / "metadata.csv"
    titles: list[str] = []
    if meta.is_file():
        with meta.open(encoding="utf-8-sig", newline="") as f:
            titles = [r.get("title", "") for r in csv.DictReader(f) if r.get("title")]
    pdir = out_dir / "papers"
    n = 0
    if pdir.is_dir():
        n = len(list(pdir.glob(file_glob)))
    return {
        "local_dir": str(out_dir),
        "metadata_csv": str(meta),
        "metadata_rows": len(titles),
        "downloaded_files": n,
        "titles": titles,
    }


def resolve_tiered_expression(
    root: Path,
    level: str,
    search_md: str = "",
    topic: str = "",
    range_label: str = "",
) -> tuple[str, str, str]:
    """从 search.md 解析 L1–L4 表达式。返回 (expression, search_md_path, level)。

    逻辑移植自 acq_mcp._resolve_tiered_expression，root 显式传入，不依赖 PROJECT_ROOT。
    """
    from acq.sources.cnki_query import (
        VALID_LEVELS,
        extract_level_expression,
        validate_tiered_expression,
    )

    level_u = (level or "").strip().upper()
    if level_u not in VALID_LEVELS:
        raise ValueError(f"level 须为 {', '.join(VALID_LEVELS)} 之一，收到: {level!r}")

    path: Path | None = Path(search_md) if search_md else None
    if path is None or not str(search_md).strip():
        if not topic:
            raise ValueError(
                "分级采集需要 search_md，或同时提供 topic（+ 可选 range_label）"
            )
        base = Path(root) / "keyword_workspace" / topic
        if range_label:
            path = base / range_label / "search.md"
        else:
            candidates = sorted(
                base.glob("*/search.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not candidates:
                raise FileNotFoundError(
                    f"未找到 keyword_workspace/{topic}/*/search.md，请先 cnki_prepare / prepare"
                )
            path = candidates[0]
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"search.md 不存在: {path}（请先 cnki_prepare / prepare）")

    expression = extract_level_expression(path.read_text(encoding="utf-8"), level_u)
    validate_tiered_expression(expression)
    return expression, str(path), level_u
