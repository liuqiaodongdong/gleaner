"""CNKI 分级建式纯逻辑测试。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from acq.sources import cnki_query as cq

ROOT = Path(__file__).resolve().parent.parent
TIERS = ROOT / "acq" / "data" / "cnki_journal_tiers.json"


def test_tiers_file_exists_and_counts():
    assert TIERS.is_file()
    counts = cq.tier_counts()
    assert counts["tier1"] >= 10
    assert counts["tier2"] >= 10
    assert counts["tier3"] >= 50


def test_parse_json_groups():
    groups = cq.parse_concept_groups_json(
        [{"name": "数字经济", "keywords": ["数字经济", "数字化", "数据要素"]},
         {"name": "TFP", "keywords": ["全要素生产率", "TFP"]}]
    )
    assert [g.name for g in groups] == ["数字经济", "TFP"]
    assert groups[0].keywords[0] == "数字经济"


def test_parse_markdown_groups():
    md = """# Keywords
## Concept groups / 概念分组
### A: 数字经济
中文: 数字经济, 数字化, 平台经济
English: digital economy
"""
    groups = cq.parse_concept_groups(md)
    assert groups[0].name == "数字经济"
    assert "平台经济" in groups[0].keywords
    assert "digital economy" not in groups[0].keywords


def test_ladder_has_ly_and_levels():
    groups = cq.parse_concept_groups_json(
        [{"name": "数字经济", "keywords": ["数字经济", "数字化"]}]
    )
    ladder = cq.build_ladder(groups, year_from="2020", year_to="2026", max_keywords=5)
    for lv in cq.VALID_LEVELS:
        assert lv in ladder
        cq.validate_tiered_expression(ladder[lv])
        assert "SU %=" in ladder[lv]
        assert "YE >= '2020'" in ladder[lv]
        assert "YE <= '2026'" in ladder[lv]
    assert "LY = (" in ladder["L1"]
    # L1 uses tier1 journals
    assert "经济研究" in ladder["L1"] or "管理世界" in ladder["L1"]


def test_extract_level_from_markdown(tmp_path: Path):
    groups = cq.parse_concept_groups_json(
        '[{"name":"x","keywords":["数字经济"]}]'
    )
    md = cq.build_markdown(
        topic="t",
        keywords_path="keyword_workspace/t/keywords.md",
        groups=groups,
        year_from="2015",
        max_keywords=3,
    )
    expr = cq.extract_level_expression(md, "L2")
    cq.validate_tiered_expression(expr)
    with pytest.raises(ValueError):
        cq.extract_level_expression(md, "L9")


def test_prepare_search_writes_files(tmp_path: Path):
    result = cq.prepare_search(
        topic="数字经济测试",
        concept_groups=json.dumps(
            [{"name": "数字经济", "keywords": ["数字经济", "数字化"]}],
            ensure_ascii=False,
        ),
        workspace_root=tmp_path,
        year_from="2018",
        max_keywords=4,
        num=10,
    )
    assert "search_md" in result
    assert Path(result["keywords_md"]).is_file()
    assert Path(result["search_md"]).is_file()
    assert "L1" in result["levels"]
    text = Path(result["search_md"]).read_text(encoding="utf-8")
    assert "## L1" in text and "LY = (" in text
    expr = cq.extract_level_expression(text, "L1")
    cq.validate_tiered_expression(expr)


def test_validate_rejects_no_ly():
    with pytest.raises(ValueError):
        cq.validate_tiered_expression("SU %= '数字经济'")
