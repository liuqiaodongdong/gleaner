import pytest
from acq.sources.els_query import (
    build_qs,
    clamp_show,
    load_tiers,
    normalize_els_query,
    parse_els_concept_groups,
    select_journals,
)


def test_build_qs_single_group_single_term():
    assert build_qs([["tax"]]) == "tax"


def test_build_qs_quotes_only_multiword():
    # 多词词组加引号(当短语)，单词裸用(允许 SD 词干扩展，召回更好)
    assert build_qs([["digital economy", "digitalization"]]) == \
        '("digital economy" OR digitalization)'


def test_build_qs_and_across_groups():
    qs = build_qs([["digital economy", "digitalization"], ["innovation", "patent"]])
    assert qs == '("digital economy" OR digitalization) AND (innovation OR patent)'


def test_build_qs_skips_empty():
    assert build_qs([["tax"], [], ["  "]]) == "tax"


def test_normalize_uppercases_bool_and_strips_tak():
    assert normalize_els_query('tak("supply chain") and tak(green transition)') == \
        '"supply chain" AND green transition'


def test_normalize_rejects_cjk_only():
    with pytest.raises(ValueError, match="英文"):
        normalize_els_query("绿色转型 AND 供应链")


def test_normalize_rejects_empty():
    with pytest.raises(ValueError, match="空"):
        normalize_els_query("   ")


def test_clamp_show_snaps_to_allowed():
    assert clamp_show(8) == 10
    assert clamp_show(10) == 10
    assert clamp_show(25) == 25
    assert clamp_show(200) == 100


def test_parse_els_concept_groups_json():
    groups = parse_els_concept_groups(
        '[{"name":"sc","keywords":["supply chain","供应商"]},'
        '{"name":"gt","keywords":["green transition"]}]'
    )
    assert groups == [["supply chain"], ["green transition"]]


def test_parse_els_concept_groups_rejects_chinese_only():
    with pytest.raises(ValueError, match="英文"):
        parse_els_concept_groups('[{"name":"A","keywords":["供应链","绿色转型"]}]')


def test_parse_els_markdown_english_lines():
    md = """### A: firms
英文: listed firm, listed company
### B: green
English: green transition, green innovation
"""
    assert parse_els_concept_groups(md) == [
        ["listed firm", "listed company"],
        ["green transition", "green innovation"],
    ]


def test_select_journals_tier_filter():
    tiers = {"tier1": [{"name": "A", "issn": "1", "level": "x", "tier": 1}],
             "tier2": [{"name": "B", "issn": "2", "level": "y", "tier": 2}],
             "tier3": [{"name": "C", "issn": "3", "level": "z", "tier": 3}]}
    assert [j["name"] for j in select_journals(tiers, "1")] == ["A"]
    assert {j["name"] for j in select_journals(tiers, "1+2")} == {"A", "B"}
    assert len(select_journals(tiers, "1+2+3")) == 3


def test_load_tiers_real_file():
    d = load_tiers()
    assert d["meta"]["count"] >= 80
