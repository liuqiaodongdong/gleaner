"""物尽其用 Gleaner —— 机构学术资源采集 MCP，跑在主力机(本地 stdio)，CC 直连。

Authors: liuqiaodongdong and Grok (https://github.com/liuqiaodongdong · xAI)

三条采集线（全部主力机本地执行，无需备用机 SSH）：
  - CNKI 中文线   cnki_collect(全文)/cnki_list(题录)  —— 本地经代理(机构权限)+超级鹰过码 → PDF
  - 国际线 #13     intl_collect                        —— 本地直跑(OpenAlex→OA/NBER/Sci-Hub/CARSI) → PDF
  - Elsevier 订阅线 els_collect                        —— 本地官方 API + API key → 全文 XML 转 MD
辅助：setup_status(部署引导) / chaojiying_score / list_sources。
产物统一落 corpus/<批次>/，merged_metadata.csv 跨源去重喂 0131。

【Agent 铁律】用户首次使用或准备采集前，先调 setup_status；
若对应线 ready=false，必须按 next_steps_for_user 引导用户申请/填写凭据，
禁止在未配置时硬跑采集。详见仓库 AGENTS.md。

CC 侧典型用法：setup_status → 配齐凭据 → 主题 → 检索式 → cnki_collect / els_collect。
"""
import base64
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gleaner")  # 物尽其用 Gleaner

LOCAL_CORPUS = Path(__file__).parent / "corpus"   # 主力机语料目录(喂 0131)


def _proxy_server() -> str:
    """返回给 Playwright 用的代理地址。优先 ACQ_PROXY 环境变量；否则读 Windows 系统代理
    (HKCU Internet Settings)，与用户浏览器保持一致——这样用户再换代理也无需改码。
    读不到则空串(直连)。"""
    v = os.environ.get("ACQ_PROXY")
    if v:
        return v
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        enable, _ = winreg.QueryValueEx(k, "ProxyEnable")
        if not enable:
            return ""
        server, _ = winreg.QueryValueEx(k, "ProxyServer")
        if not server:
            return ""
        if "=" in server:  # 分协议格式 "http=host:port;https=host:port"
            parts = dict(p.split("=", 1) for p in server.split(";") if "=" in p)
            server = parts.get("https") or parts.get("http") or ""
        if not server:
            return ""
        return server if "://" in server else f"http://{server}"
    except Exception:
        return ""


def _refresh_merged():
    """跨源(中英)去重归一，刷新 corpus/merged_metadata.csv(喂 0131)。失败不阻断采集。"""
    try:
        from acq.normalize_corpus import merge_corpus
        return str(merge_corpus(LOCAL_CORPUS))
    except Exception as exc:
        return f"merge_skipped: {exc}"


def _run_collect(query: str, num: int = 20, pro: bool = False, out_name: str = "",
                 script: str = "run_batch.py") -> dict:
    """核心：写参数→主力机本地直跑 <script>(经代理拿知网机构权限)→读 metadata。
    script：cnki_collect→run_batch.py，cnki_list→run_list.py。
    """
    batch = out_name or ("batch_" + re.sub(r"\W+", "_", query)[:20]).strip("_")
    out_dir = LOCAL_CORPUS / batch
    LOCAL_CORPUS.mkdir(parents=True, exist_ok=True)
    params = {"num": int(num), "out": str(out_dir)}   # 绝对路径：脚本直接落主力机语料目录
    if pro:
        params.update(pro=True, expression=query)
    else:
        params["keyword"] = query

    # 1) 参数写本地 JSON(避免命令行中文乱码)
    pfile = LOCAL_CORPUS / "_mcp_params.json"
    pfile.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")

    # 2) 本地直跑采集脚本：无头 + 系统 Edge + 代理(拿机构权限)
    project_root = Path(__file__).parent
    env = dict(os.environ)
    env.setdefault("ACQ_HEADLESS", "1")
    env.setdefault("ACQ_BROWSER_CHANNEL", "msedge")
    proxy = _proxy_server()
    if proxy:
        env["ACQ_PROXY"] = proxy
    r = subprocess.run([sys.executable, str(project_root / script), str(pfile)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=1800, cwd=str(project_root), env=env)
    out, err = r.stdout, r.stderr

    # 3) 读 metadata(脚本已直接写入 out_dir，无需 scp 拉回)
    local = out_dir
    meta = local / "metadata.csv"
    titles, npdf = [], 0
    if meta.exists():
        with open(meta, encoding="utf-8-sig") as f:
            titles = [r.get("title", "") for r in csv.DictReader(f)]
    pdir = local / "papers"
    if pdir.exists():
        npdf = len(list(pdir.glob("*.pdf"))) + len(list(pdir.glob("*.caj")))
    return {"query": query, "mode": "pro" if pro else "keyword",
            "ok": r.returncode == 0, "exit_code": r.returncode,
            "proxy": proxy or "(直连)",
            "downloaded_files": npdf, "metadata_rows": len(titles),
            "local_dir": str(local), "metadata_csv": str(meta),
            "merged_metadata": _refresh_merged(),
            "titles": titles, "log_tail": (out or "")[-1000:],
            "stderr_tail": (err or "")[-500:]}


@mcp.tool()
def cnki_collect(query: str, num: int = 20, pro: bool = False, out_name: str = ""):
    """检索知网并下载全文(主力机本地，经代理拿机构权限，超级鹰过验证码)。

    依赖：ACQ_PROXY/系统代理 + CJY_* 超级鹰；推荐 cookies.json（python login.py）。
    若未配置会返回 setup_incomplete 与 next_steps_for_user，请先引导用户完成配置。
    首次使用请先调 setup_status。

    Args:
        query: 关键词；或专业检索式(pro=True，用 cnki-advanced-search 技能生成)
        num: 目标篇数
        pro: 是否专业检索式模式
        out_name: 批次目录名(默认按 query 自动生成)
    返回 JSON：下载数、主力机本地目录、metadata.csv 路径、标题列表。
    """
    from acq.setup_check import preflight
    bad = preflight("cnki_collect")
    if bad:
        return json.dumps(bad, ensure_ascii=False, indent=2)
    return json.dumps(_run_collect(query, num, pro, out_name), ensure_ascii=False, indent=2)


@mcp.tool()
def cnki_list(query: str, num: int = 100, pro: bool = False, out_name: str = ""):
    """检索知网只取题录元数据(作者/期刊/年/被引)，不下全文，供 find-leading-scholars 排本土大佬。

    与 cnki_collect 同为主力机本地执行，但跑 run_list.py —— 只爬列表页，
    不进详情页、不下 PDF，因此快很多、配额可设大(num 默认 100)。
    需要机构代理；首次使用请先 setup_status。

    Args:
        query: 关键词；或专业检索式(pro=True，用 cnki-advanced-search 技能生成)
        num: 目标题录数
        pro: 是否专业检索式模式
        out_name: 批次目录名(默认按 query 自动生成)
    返回 JSON：metadata_rows、主力机本地目录、metadata.csv 路径、标题列表。
    downloaded_files 恒为 0（题录模式不下文，属预期）。
    """
    from acq.setup_check import preflight
    bad = preflight("cnki_list")
    if bad:
        return json.dumps(bad, ensure_ascii=False, indent=2)
    return json.dumps(_run_collect(query, num, pro, out_name, script="run_list.py"),
                      ensure_ascii=False, indent=2)


@mcp.tool()
def intl_collect(query: str, num: int = 25, sources=None, year_from: str = "",
                 issn: str = "", out_name: str = ""):
    """检索国际论文并下载全文（OpenAlex发现→OA直下/SciHub/CARSI机构库），结果进主力机语料目录。

    OA/SciHub/CARSI 均在主力机本地直跑，无需校园 IP，无需 SSH。

    Args:
        query: 英文关键词或短语
        num: 目标篇数（OpenAlex 最多拉取条数）
        sources: 下载渠道列表，默认 ["oa", "scihub"]，可加 "carsi"
        year_from: 年份下限（如 "2020"）
        issn: 期刊 ISSN 过滤
        out_name: 批次目录名（默认按 query 自动生成）
    返回 JSON：发现数、下载数、主力机本地目录、metadata.csv 路径、标题列表。
    """
    if sources is None:
        sources = ["oa", "nber", "scihub"]
    elif isinstance(sources, str):
        # MCP 客户端可能把列表传成字符串(JSON 数组或逗号分隔)，做个防御
        try:
            parsed = json.loads(sources)
            sources = parsed if isinstance(parsed, list) else [str(parsed)]
        except Exception:
            sources = [s.strip() for s in sources.split(",") if s.strip()]

    batch = out_name or ("intl_" + re.sub(r"\W+", "_", query)[:20]).strip("_")
    out_dir = LOCAL_CORPUS / batch
    LOCAL_CORPUS.mkdir(parents=True, exist_ok=True)

    # 参数写到本地临时 JSON，传给 run_intl_batch.py
    params = {
        "query": query,
        "num": int(num),
        "out": str(out_dir),
        "sources": sources,
        "email": "Libby_Stantoncsc@writeme.com",
    }
    if year_from:
        params["year_from"] = year_from
    if issn:
        params["issn"] = issn

    pfile = LOCAL_CORPUS / "_intl_params.json"
    pfile.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")

    # 本地直跑 run_intl_batch.py
    project_root = Path(__file__).parent
    r = subprocess.run(
        [sys.executable, str(project_root / "run_intl_batch.py"), str(pfile)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=1800, cwd=str(project_root),
    )

    # 读 metadata
    meta = out_dir / "metadata.csv"
    titles, npdf = [], 0
    if meta.exists():
        with open(meta, encoding="utf-8-sig") as f:
            titles = [row.get("title", "") for row in csv.DictReader(f)]
    pdir = out_dir / "papers"
    if pdir.exists():
        npdf = len(list(pdir.glob("*.pdf")))

    return json.dumps({
        "query": query, "sources": sources,
        "ok": r.returncode == 0,            # 区分"脚本正常但0篇"与"脚本崩溃退出"
        "exit_code": r.returncode,
        "downloaded_files": npdf, "metadata_rows": len(titles),
        "local_dir": str(out_dir), "metadata_csv": str(meta),
        "merged_metadata": _refresh_merged(),
        "titles": titles,
        "log_tail": (r.stdout or "")[-1000:],
        "stderr_tail": (r.stderr or "")[-500:],
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def els_collect(query: str, num: int = 25, tier: str = "1+2", year_from: str = "2015",
                per_journal: int = 25, out_name: str = ""):
    """检索学校订阅的 Elsevier/ScienceDirect【白名单经济/管理刊】并取全文(转MD)。

    主力机本地执行：Elsevier **官方** Developer API + API key
    （ELSEVIER_API_KEY 或 acq/data/.elsevier_key）。申请步骤见 docs/ELSEVIER_API.md
    （https://dev.elsevier.com/apikey/manage），禁止第三方 Key/网页爬取。
    无浏览器/无登录。只检索白名单 (acq/data/intl_journal_tiers.json) 中所选 tier 的刊。
    缺 key 时返回 setup_incomplete 与 apply_steps；首次请先 setup_status。

    Args:
        query: SD 专业检索式(qs 布尔)，如 '("digital economy" OR digitalization) AND (innovation OR patent)'。
               可用 acq.sources.els_query.build_qs(概念组) 生成；普通短语亦可。
        num: 全局目标篇数上限
        tier: 检索的白名单档位 "1"/"1+2"/"1+2+3"(1=顶级/A+++/A++,2=A+,3=ABS等)
        year_from: 年份下限(如 "2020")
        per_journal: 每刊取回上限
        out_name: 批次目录名(默认按 query 自动生成)
    返回 JSON：发现数/下载数/本地目录/标题/merged_metadata。
    """
    from acq.setup_check import preflight
    bad = preflight("elsevier")
    if bad:
        return json.dumps(bad, ensure_ascii=False, indent=2)
    from acq.sources.els_query import load_tiers, select_journals
    journals = select_journals(load_tiers(), tier)
    if not journals:
        return json.dumps({"query": query, "tier": tier, "found": 0,
                           "note": "该 tier 无白名单刊"}, ensure_ascii=False)
    batch = out_name or ("els_" + re.sub(r"\W+", "_", query)[:20]).strip("_")
    out_dir = LOCAL_CORPUS / batch
    LOCAL_CORPUS.mkdir(parents=True, exist_ok=True)
    params = {"qs": query, "journals": journals, "date_from": year_from,
              "per_journal": int(per_journal), "num": int(num), "out": str(out_dir)}
    pfile = LOCAL_CORPUS / "_els_params.json"
    pfile.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")

    # 本地直跑 run_els_batch.py（API key 鉴权，与 intl_collect 同构）
    project_root = Path(__file__).parent
    r = subprocess.run(
        [sys.executable, str(project_root / "run_els_batch.py"), str(pfile)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=1800, cwd=str(project_root),
    )
    out, err = r.stdout, r.stderr

    meta = out_dir / "metadata.csv"
    titles, nmd = [], 0
    if meta.exists():
        with open(meta, encoding="utf-8-sig") as f:
            titles = [r.get("title", "") for r in csv.DictReader(f)]
    pdir = out_dir / "papers"
    if pdir.exists():
        nmd = len(list(pdir.glob("*.md")))
    return json.dumps({"query": query, "tier": tier, "journals_searched": len(journals),
                       "ok": r.returncode == 0, "exit_code": r.returncode,
                       "found": len(titles), "downloaded_files": nmd,
                       "local_dir": str(out_dir), "merged_metadata": _refresh_merged(),
                       "titles": titles, "log_tail": (out or "")[-800:],
                       "stderr_tail": (err or "")[-500:]},
                      ensure_ascii=False, indent=2)


@mcp.tool()
def setup_status():
    """【部署引导·优先调用】检查超级鹰 / Elsevier API key / CNKI cookies / 代理是否已配置。

    Agent 在用户首次使用本 MCP、或准备 cnki_collect/els_collect 之前必须先调本工具。
    返回 JSON：各线 ready、blockers、next_steps_for_user（含申请网址与填写方式）。
    不回显任何密钥明文。若有缺失项，请把 next_steps_for_user 用清单展示给用户并协助完成。
    """
    from acq.setup_check import check_setup
    return json.dumps(check_setup(), ensure_ascii=False, indent=2)


@mcp.tool()
def chaojiying_score():
    """查超级鹰打码积分余额(主力机本地直查)。未配置 CJY_* 时返回错误提示。"""
    from captcha import chaojiying_score as _score
    return _score()


@mcp.tool()
def list_sources():
    """列出当前可用的论文源 adapter（含就绪状态与 guard 配额）。

    含 setup 摘要；详细部署引导请用 setup_status。
    """
    from acq.setup_check import check_setup
    setup = check_setup()

    def _guard_info(name):
        try:
            state_file = Path(__file__).parent / "acq" / "guard_state" / f"guard_{name}.json"
            if state_file.exists():
                s = json.loads(state_file.read_text("utf-8"))
                used = s.get("count", 0)
                tripped = s.get("tripped", False)
                return {"today_used": used, "tripped": tripped,
                        "day": s.get("day", ""), "fail_count": s.get("fail_count", 0)}
            return {"status": "no_state_yet"}
        except Exception:
            return {"status": "unknown"}

    L = setup["lines"]
    return json.dumps({
        "setup_ok": setup["ok"],
        "next_steps_for_user": setup["next_steps_for_user"],
        "sources": [
            {"name": "cnki", "type": "paper",
             "status": "ready" if L["cnki"]["cnki_collect_ready"] else "needs_setup",
             "modes": ["keyword", "pro(专业检索式)"], "access": "主力机本地经代理(机构权限)",
             "tool": "cnki_collect",
             "ready": L["cnki"]["cnki_collect_ready"],
             "note": "题录-only 走 cnki_list；首次请 setup_status"},
            {"name": "openalex", "type": "discovery", "status": "ready",
             "modes": ["keyword"], "access": "公网API(mailto必填)",
             "tool": "intl_collect", "note": "发现层，不直接下文"},
            {"name": "oa", "type": "download", "status": "ready",
             "modes": ["doi→直链"], "access": "公网OA(Unpaywall/DOAJ)",
             "tool": "intl_collect", "guard": _guard_info("oa")},
            {"name": "scihub", "type": "download", "status": "ready",
             "modes": ["doi→SciHub镜像"], "access": "公网(绕Clash直连)",
             "tool": "intl_collect", "guard": _guard_info("scihub")},
            {"name": "carsi", "type": "download",
             "status": "ready" if L["intl"]["carsi_optional"]["ok"] else "optional_unconfigured",
             "modes": ["doi→机构订阅"], "access": "CARSI认人不认IP，主力机本地",
             "tool": "intl_collect", "guard": _guard_info("carsi")},
            {"name": "elsevier", "type": "paper",
             "status": "ready" if L["elsevier"]["ready"] else "needs_setup",
             "modes": ["qs专业检索+白名单tier→取全文转MD"],
             "access": "主力机本地，Elsevier官方API+API key", "tool": "els_collect",
             "ready": L["elsevier"]["ready"],
             "note": "白名单 acq/data/intl_journal_tiers.json；首次请 setup_status"},
        ],
    }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
