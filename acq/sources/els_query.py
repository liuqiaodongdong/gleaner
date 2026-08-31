# acq/sources/els_query.py —— ScienceDirect Search API V2 专业检索构建 + 白名单选刊
"""按官方 PUT 接口组式，避免把松散词丢进全文 qs 导致下歪。

ScienceDirect Search API V2（推荐 PUT）原生字段：
  title  文章题名（本线默认，对应知网 SU / Scopus TITLE）
  qs     全文（除参考文献）；太松，仅 --scope qs 显式打开
  pub    刊名（由 run_els_batch 按白名单逐刊填）
  date   年份范围 YYYY 或 YYYY-YYYY
  display.sortBy  relevance（官方默认）| date
  display.show   仅 10 / 25 / 50 / 100

V2 PUT 的 title/qs 内支持大写 AND / OR / NOT、括号、引号短语。
tak() / TITLE-ABS-KEY() 是旧 GET / Scopus 语法，PUT 不认，组式时剥掉只留内层。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_DEFAULT_TIERS = Path(__file__).resolve().parent.parent / "data" / "intl_journal_tiers.json"
QS_MAX = 250
SHOW_ALLOWED = (10, 25, 50, 100)
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_FIELD_WRAP = re.compile(
    r"\b(?:tak|title-abstr-key|ttl|title|abs|key|title-abs-key)\s*\(([^()]*)\)",
    re.I,
)
_BOOL_WORD = re.compile(r"\b(and\s+not|and|or|not)\b", re.I)


def _term(t: str) -> str:
    """多词/带连字符的词组加引号，单词原样（允许 SD 词干）。"""
    t = (t or "").strip().strip('"').strip("{}")
    if not t:
        return ""
    return f'"{t}"' if (" " in t or "-" in t) else t


def build_qs(groups: list) -> str:
    """概念组 -> V2 title/qs 布尔式：组内 OR、组间 AND。

    groups: [["digital economy","digitalization"], ["innovation","patent"]]
        -> '("digital economy" OR digitalization) AND (innovation OR patent)'
    空词/空组自动跳过；单组单词不加括号。
    """
    parts = []
    for g in groups:
        terms = [_term(t) for t in g if t and str(t).strip()]
        terms = [x for x in terms if x]
        if not terms:
            continue
        parts.append(terms[0] if len(terms) == 1 else "(" + " OR ".join(terms) + ")")
    return " AND ".join(parts)


def _strip_legacy_field_wrappers(s: str) -> str:
    """剥掉 tak(...) / ttl(...) / TITLE-ABS-KEY(...)，V2 PUT 只认 title/qs 字段。"""
    prev = None
    while prev != s:
        prev = s
        s = _FIELD_WRAP.sub(r"\1", s)
    return s


def _upper_bool(s: str) -> str:
    def repl(m: re.Match) -> str:
        w = re.sub(r"\s+", " ", m.group(1).strip().lower())
        if w == "and not":
            return "NOT"
        return w.upper()

    s = _BOOL_WORD.sub(repl, s)
    return re.sub(r"\bAND\s+NOT\b", "NOT", s)


def normalize_els_query(raw: str) -> str:
    """把用户/Agent 输入收成 V2 PUT 可用的 title/qs 布尔式。

    - 空式报错
    - 纯中文报错（SD 经济管理刊几乎不吃中文主题词）
    - 剥旧 GET/Scopus 字段包装
    - and/or/not 升成 AND/OR/NOT（小写在 V2 里是普通词）
    - 超 250 字符从词边界截断
    """
    s = (raw or "").strip()
    if not s:
        raise ValueError("Elsevier 检索式为空")
    content = _BOOL_WORD.sub(" ", s)
    if _CJK_RE.search(s) and not re.search(r"[A-Za-z]{2,}", content):
        raise ValueError(
            "ScienceDirect 专业检索需英文式。纯中文在 SD 上几乎无效，"
            "请改用英文概念组（JSON keywords）或英文短语，例如 "
            '"supply chain" AND "green transition"。'
        )
    s = _strip_legacy_field_wrappers(s)
    s = _upper_bool(s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > QS_MAX:
        s = s[:QS_MAX].rsplit(" ", 1)[0].rstrip("()").strip()
    if not s:
        raise ValueError("Elsevier 检索式规范化后为空")
    return s


def clamp_show(n: int) -> int:
    """V2 display.show 只允许 10/25/50/100。"""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return 10
    for v in SHOW_ALLOWED:
        if n <= v:
            return v
    return 100


def parse_els_concept_groups(raw: str | list | dict) -> list[list[str]]:
    """解析 Elsevier 用的英文概念组。只要词列表，不要中文 SU 式。

    支持：
      [{"name":"supply chain","keywords":["supply chain","supplier-customer"]}, ...]
      [["supply chain","supplier"], ["green transition"]]
      markdown 里的 `英文:` / `English:` / `en:` 行
    只有 `中文:`、没有英文词时抛错。
    """
    if raw is None:
        raise ValueError("concept_groups 为空")
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            raise ValueError("concept_groups 为空")
        if "###" in text or "英文:" in text or "English:" in text or "en:" in text:
            groups = _parse_els_markdown_groups(text)
            if groups:
                return groups
            raise ValueError(
                "markdown 概念组未找到英文词。请写 `英文:` / `English:` 行，不要只写 `中文:`。"
            )
        raw = json.loads(text)

    if isinstance(raw, dict):
        raw = raw.get("groups") or raw.get("concept_groups") or raw
        if isinstance(raw, dict):
            raise ValueError("concept_groups JSON 需为数组，或含 groups 数组")

    if not isinstance(raw, list) or not raw:
        raise ValueError("concept_groups 需为非空数组")

    out: list[list[str]] = []
    for i, item in enumerate(raw):
        if isinstance(item, dict):
            kws = item.get("keywords") or item.get("en") or item.get("english") or item.get("terms") or []
            if isinstance(kws, str):
                kws = [p.strip() for p in re.split(r"[,，;；]", kws) if p.strip()]
            kws = [str(k).strip() for k in kws if str(k).strip()]
        elif isinstance(item, (list, tuple)):
            kws = [str(k).strip() for k in item if str(k).strip()]
        elif isinstance(item, str):
            kws = [item.strip()] if item.strip() else []
        else:
            raise ValueError(f"无法解析 concept_groups[{i}]")
        latin = [k for k in kws if re.search(r"[A-Za-z]", k)]
        if not latin:
            raise ValueError(
                f"概念组 {i + 1} 没有英文词。ScienceDirect 请用英文 keywords，不要只填中文。"
            )
        out.append(latin)
    if not out:
        raise ValueError("concept_groups 无有效英文组")
    return out


def _parse_els_markdown_groups(text: str) -> list[list[str]]:
    groups: list[list[str]] = []
    pending: list[str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if re.match(r"^###\s+", line):
            if pending:
                groups.append(pending)
            pending = None
            continue
        m = re.match(r"^(?:英文|English|en)\s*[:：]\s*(.+)$", line, re.I)
        if m:
            kws = [p.strip() for p in re.split(r"[,，;；]", m.group(1)) if p.strip()]
            latin = [k for k in kws if re.search(r"[A-Za-z]", k)]
            if latin:
                pending = latin
    if pending:
        groups.append(pending)
    return groups


def load_tiers(path=None) -> dict:
    p = Path(path) if path else _DEFAULT_TIERS
    return json.loads(p.read_text(encoding="utf-8"))


def select_journals(tiers: dict, tier_sel: str) -> list:
    """tier_sel '1' / '1+2' / '1+2+3' -> 选中 tier 的刊列表。"""
    want = {int(x) for x in tier_sel.split("+") if x.strip().isdigit()}
    out = []
    for t in (1, 2, 3):
        if t in want:
            out.extend(tiers.get(f"tier{t}", []))
    return out
