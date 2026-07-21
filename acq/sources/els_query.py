# acq/sources/els_query.py —— ScienceDirect 专业检索构建 + 白名单选刊（纯逻辑，无网络）
import json
from pathlib import Path

_DEFAULT_TIERS = Path(__file__).resolve().parent.parent / "data" / "intl_journal_tiers.json"


def _term(t: str) -> str:
    """多词词组加引号，单词原样。"""
    t = t.strip()
    return f'"{t}"' if " " in t else t


def build_qs(groups: list) -> str:
    """概念组 -> SD qs 布尔式：组内 OR、组间 AND。

    groups: [["digital economy","digitalization"], ["innovation","patent"]]
        -> '("digital economy" OR "digitalization") AND ("innovation" OR "patent")'
    空词/空组自动跳过；单组单词不加括号。
    """
    parts = []
    for g in groups:
        terms = [_term(t) for t in g if t and t.strip()]
        if not terms:
            continue
        parts.append(terms[0] if len(terms) == 1 else "(" + " OR ".join(terms) + ")")
    return " AND ".join(parts)


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
