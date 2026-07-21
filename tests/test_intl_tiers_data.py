import json
from pathlib import Path

TIERS = Path(__file__).parent.parent / "acq" / "data" / "intl_journal_tiers.json"


def test_tier_file_shape():
    d = json.loads(TIERS.read_text(encoding="utf-8"))
    assert set(d) >= {"meta", "tier1", "tier2", "tier3"}
    total = len(d["tier1"]) + len(d["tier2"]) + len(d["tier3"])
    assert total == d["meta"]["count"] >= 80  # 实测 96，留余量


def test_known_top_journals_present():
    d = json.loads(TIERS.read_text(encoding="utf-8"))
    names = {j["name"] for t in ("tier1", "tier2", "tier3") for j in d[t]}
    issns = {j["issn"] for t in ("tier1", "tier2", "tier3") for j in d[t]}
    assert "0304-4076" in issns  # Journal of Econometrics
    assert any("Public Economics" in n for n in names)


def test_every_journal_has_required_fields():
    d = json.loads(TIERS.read_text(encoding="utf-8"))
    for t in ("tier1", "tier2", "tier3"):
        for j in d[t]:
            assert j["name"] and j["issn"] and j["level"]
            assert j["tier"] in (1, 2, 3)
