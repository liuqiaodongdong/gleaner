from acq.sources.els_query import build_qs, load_tiers, select_journals


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
