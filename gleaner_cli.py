# gleaner_cli.py — Gleaner 统一 CLI（install-skill / status / sources / score / login-hint / prepare / cnki-list / cnki / els / intl）
"""用法: python gleaner_cli.py <command> [options]

全局: --root PATH  --json  --timeout SEC
子命令: install-skill | status | sources | score | login-hint | prepare | cnki-list | cnki | els | intl
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

CNKI_BATCH_NUM_MIN = 40
CNKI_BATCH_NUM_MAX = 60

from acq.cli_support import (
    apply_credentials,
    install_user_skill,
    load_credentials,
    resolve_root,
    resolve_tiered_expression,
    run_logged,
    summarize_batch,
)


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

    _print_json(check_setup())
    return 0


def cmd_sources(root: Path) -> int:
    """列出各源状态；guard 读 root/acq/guard_state/。"""
    from acq.setup_check import check_setup

    setup = check_setup()

    def _guard_info(name: str) -> dict:
        try:
            state_file = root / "acq" / "guard_state" / f"guard_{name}.json"
            if state_file.exists():
                s = json.loads(state_file.read_text(encoding="utf-8"))
                return {
                    "today_used": s.get("count", 0),
                    "tripped": s.get("tripped", False),
                    "day": s.get("day", ""),
                    "fail_count": s.get("fail_count", 0),
                }
            return {"status": "no_state_yet"}
        except Exception:
            return {"status": "unknown"}

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
                "access": "主力机本地经代理(机构权限)",
                "tool": "cnki / cnki-list / prepare",
                "ready": L["cnki"]["cnki_collect_ready"],
                "note": (
                    "分级：Agent 拓展概念组→prepare→level=L1..L4；"
                    "白名单 acq/data/cnki_journal_tiers.json"
                ),
            },
            {
                "name": "openalex",
                "type": "discovery",
                "status": "ready",
                "modes": ["keyword"],
                "access": "公网API(mailto必填)",
                "tool": "intl",
                "note": "发现层，不直接下文",
            },
            {
                "name": "oa",
                "type": "download",
                "status": "ready",
                "modes": ["doi→直链"],
                "access": "公网OA(Unpaywall/DOAJ)",
                "tool": "intl",
                "guard": _guard_info("oa"),
            },
            {
                "name": "scihub",
                "type": "download",
                "status": "ready",
                "modes": ["doi→SciHub镜像"],
                "access": "公网直连（不走环境代理）",
                "tool": "intl",
                "guard": _guard_info("scihub"),
            },
            {
                "name": "carsi",
                "type": "download",
                "status": (
                    "ready"
                    if L["intl"]["carsi_optional"]["ok"]
                    else "optional_unconfigured"
                ),
                "modes": ["doi→机构订阅"],
                "access": "CARSI认人不认IP，主力机本地",
                "tool": "intl",
                "guard": _guard_info("carsi"),
            },
            {
                "name": "elsevier",
                "type": "paper",
                "status": "ready" if L["elsevier"]["ready"] else "needs_setup",
                "modes": ["title题名布尔+relevance+白名单tier→取全文转MD"],
                "access": "主力机本地，Elsevier官方API+API key",
                "tool": "els",
                "ready": L["elsevier"]["ready"],
                "note": (
                    "白名单 acq/data/intl_journal_tiers.json；"
                    "首次请 python gleaner_cli.py status"
                ),
            },
        ],
    }
    _print_json(payload)
    return 0


def cmd_score(_root: Path) -> int:
    from captcha import chaojiying_score

    print(chaojiying_score())
    return 0


def cmd_login_hint(_root: Path) -> int:
    text = """\
【CNKI 有头登录 · 获取 cookies.json】

1. 在项目根目录（GLEANER_ROOT）打开终端。
2. 建议使用 Edge 通道（系统已装 Edge 时更稳）：
     set ACQ_BROWSER_CHANNEL=msedge
   PowerShell:
     $env:ACQ_BROWSER_CHANNEL = "msedge"
3. 批次间重录必须带现有 cookies.json（加载后刷新会话，禁止冷启动）。
     python login.py
   仅首次没有 cookie 时才允许：
     set ACQ_ALLOW_COLD_LOGIN=1
     python login.py
   冷启动通常下不了全文，不要用它续批次。
4. 检索页滑块由超级鹰 9602 自动解（需已配置 CJY_*）。
   看得见拼图才打码；过验证（拼图消失或检索框出现）立刻写 cookies.json 并退出。
   URL 仍带 /verify 也算过了。无面板绝不整页送超级鹰。
   Agent 不要用浏览器工具自己抠 cookie，只跑 login.py。
   无需个人账号。缺超级鹰时请手拖，拖完脚本会立刻写盘。
5. cookie 为短会话：换网络、换代理或过期后请重跑 login.py（仍加载旧 cookie）。
   全文分批时：每批在 40–60 随机取一篇数（省略 --num 即可），同一 --out-name；
   批间热启动 login.py，不要并行、不要每批都写死 50。
6. 登录后可用：
     python gleaner_cli.py status
   查看 cookies 是否就绪。

说明：CNKI 采集硬门槛为机构代理 + cookies.json；全文另需超级鹰。
无 cookie 禁止先采（会空烧超级鹰）。勿把 cookies.json / 密钥提交到 git。
"""
    print(text)
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
    num = int(getattr(args, "num", 0) or 0)
    num_randomized = False
    if command == "cnki" and num <= 0:
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
    corpus.mkdir(parents=True, exist_ok=True)
    out_dir = corpus / batch
    params: dict[str, Any] = {"num": num, "out": str(out_dir)}
    if pro:
        params.update(pro=True, expression=params_query)
    else:
        params["keyword"] = params_query

    pfile = corpus / params_filename
    pfile.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")

    os.environ.setdefault("ACQ_HEADLESS", "1")
    os.environ.setdefault("ACQ_BROWSER_CHANNEL", "msedge")

    log_path = corpus / f"{batch}_run.log"
    cmd = [sys.executable, str(root / script), str(pfile)]
    exit_code = run_logged(
        cmd,
        cwd=root,
        log_path=log_path,
        timeout=getattr(args, "timeout", None),
    )

    summary = summarize_batch(out_dir, file_glob="*.pdf")
    # 全文线可能还有 .caj
    if command == "cnki":
        caj = summarize_batch(out_dir, file_glob="*.caj")
        summary["downloaded_files"] = summary["downloaded_files"] + caj["downloaded_files"]

    result: dict[str, Any] = {
        "ok": exit_code == 0,
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
    return 0 if exit_code == 0 else 1


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


# OpenAlex polite pool mailto
_INTL_DEFAULT_EMAIL = "Libby_Stantoncsc@writeme.com"
_INTL_DEFAULT_SOURCES = ["oa", "nber", "scihub"]


def cmd_els(root: Path, args: argparse.Namespace) -> int:
    """Elsevier：preflight → 白名单选刊 → params → run_els_batch.py → 摘要 *.md。"""
    from acq.setup_check import preflight
    from acq.sources.els_query import (
        build_qs,
        load_tiers,
        normalize_els_query,
        parse_els_concept_groups,
        select_journals,
    )

    bad = preflight("elsevier")
    if bad:
        _print_json(bad)
        return 1

    query = (args.query or "").strip()
    groups_raw = (getattr(args, "concept_groups", None) or "").strip()
    if groups_raw:
        try:
            groups = parse_els_concept_groups(_resolve_concept_groups(groups_raw))
            query = build_qs(groups)
        except (ValueError, json.JSONDecodeError) as exc:
            _print_json({"ok": False, "error": f"concept_groups 无效: {exc}"})
            return 1
    if not query:
        _print_json({
            "ok": False,
            "error": "els 需要 --query（英文布尔式）或 --concept-groups（英文概念组）",
        })
        return 1
    try:
        query = normalize_els_query(query)
    except ValueError as exc:
        _print_json({"ok": False, "error": str(exc)})
        return 1

    tier = (args.tier or "1+2").strip()
    year_from = (args.year_from or "2015").strip()
    per_journal = int(args.per_journal)
    num = int(args.num)
    out_name = (args.out_name or "").strip()
    sort = (getattr(args, "sort", None) or "relevance").strip()
    scope = (getattr(args, "scope", None) or "title").strip()

    journals = select_journals(load_tiers(), tier)
    if not journals:
        _print_json(
            {
                "ok": False,
                "query": query,
                "tier": tier,
                "found": 0,
                "note": "该 tier 无白名单刊",
            }
        )
        return 1

    batch = out_name or ("els_" + re.sub(r"\W+", "_", query)[:20]).strip("_")
    corpus = root / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    out_dir = corpus / batch
    params: dict[str, Any] = {
        "qs": query,
        "journals": journals,
        "date_from": year_from,
        "per_journal": per_journal,
        "num": num,
        "sort": sort,
        "scope": scope,
        "out": str(out_dir),
    }
    pfile = corpus / "_cli_els_params.json"
    pfile.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")

    log_path = corpus / f"{batch}_run.log"
    cmd = [sys.executable, str(root / "run_els_batch.py"), str(pfile)]
    exit_code = run_logged(
        cmd,
        cwd=root,
        log_path=log_path,
        timeout=getattr(args, "timeout", None),
    )

    summary = summarize_batch(out_dir, file_glob="*.md")
    result: dict[str, Any] = {
        "ok": exit_code == 0,
        "exit_code": exit_code,
        "command": "els",
        "query": query,
        "tier": tier,
        "journals_searched": len(journals),
        "log_path": str(log_path),
        "params_file": str(pfile),
        "merged_metadata": (
            _try_merge_corpus(root) if exit_code == 0 else None
        ),
        **summary,
    }
    _print_json(result)
    return 0 if exit_code == 0 else 1


def _parse_intl_sources(raw: str | None) -> list[str]:
    """--sources 逗号分隔或 JSON 数组；空则用默认渠道。"""
    if raw is None or not str(raw).strip():
        return list(_INTL_DEFAULT_SOURCES)
    text = str(raw).strip()
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(s).strip() for s in parsed if str(s).strip()]
        except Exception:
            pass
    return [s.strip() for s in text.split(",") if s.strip()]


def cmd_intl(root: Path, args: argparse.Namespace) -> int:
    """国际：写 params（字段同 intl_collect）→ run_intl_batch.py → 摘要 *.pdf。"""
    query = (args.query or "").strip()
    if not query:
        _print_json({"ok": False, "error": "intl 需要 --query"})
        return 1

    num = int(args.num)
    sources = _parse_intl_sources(getattr(args, "sources", None))
    year_from = (getattr(args, "year_from", None) or "").strip()
    issn = (getattr(args, "issn", None) or "").strip()
    out_name = (getattr(args, "out_name", None) or "").strip()
    email = (getattr(args, "email", None) or "").strip() or _INTL_DEFAULT_EMAIL

    batch = out_name or ("intl_" + re.sub(r"\W+", "_", query)[:20]).strip("_")
    corpus = root / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    out_dir = corpus / batch

    params: dict[str, Any] = {
        "query": query,
        "num": num,
        "out": str(out_dir),
        "sources": sources,
        "email": email,
    }
    if year_from:
        params["year_from"] = year_from
    if issn:
        params["issn"] = issn

    pfile = corpus / "_cli_intl_params.json"
    pfile.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")

    log_path = corpus / f"{batch}_run.log"
    cmd = [sys.executable, str(root / "run_intl_batch.py"), str(pfile)]
    exit_code = run_logged(
        cmd,
        cwd=root,
        log_path=log_path,
        timeout=getattr(args, "timeout", None),
    )

    summary = summarize_batch(out_dir, file_glob="*.pdf")
    result: dict[str, Any] = {
        "ok": exit_code == 0,
        "exit_code": exit_code,
        "command": "intl",
        "query": query,
        "sources": sources,
        "log_path": str(log_path),
        "params_file": str(pfile),
        "merged_metadata": (
            _try_merge_corpus(root) if exit_code == 0 else None
        ),
        **summary,
    }
    _print_json(result)
    return 0 if exit_code == 0 else 1


def _add_cnki_args(p: argparse.ArgumentParser, *, default_num: int) -> None:
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
            f"本批目标篇数（默认 {default_num}；全文 0=在 "
            f"{CNKI_BATCH_NUM_MIN}–{CNKI_BATCH_NUM_MAX} 随机，不要每批写死 50）。"
            "同一 --out-name 续传，不要一次填满 TOTAL"
        ),
    )
    p.add_argument(
        "--out-name",
        default="",
        dest="out_name",
        help="corpus 下批次目录名；同一任务必须沿用，才能续传跳过已下",
    )


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=None, help="覆盖 GLEANER_ROOT / 默认仓库路径")
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
        prog="gleaner_cli.py",
        description="Gleaner 统一 CLI（Skill 调用入口）",
    )
    parser.add_argument("--root", default=None, help="覆盖 GLEANER_ROOT")
    parser.add_argument("--json", action="store_true", help="预留 JSON 模式")
    parser.add_argument(
        "--timeout", type=float, default=None, help="可选长任务超时（秒）"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "install-skill",
        parents=[common],
        help="把 skill/gleaner 注册到 ~/.grok、~/.cursor、~/.codex",
    )
    sub.add_parser("status", parents=[common], help="部署就绪检查")
    sub.add_parser("sources", parents=[common], help="列出论文源与 guard 状态")
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

    p_cnki = sub.add_parser(
        "cnki", parents=[common], help="CNKI 全文（run_batch.py，默认无硬超时）"
    )
    _add_cnki_args(p_cnki, default_num=0)

    p_els = sub.add_parser(
        "els", parents=[common], help="Elsevier 白名单全文（run_els_batch.py，默认无硬超时）"
    )
    p_els.add_argument(
        "--query",
        default="",
        help="英文布尔式，写入题名字段。例: \"supply chain\" AND \"green transition\"",
    )
    p_els.add_argument(
        "--concept-groups",
        default="",
        dest="concept_groups",
        help="英文概念组 JSON（或 @path）；组内 OR、组间 AND。有则覆盖 --query",
    )
    p_els.add_argument("--num", type=int, default=25, help="全局目标篇数上限（默认 25）")
    p_els.add_argument(
        "--tier", default="1+2", help='白名单档位 "1"/"1+2"/"1+2+3"（默认 1+2）'
    )
    p_els.add_argument(
        "--year-from", default="2015", dest="year_from", help="年份下限（默认 2015）"
    )
    p_els.add_argument(
        "--per-journal",
        type=int,
        default=10,
        dest="per_journal",
        help="每刊取回上限（默认 10；API 仅允许 10/25/50/100）",
    )
    p_els.add_argument(
        "--sort",
        default="relevance",
        choices=("relevance", "date"),
        help="排序：relevance（默认，防下歪）或 date",
    )
    p_els.add_argument(
        "--scope",
        default="title",
        choices=("title", "qs"),
        help="title=题名（默认）；qs=全文（易下歪，仅高召回时用）",
    )
    p_els.add_argument("--out-name", default="", dest="out_name", help="corpus 下批次目录名")

    p_intl = sub.add_parser(
        "intl", parents=[common], help="国际论文（run_intl_batch.py，默认无硬超时）"
    )
    p_intl.add_argument("--query", required=True, help="英文关键词或短语")
    p_intl.add_argument("--num", type=int, default=25, help="目标篇数（默认 25）")
    p_intl.add_argument(
        "--sources",
        default="",
        help='下载渠道，逗号分隔（默认 oa,nber,scihub；可加 carsi）',
    )
    p_intl.add_argument(
        "--year-from", default="", dest="year_from", help="年份下限（如 2020）"
    )
    p_intl.add_argument("--issn", default="", help="期刊 ISSN 过滤")
    p_intl.add_argument("--out-name", default="", dest="out_name", help="corpus 下批次目录名")
    p_intl.add_argument(
        "--email",
        default="",
        help=f"OpenAlex mailto（默认 {_INTL_DEFAULT_EMAIL}）",
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
    if cmd == "els":
        return cmd_els(root, args)
    if cmd == "intl":
        return cmd_intl(root, args)

    print(f"未知子命令: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
