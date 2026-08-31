# acq/sources/cnki_query.py —— CNKI 专业检索式构建 + 中文刊分级（纯逻辑，无网络）
"""从概念组 + journal_tiers 生成 L1–L4 检索式。

关键词同义发散由 Agent 完成；本模块只做确定性：
  概念组 → SU 子句 + LY 刊滤 + YE 年份 → search.md / 表达式。
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, NamedTuple

_DEFAULT_TIERS = Path(__file__).resolve().parent.parent / "data" / "cnki_journal_tiers.json"
VALID_LEVELS = ("L1", "L2", "L3", "L4")


class ConceptGroup(NamedTuple):
    label: str
    name: str
    keywords: list[str]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _split_keywords(value: str) -> list[str]:
    parts = re.split(r"[,，;；]", value)
    cleaned = []
    for part in parts:
        token = part.strip().strip("'\"`")
        if token:
            cleaned.append(token)
    return _dedupe(cleaned)


def parse_concept_groups(text: str) -> list[ConceptGroup]:
    """从 keywords.md 的「概念分组」段解析；每组需 `### X: 名` + `中文:` 行。"""
    groups: list[ConceptGroup] = []
    current_label = ""
    current_name = ""

    for raw_line in text.splitlines():
        line = raw_line.strip()
        heading = re.match(r"^###\s+([^:：]+)[:：]\s*(.+?)\s*$", line)
        if heading:
            current_label = heading.group(1).strip()
            current_name = heading.group(2).strip()
            continue

        if current_name and line.startswith("中文:"):
            keywords = _split_keywords(line.split(":", 1)[1])
            if keywords:
                groups.append(ConceptGroup(current_label, current_name, keywords))
            current_label = ""
            current_name = ""

    if not groups:
        raise ValueError("未找到带 `中文:` 行的概念分组（Concept groups）")
    return groups


def parse_concept_groups_json(raw: str | list | dict) -> list[ConceptGroup]:
    """接受 JSON 字符串或已解析结构。

    支持：
      [{"name":"数字经济","keywords":["数字经济","数字化"]}, ...]
      {"groups":[...]} 同上
      [["数字经济","数字化"], ["制造业"]]  — 自动标 A/B/...
    """
    data: Any = raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            raise ValueError("concept_groups 为空")
        # 若像 markdown，走 markdown 解析
        if "###" in text or "中文:" in text:
            return parse_concept_groups(text)
        data = json.loads(text)

    if isinstance(data, dict):
        data = data.get("groups") or data.get("concept_groups") or data
        if isinstance(data, dict):
            raise ValueError("concept_groups JSON 需为数组，或含 groups 数组")

    if not isinstance(data, list) or not data:
        raise ValueError("concept_groups 需为非空数组")

    groups: list[ConceptGroup] = []
    for i, item in enumerate(data):
        label = chr(ord("A") + i) if i < 26 else str(i + 1)
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("label") or f"概念{label}")
            kws = item.get("keywords") or item.get("中文") or item.get("terms") or []
            if isinstance(kws, str):
                kws = _split_keywords(kws)
            kws = _dedupe([str(k) for k in kws if str(k).strip()])
            if item.get("label"):
                label = str(item["label"])
        elif isinstance(item, (list, tuple)):
            name = f"概念{label}"
            kws = _dedupe([str(k) for k in item if str(k).strip()])
        elif isinstance(item, str):
            name = item
            kws = [item]
        else:
            raise ValueError(f"无法解析 concept_groups[{i}]: {type(item)}")
        if not kws:
            raise ValueError(f"概念组 {label}/{name} 无关键词")
        groups.append(ConceptGroup(label, name, kws))
    return groups


def load_journal_tiers(path: str | Path | None = None) -> dict[str, list[str]]:
    p = Path(path) if path else _DEFAULT_TIERS
    data = json.loads(p.read_text(encoding="utf-8"))
    tiers: dict[str, list[str]] = {}
    for tier_name in ("tier1", "tier2", "tier3"):
        journals = []
        for item in data.get(tier_name, []):
            if isinstance(item, str):
                name = item
            else:
                name = item.get("name", "")
            if name:
                journals.append(name)
        tiers[tier_name] = journals
    return tiers


def tier_counts(tiers: dict[str, list[str]] | None = None) -> dict[str, int]:
    t = tiers if tiers is not None else load_journal_tiers()
    return {k: len(v) for k, v in t.items()}


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_keyword_expression(
    groups: list[ConceptGroup],
    field: str = "SU",
    match: str = "%=",
    max_keywords: int = 8,
    core_only: bool = False,
) -> str:
    selected_groups = groups[:2] if core_only and len(groups) > 2 else groups
    blocks = []
    for group in selected_groups:
        selected_keywords = group.keywords[:max_keywords]
        clauses = [f"{field} {match} {_quote(keyword)}" for keyword in selected_keywords]
        blocks.append("(" + " OR ".join(clauses) + ")")
    return " AND ".join(blocks)


def build_journal_filter(journals: list[str]) -> str:
    if not journals:
        raise ValueError("期刊列表为空，无法构建 LY 过滤")
    joined = " + ".join(_quote(j) for j in journals)
    return f"LY = ({joined})"


def build_date_clause(year_from: str = "2015", year_to: str = "") -> str:
    if not year_from and not year_to:
        return ""
    if year_from and year_to:
        return f"YE >= {_quote(year_from)} AND YE <= {_quote(year_to)}"
    if year_from:
        return f"YE >= {_quote(year_from)}"
    return f"YE <= {_quote(year_to)}"


def _join_clauses(*clauses: str) -> str:
    return " AND ".join(c for c in clauses if c)


def _expression(
    groups: list[ConceptGroup],
    journals: list[str],
    year_from: str,
    year_to: str,
    field: str,
    match: str,
    max_keywords: int,
    core_only: bool,
) -> str:
    return _join_clauses(
        build_keyword_expression(groups, field, match, max_keywords, core_only),
        build_journal_filter(journals),
        build_date_clause(year_from, year_to),
    )


def build_ladder(
    groups: list[ConceptGroup],
    tiers: dict[str, list[str]] | None = None,
    year_from: str = "2015",
    year_to: str = "",
    field: str = "SU",
    match: str = "%=",
    max_keywords: int = 8,
) -> dict[str, str]:
    """返回 L1–L4 四档专业检索式。"""
    t = tiers if tiers is not None else load_journal_tiers()
    return {
        "L1": _expression(groups, t.get("tier1", []), year_from, year_to, field, match, max_keywords, False),
        "L2": _expression(groups, t.get("tier2", []), year_from, year_to, field, match, max_keywords, False),
        "L3": _expression(groups, t.get("tier1", []), year_from, year_to, field, match, max_keywords, True),
        "L4": _expression(groups, t.get("tier2", []), year_from, year_to, field, match, max_keywords, True),
    }


def extract_level_expression(markdown: str, level: str) -> str:
    level = level.upper()
    if level not in VALID_LEVELS:
        raise ValueError(f"无效 level={level}，可选 {', '.join(VALID_LEVELS)}")
    pattern = re.compile(
        rf"^##\s+{re.escape(level)}\b.*?\n+```(?:\w+)?\n(.*?)\n```",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(markdown)
    if not m:
        raise ValueError(f"search.md 中找不到 {level} 代码块")
    return m.group(1).strip()


def validate_tiered_expression(expression: str) -> None:
    if "LY" not in expression or "LY =" not in expression:
        raise ValueError("分级检索要求表达式含 `LY = (...)` 期刊过滤")


def _concept_table(groups: list[ConceptGroup], max_keywords: int) -> str:
    lines = [
        "| Group | Keywords (selected for search) |",
        "|-------|--------------------------------|",
    ]
    for g in groups:
        lines.append(f"| {g.label}: {g.name} | {', '.join(g.keywords[:max_keywords])} |")
    return "\n".join(lines)


def _dropped_groups(groups: list[ConceptGroup]) -> str:
    dropped = groups[2:]
    if not dropped:
        return "None"
    return ", ".join(f"{g.label} ({g.name})" for g in dropped)


def keywords_md_from_groups(topic: str, groups: list[ConceptGroup]) -> str:
    """Agent 若只传 JSON 概念组，落盘为可编辑的 keywords.md 骨架。"""
    lines = [
        f"# Keywords: {topic}",
        "",
        f"> Generated on {date.today().isoformat()}. Concept groups provided by agent; review before use.",
        "",
        "## Concept groups / 概念分组",
        "",
    ]
    for g in groups:
        lines.append(f"### {g.label}: {g.name}")
        lines.append(f"中文: {', '.join(g.keywords)}")
        lines.append("")
    lines.append("## Flat list (copy-paste ready)")
    for g in groups:
        for kw in g.keywords:
            lines.append(kw)
    lines.append("")
    return "\n".join(lines)


def build_markdown(
    topic: str,
    keywords_path: str | Path,
    groups: list[ConceptGroup],
    tiers: dict[str, list[str]] | None = None,
    year_from: str = "2015",
    year_to: str = "",
    range_label: str = "",
    field: str = "SU",
    match: str = "%=",
    max_keywords: int = 8,
    num: int = 30,
) -> str:
    t = tiers if tiers is not None else load_journal_tiers()
    ladder = build_ladder(groups, t, year_from, year_to, field, match, max_keywords)
    range_label = range_label or f"{year_from or 'any'}_{year_to or date.today().year}"
    keywords_path = Path(keywords_path)
    date_text = build_date_clause(year_from, year_to) or "不限年份"

    return f"""# CNKI Search: {topic}

> Generated on {date.today().isoformat()} from {keywords_path.as_posix()}
> Journal tiers: acq/data/cnki_journal_tiers.json
> Date range: {date_text}
> Search field: {field} {match}

## Concept Groups Used

{_concept_table(groups, max_keywords)}

## L1 — 精准检索 (Tier 1 顶刊, all concept groups)

```
{ladder['L1']}
```

## L2 — 核心检索 (Tier 2 期刊, all concept groups)

```
{ladder['L2']}
```

## L3 — 扩展检索 (Tier 1 顶刊, core concept groups only)

> Dropped groups: {_dropped_groups(groups)}

```
{ladder['L3']}
```

## L4 — 探索检索 (Tier 2 期刊, all concept groups only if ≤2 groups else core)

```
{ladder['L4']}
```

## Usage (Gleaner CLI)

1. 先 `python gleaner_cli.py prepare`（本文件即其产物）
2. 再 `python gleaner_cli.py cnki-list --level L1 --search-md 本路径 --num {num}`
3. TOTAL 够用则 `python gleaner_cli.py cnki --level L1 --search-md 本路径 --num {num}`
4. 结果太少则升到 L2 → L3 → L4
"""


def prepare_search(
    topic: str,
    concept_groups: str | list | dict,
    *,
    workspace_root: str | Path,
    year_from: str = "2015",
    year_to: str = "",
    range_label: str = "",
    max_keywords: int = 8,
    field: str = "SU",
    match: str = "%=",
    num: int = 30,
    tiers_path: str | Path | None = None,
) -> dict[str, Any]:
    """写 keywords.md + search.md，返回路径与 L1–L4 表达式。"""
    root = Path(workspace_root)
    groups = parse_concept_groups_json(concept_groups)
    tiers = load_journal_tiers(tiers_path)
    range_label = range_label or f"{year_from or 'any'}_{year_to or date.today().year}"

    topic_dir = root / "keyword_workspace" / topic
    kw_path = topic_dir / "keywords.md"
    search_path = topic_dir / range_label / "search.md"
    topic_dir.mkdir(parents=True, exist_ok=True)
    search_path.parent.mkdir(parents=True, exist_ok=True)

    # 完整 keywords.md 原样落盘；否则从解析后的概念组生成骨架
    if (
        isinstance(concept_groups, str)
        and concept_groups.lstrip().startswith("#")
        and "中文:" in concept_groups
    ):
        kw_path.write_text(concept_groups, encoding="utf-8")
    else:
        kw_path.write_text(keywords_md_from_groups(topic, groups), encoding="utf-8")

    md = build_markdown(
        topic=topic,
        keywords_path=kw_path.relative_to(root) if kw_path.is_relative_to(root) else kw_path,
        groups=groups,
        tiers=tiers,
        year_from=year_from,
        year_to=year_to,
        range_label=range_label,
        field=field,
        match=match,
        max_keywords=max_keywords,
        num=num,
    )
    search_path.write_text(md, encoding="utf-8")
    ladder = build_ladder(groups, tiers, year_from, year_to, field, match, max_keywords)

    return {
        "topic": topic,
        "range_label": range_label,
        "keywords_md": str(kw_path),
        "search_md": str(search_path),
        "tier_counts": tier_counts(tiers),
        "concept_groups": [
            {"label": g.label, "name": g.name, "keywords": g.keywords[:max_keywords]}
            for g in groups
        ],
        "levels": ladder,
        "recommended_level": "L1",
        "next": (
            f'python gleaner_cli.py cnki-list --level L1 --search-md "{search_path}" --num {num}；'
            f'够用再 cnki --level L1；结果少再 L2/L3/L4'
        ),
    }
