# gleanera_cli.py — Gleanera 校外机构版 CLI（install-skill / status / sources / score / login-hint / prepare / cnki-list / cnki）
"""用法: python gleanera_cli.py <command> [options]

全局: --root PATH  --json  --timeout SEC
子命令: install-skill | status | sources | score | login-hint | prepare | cnki-list | cnki
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from pathlib import Path
from typing import Any

from acq.cli_support import (
    apply_credentials,
    install_user_skill,
    load_credentials,
    resolve_root,
    resolve_tiered_expression,
    run_logged,
    summarize_batch,
)

CNKI_BATCH_NUM_MIN = 40
CNKI_BATCH_NUM_MAX = 60


def _cnki_file_count(out_dir: Path) -> int:
    pdf = summarize_batch(out_dir, file_glob="*.pdf")["downloaded_files"]
    caj = summarize_batch(out_dir, file_glob="*.caj")["downloaded_files"]
    return int(pdf) + int(caj)




def _print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _resolve_concept_groups(raw: str) -> str:
    """--concept-groups 为 JSON 字符串；若以 @ 开头则读文件内容。"""
    if raw.startswith("@"):
        path = Path(raw[1:]).expanduser()
        return path.read_text(encoding="utf-8")
    return raw


def _batch_slug(name: str, max_len: int = 24) -> str:
    return re.sub(r"\W+", "_", name or "")[:max_len].strip("_") or "cnki"


def _try_merge_corpus(root: Path) -> str:
    """跨源归一 merged_metadata.csv；失败不阻断。"""
    try:
        from acq.normalize_corpus import merge_corpus

        return str(merge_corpus(root / "corpus"))
    except Exception as exc:
        return f"merge_skipped: {exc}"


def cmd_install_skill(root: Path) -> int:
    try:
        payload = install_user_skill(root)
    except FileNotFoundError as exc:
        _print_json(
            {
                "ok": False,
                "error": "skill_source_missing",
                "message": str(exc),
            }
        )
        return 1
    _print_json(payload)
    return 0


def cmd_status(_root: Path) -> int:
    from acq.setup_check import check_setup
    from acq.cnki_session import resolve_session_mode
    payload = check_setup()
    try:
        mode = resolve_session_mode(_root)
        payload["session_mode"] = mode
        if mode == "institution" and "cnki" in payload.get("lines", {}):
            payload["lines"]["cnki"]["cookies"]["hint"] = "机构会话：下载期间不自动重录或覆盖；失效时主动运行 python login.py --institution"
    except ValueError as exc:
        payload.update(ok=False, session_mode="institution", session_error=str(exc))
        cnki = payload.get("lines", {}).get("cnki", {})
        for key in ("ready", "cnki_collect_ready", "cnki_list_ready", "cnki_ready"):
            cnki[key] = False
        cnki.get("cookies", {}).update(ok=False, status="session_invalid", hint=str(exc))
        payload.setdefault("blockers", []).append({"id": "institution_session", "severity": "cnki",
                                                   "title": "机构会话不可用", "action": "主动运行 python login.py --institution"})
        payload.setdefault("next_steps_for_user", []).append(str(exc))
        payload["ready_any_line"] = False
        payload["ready_all_core"] = False
    _print_json(payload)
    return 0


def cmd_sources(root: Path) -> int:
    """列出当前保留的采集源和配置状态。"""
    from acq.setup_check import check_setup

    setup = check_setup()

    L = setup["lines"]
    payload = {
        "setup_ok": setup["ok"],
        "next_steps_for_user": setup["next_steps_for_user"],
        "sources": [
            {
                "name": "cnki",
                "type": "paper",
                "status": "ready" if L["cnki"]["cnki_collect_ready"] else "needs_setup",
                "modes": ["keyword", "pro", "tiered L1-L4 (prepare→LY刊滤)"],
                "access": "默认直连；代理可选，全文依赖有效机构权限",
                "tool": "cnki / cnki-list / prepare",
                "ready": L["cnki"]["cnki_collect_ready"],
                "note": (
                    "分级：Agent 拓展概念组→prepare→level=L1..L4；"
                    "白名单 acq/data/cnki_journal_tiers.json"
                ),
            },
        ],
    }
    _print_json(payload)
    return 0


def cmd_score(_root: Path) -> int:
    from captcha import chaojiying_score

    result = chaojiying_score()
    print(result)
    try:
        payload = json.loads(result)
        return 0 if isinstance(payload, dict) and payload.get("err_no") == 0 else 1
    except (ValueError, TypeError):
        return 1


def cmd_login_hint(_root: Path) -> int:
    print("Gleanera 用于校外学校机构登录。运行 python login.py，在可见浏览器选择学校并完成认证。")
    print("Windows 默认 msedge；超级鹰仅为采集验证码的可选服务。")
    print("脚本确认机构身份后保存会话；不需要冷启动开关。网络默认直连，ACQ_PROXY 可选。")
    print("采集期间保持会话文件不变；失效后主动重新运行 python login.py，不自动刷新。")
    return 0


def cmd_prepare(root: Path, args: argparse.Namespace) -> int:
    from acq.sources.cnki_query import prepare_search

    try:
        concept_groups = _resolve_concept_groups(args.concept_groups)
        result = prepare_search(
            topic=args.topic,
            concept_groups=concept_groups,
            workspace_root=root,
            year_from=args.year_from,
            year_to=args.year_to or "",
            range_label=args.range_label or "",
            max_keywords=int(args.max_keywords),
            num=int(args.num),
        )
        result["ok"] = True
        _print_json(result)
        return 0
    except Exception as exc:
        _print_json(
            {
                "ok": False,
                "error": str(exc),
                "hint": "concept_groups 须为 JSON 数组或含「中文:」的 keywords.md；@path 读文件",
            }
        )
        return 1


def _cmd_cnki_dispatch(
    root: Path,
    args: argparse.Namespace,
    *,
    command: str,
    script: str,
    params_filename: str,
) -> int:
    """cnki-list / cnki 共用：preflight → 解析检索式 → 写 params → run_logged → 摘要 JSON。"""
    from acq.setup_check import preflight
    from acq.cnki_session import resolve_session_mode

    try:
        session_mode = resolve_session_mode(root, getattr(args, "session_mode", "auto"))
    except ValueError as exc:
        _print_json({"ok": False, "error": "institution_session_invalid", "message": str(exc),
                     "next_action": "python login.py --institution"})
        return 1

    # 浏览器启动前先做就绪检查
    line = "cnki-list" if command == "cnki-list" else "cnki"
    bad = preflight(line)
    if bad:
        _print_json(bad)
        return 1

    level = (getattr(args, "level", None) or "").strip()
    query = (getattr(args, "query", None) or "").strip()
    search_md = (getattr(args, "search_md", None) or "").strip()
    topic = (getattr(args, "topic", None) or "").strip()
    range_label = (getattr(args, "range_label", None) or "").strip()
    out_name = (getattr(args, "out_name", None) or "").strip()
    pro = bool(getattr(args, "pro", False))
    explicit_num = int(getattr(args, "num", 0) or 0)
    details = command == "cnki-list" and bool(getattr(args, "details", False))
    if command == "cnki-list" and explicit_num <= 0:
        _print_json({"ok": False, "error": "--num 必须大于 0", "command": command})
        return 1
    until = max(0, int(getattr(args, "until", 0) or 0)) if command == "cnki" else 0
    num = explicit_num
    num_randomized = False
    if command == "cnki" and explicit_num <= 0 and until <= 0:
        num = random.randint(CNKI_BATCH_NUM_MIN, CNKI_BATCH_NUM_MAX)
        num_randomized = True
        print(
            f"[gleaner] 本批全文篇数随机为 {num}（{CNKI_BATCH_NUM_MIN}–{CNKI_BATCH_NUM_MAX}）",
            file=sys.stderr,
        )

    extra: dict[str, Any] = {}
    try:
        if level:
            expression, smd, level_u = resolve_tiered_expression(
                root,
                level,
                search_md=search_md,
                topic=topic or query,
                range_label=range_label,
            )
            slug = _batch_slug(topic or query or "cnki")
            batch = out_name or f"{slug}_{level_u}"
            params_query = expression
            pro = True
            extra = {
                "mode": "tiered",
                "level": level_u,
                "search_md": smd,
                "expression_preview": (
                    expression[:240] + ("…" if len(expression) > 240 else "")
                ),
            }
        else:
            if not query:
                raise ValueError(
                    "非分级模式需要 --query；分级模式请传 --level + --search-md/--topic"
                )
            batch = out_name or ("batch_" + _batch_slug(query, 20))
            params_query = query
            extra = {"mode": "pro" if pro else "keyword"}
    except Exception as exc:
        _print_json({"ok": False, "error": str(exc), "command": command})
        return 1

    corpus = root / "corpus"
    if details and not out_name:
        batch += "_metadata"
    corpus.mkdir(parents=True, exist_ok=True)
    out_dir = corpus / batch
    params: dict[str, Any] = {"num": num, "out": str(out_dir)}
    if command == "cnki-list":
        params["details"] = details
        from run_list import FIELDS, DETAIL_FIELDS, check_output_schema
        fields = DETAIL_FIELDS if details else FIELDS
        try:
            check_output_schema(out_dir, fields)
        except ValueError as exc:
            _print_json({"ok": False, "error": str(exc), "command": command})
            return 1
        extra["details"] = details
        extra["fields"] = fields
    if pro:
        params.update(pro=True, expression=params_query)
    else:
        params["keyword"] = params_query

    pfile = corpus / params_filename
    os.environ.setdefault("ACQ_HEADLESS", "1")
    os.environ.setdefault("ACQ_BROWSER_CHANNEL", "msedge")
    log_path = corpus / f"{batch}_run.log"
    timeout = getattr(args, "timeout", None)
    cmd = [sys.executable, str(root / script), str(pfile)]

    def _write_params(n: int) -> None:
        params["num"] = n
        pfile.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")

    def _run_once(n: int, *, append_log: bool) -> int:
        _write_params(n)
        return run_logged(
            cmd,
            cwd=root,
            log_path=log_path,
            env={"ACQ_SESSION_MODE": session_mode},
            timeout=timeout,
            append=append_log,
        )

    serial_batches: list[int] = []
    login_between = 0
    if command == "cnki" and until > 0:
        # 无新增会停；上限按「每批至少 1 篇」估，避免小 --num 被 40 篇公式提前截断
        max_rounds = until + 4
        exit_code = 0
        for i in range(max_rounds):
            have = _cnki_file_count(out_dir)
            if have >= until:
                print(f"[gleaner] 已有 {have} 篇 ≥ 目标 {until}，串行结束", file=sys.stderr)
                break
            if explicit_num > 0:
                n = explicit_num
            else:
                n = random.randint(CNKI_BATCH_NUM_MIN, CNKI_BATCH_NUM_MAX)
                num_randomized = True
            n = max(1, min(n, until - have))
            serial_batches.append(n)
            num = n
            print(
                f"[gleaner] 串行第 {i + 1} 批 num={n} 已有={have} 目标={until}",
                file=sys.stderr,
            )
            exit_code = _run_once(n, append_log=(i > 0))
            after = _cnki_file_count(out_dir)
            if after <= have:
                print("[gleaner] 本批没有新增全文，停止串行（避免空转）", file=sys.stderr)
                break
            if exit_code != 0:
                print(f"[gleaner] 本批退出码 {exit_code}，停止串行", file=sys.stderr)
                break
        extra["until"] = until
        extra["serial_batches"] = serial_batches
        extra["login_between"] = login_between
    else:
        _write_params(num)
        exit_code = _run_once(num, append_log=False)

    summary = summarize_batch(out_dir, file_glob="*.pdf")
    # 全文线可能还有 .caj
    if command == "cnki":
        caj = summarize_batch(out_dir, file_glob="*.caj")
        summary["downloaded_files"] = summary["downloaded_files"] + caj["downloaded_files"]

    downloaded = int(summary.get("downloaded_files") or 0)
    extra["session_mode"] = session_mode
    until_reached = until <= 0 or downloaded >= until
    if until > 0:
        extra["until_reached"] = until_reached
        if not until_reached:
            if session_mode == "institution":
                extra["next_action"] = "核对下载日志；如机构会话失效，请主动运行 python login.py --institution"
            print(
                f"[gleaner] 未达目标：已有 {downloaded} < {until}",
                file=sys.stderr,
            )
    ok = exit_code == 0 and until_reached
    result: dict[str, Any] = {
        "ok": ok,
        "exit_code": exit_code,
        "command": command,
        "query": params_query if not level else "",
        "log_path": str(log_path),
        "params_file": str(pfile),
        "merged_metadata": (
            _try_merge_corpus(root) if exit_code == 0 else None
        ),
        **summary,
        **extra,
        "num": num,
        "num_randomized": num_randomized,
    }
    if level:
        result["query"] = params_query  # 分级也带回完整式，便于排查
    _print_json(result)
    return 0 if ok else 1


def cmd_cnki_list(root: Path, args: argparse.Namespace) -> int:
    return _cmd_cnki_dispatch(
        root,
        args,
        command="cnki-list",
        script="run_list.py",
        params_filename="_cli_cnki_list_params.json",
    )


def cmd_cnki(root: Path, args: argparse.Namespace) -> int:
    return _cmd_cnki_dispatch(
        root,
        args,
        command="cnki",
        script="run_batch.py",
        params_filename="_cli_cnki_params.json",
    )


def _add_cnki_args(
    p: argparse.ArgumentParser, *, default_num: int, fulltext: bool = False
) -> None:
    p.add_argument("--session-mode", choices=["auto", "institution"], default="institution",
                   help="默认 institution；auto 兼容为机构模式。采集期间不自动重录或覆盖 cookies")
    p.add_argument("--level", default="", help="分级 L1–L4；非空则走分级专业式")
    p.add_argument("--search-md", default="", dest="search_md", help="search.md 路径")
    p.add_argument("--topic", default="", help="无 search-md 时定位 keyword_workspace/<topic>")
    p.add_argument("--range-label", default="", dest="range_label", help="配合 topic 子目录")
    p.add_argument("--query", default="", help="关键词或专业检索式（非分级）")
    p.add_argument(
        "--pro",
        action="store_true",
        help="非分级时 query 视为专业检索式",
    )
    p.add_argument(
        "--num",
        type=int,
        default=default_num,
        help=(
            f"本批目标篇数（默认 {default_num}"
            + (
                f"；0=在 {CNKI_BATCH_NUM_MIN}–{CNKI_BATCH_NUM_MAX} 随机，不要每批写死 50）。"
                "同一 --out-name 续传；要采够请用 --until，不要一次填满 TOTAL"
                if fulltext
                else "）。题录本批条数"
            )
        ),
    )
    p.add_argument(
        "--out-name",
        default="",
        dest="out_name",
        help=("corpus 下批次目录名；同一任务必须沿用，才能续传跳过已下"
              if fulltext else "corpus 下题录批次目录名；重跑按题名更新"),
    )


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=None, help="覆盖 GLEANERA_ROOT / 默认仓库路径")
    common.add_argument(
        "--json",
        action="store_true",
        help="预留：摘要只打 JSON（status 默认整段 JSON）",
    )
    common.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="可选；传给长任务；默认不设超时",
    )

    parser = argparse.ArgumentParser(
        prog="gleanera_cli.py",
        description="Gleanera 校外机构版 CLI（Skill 调用入口）",
    )
    parser.add_argument("--root", default=None, help="覆盖 GLEANERA_ROOT")
    parser.add_argument("--json", action="store_true", help="预留 JSON 模式")
    parser.add_argument(
        "--timeout", type=float, default=None, help="可选长任务超时（秒）"
    )

    sub = parser.add_subparsers(
        dest="command", required=True,
        metavar="{install-skill,status,sources,score,login-hint,prepare,cnki-list,cnki}",
    )

    sub.add_parser(
        "install-skill",
        parents=[common],
        help="把 skill/gleanera 注册到 ~/.grok、~/.cursor、~/.codex",
    )
    sub.add_parser("status", parents=[common], help="部署就绪检查")
    sub.add_parser("sources", parents=[common], help="列出论文源与配置状态")
    sub.add_parser("score", parents=[common], help="查询超级鹰积分")
    sub.add_parser("login-hint", parents=[common], help="打印 CNKI 有头登录步骤")

    p_prep = sub.add_parser(
        "prepare", parents=[common], help="CNKI 分级检索式"
    )
    p_prep.add_argument("--topic", required=True, help="研究方向/主题（目录名）")
    p_prep.add_argument(
        "--concept-groups",
        required=True,
        help="概念组 JSON 字符串；或以 @path 读文件",
    )
    p_prep.add_argument("--year-from", default="2015", help="发表年份下限（默认 2015）")
    p_prep.add_argument("--year-to", default="", help="发表年份上限")
    p_prep.add_argument("--range-label", default="", help="子目录名，默认 year_from_year_to")
    p_prep.add_argument(
        "--max-keywords", type=int, default=8, help="每组最多词数（默认 8）"
    )
    p_prep.add_argument(
        "--num", type=int, default=30, help="search.md 用法说明中的目标篇数（默认 30）"
    )

    p_list = sub.add_parser(
        "cnki-list", parents=[common], help="CNKI 仅题录（run_list.py，默认无硬超时）"
    )
    _add_cnki_args(p_list, default_num=100)
    p_list.add_argument(
        "--details", action="store_true",
        help="进入详情页补充摘要、关键词、机构、基金；仅输出 11 列题录，不下载 PDF/CAJ",
    )

    p_cnki = sub.add_parser(
        "cnki", parents=[common], help="CNKI 全文（run_batch.py，默认无硬超时）"
    )
    _add_cnki_args(p_cnki, default_num=0, fulltext=True)
    p_cnki.add_argument(
        "--until",
        type=int,
        default=0,
        help="目标总篇数；>0 时串行多批。机构会话批间不自动重录。0=只跑一批",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = resolve_root(getattr(args, "root", None))
    apply_credentials(load_credentials(root))
    # 长任务 cwd；prepare 亦传 workspace_root=root
    try:
        os.chdir(root)
    except OSError:
        pass

    cmd = args.command
    if cmd == "install-skill":
        return cmd_install_skill(root)
    if cmd == "status":
        return cmd_status(root)
    if cmd == "sources":
        return cmd_sources(root)
    if cmd == "score":
        return cmd_score(root)
    if cmd == "login-hint":
        return cmd_login_hint(root)
    if cmd == "prepare":
        return cmd_prepare(root, args)
    if cmd == "cnki-list":
        return cmd_cnki_list(root, args)
    if cmd == "cnki":
        return cmd_cnki(root, args)

    print(f"未知子命令: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
