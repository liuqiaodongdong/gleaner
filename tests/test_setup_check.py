import json
import pytest
from acq import setup_check
from acq.cnki_session import mark_institution_session


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(setup_check, "ROOT", tmp_path)
    monkeypatch.setattr(setup_check, "COOKIES_FILE", tmp_path / "cookies.json")
    for key in ["ACQ_PROXY", "CJY_USER", "CJY_PASS", "CJY_SOFTID", "ELSEVIER_API_KEY"]:
        monkeypatch.delenv(key, raising=False)
    return tmp_path


def test_missing_institution_login_has_only_cnki_blocker(isolated):
    result = setup_check.check_setup()
    assert set(result["lines"]) == {"cnki"}
    assert not result["ok"]
    assert [b["id"] for b in result["blockers"]] == ["institution_session"]
    assert setup_check.preflight("cnki")["error"] == "setup_incomplete"


def test_institution_session_ready_without_proxy_or_cjy(isolated):
    cookie = isolated / "cookies.json"
    cookie.write_text('[{"name":"session","value":"test"}]', encoding="utf-8")
    mark_institution_session(isolated, cookie)
    result = setup_check.check_setup()
    assert result["ok"] and result["lines"]["cnki"]["proxy"]["mode"] == "direct"
    assert result["lines"]["cnki"]["chaojiying"]["optional"]
    assert setup_check.preflight("cnki") is None
    assert setup_check.preflight("cnki-list") is None


def test_cookie_without_confirmed_institution_marker_is_not_ready(isolated):
    (isolated / "cookies.json").write_text('[{"name":"session","value":"test"}]', encoding="utf-8")
    assert not setup_check.check_setup()["ok"]


def test_invalid_optional_proxy_blocks_with_clear_error(isolated, monkeypatch):
    monkeypatch.setenv("ACQ_PROXY", "http://127.0.0.1:PORT")
    assert "proxy" in {b["id"] for b in setup_check.check_setup()["blockers"]}


@pytest.mark.parametrize("line", ["intl", "elsevier", "els"])
def test_removed_sources_rejected(isolated, line):
    assert setup_check.preflight(line)["error"] == "unknown_line"
