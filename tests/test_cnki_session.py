"""验证机构会话隔离、批间不重录和文件只读规则。"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import browser
import gleanera_cli
from acq.cnki_session import mark_institution_session, resolve_session_mode


def test_marker_binds_cookie_contents_and_does_not_fall_back_when_changed(tmp_path):
    cookie = tmp_path / "cookies.json"
    cookie.write_text('[{"name":"session","value":"one"}]', encoding="utf-8")
    assert resolve_session_mode(tmp_path) == "institution"
    mark_institution_session(tmp_path, cookie)
    assert resolve_session_mode(tmp_path) == "institution"
    cookie.write_text('[{"name":"session","value":"two"}]', encoding="utf-8")
    with pytest.raises(ValueError, match="主动运行"):
        resolve_session_mode(tmp_path)
    with pytest.raises(ValueError):
        resolve_session_mode(tmp_path, "legacy")


def test_corrupt_marker_stops_instead_of_calling_legacy_login(tmp_path):
    from acq.cnki_session import session_path
    marker = session_path(tmp_path)
    marker.parent.mkdir(parents=True)
    marker.write_text("broken", encoding="utf-8")
    with pytest.raises(ValueError, match="机构会话不可用"):
        resolve_session_mode(tmp_path)


def test_institution_browser_save_keeps_cookie_bytes_unchanged(tmp_path, monkeypatch):
    cookie = tmp_path / "cookies.json"
    cookie.write_bytes(b"original-institution-session")
    monkeypatch.setattr(browser, "COOKIES_FILE", cookie)
    monkeypatch.setenv("ACQ_SESSION_MODE", "institution")
    context = SimpleNamespace(cookies=lambda: pytest.fail("不能重新读取并覆盖机构 cookies"))
    browser._save_cookies(context)
    assert cookie.read_bytes() == b"original-institution-session"


def test_legacy_environment_cannot_overwrite_institution_cookie(tmp_path, monkeypatch):
    cookie = tmp_path / "cookies.json"
    cookie.write_text("original", encoding="utf-8")
    monkeypatch.setattr(browser, "COOKIES_FILE", cookie)
    monkeypatch.setenv("ACQ_SESSION_MODE", "legacy")
    monkeypatch.setattr(browser, "_any_page_blocks_cookie_write", lambda context: False)
    browser._save_cookies(SimpleNamespace(cookies=lambda: [{"name": "new", "value": "x"}]))
    assert cookie.read_text(encoding="utf-8") == "original"


@pytest.mark.parametrize("mode_args", [[], ["--session-mode", "institution"]])
def test_institution_multibatch_has_zero_login_processes(tmp_path, monkeypatch, capsys, mode_args):
    monkeypatch.setenv("GLEANERA_ROOT", str(tmp_path))
    cookie = tmp_path / "cookies.json"
    cookie.write_text('[{"name":"session","value":"one"}]', encoding="utf-8")
    before = cookie.read_bytes()
    mark_institution_session(tmp_path, cookie)
    calls = []

    def run(cmd, *, cwd, log_path, env=None, timeout=None, append=False):
        assert "login.py" not in " ".join(map(str, cmd))
        assert env["ACQ_SESSION_MODE"] == "institution"
        params = json.loads((tmp_path / "corpus/_cli_cnki_params.json").read_text(encoding="utf-8"))
        calls.append(params["num"])
        papers = Path(params["out"]) / "papers"
        papers.mkdir(parents=True, exist_ok=True)
        start = len(list(papers.glob("*.pdf")))
        for i in range(params["num"]):
            (papers / f"{start+i}.pdf").write_bytes(b"%PDF-test")
        return 0

    with patch("acq.setup_check.preflight", return_value=None), patch("gleanera_cli.run_logged", side_effect=run), patch("gleanera_cli._try_merge_corpus", return_value=""):
        code = gleanera_cli.main(["cnki", "--query", "x", "--out-name", "institution_test", "--num", "1", "--until", "3", *mode_args])
    result = json.loads(capsys.readouterr().out)
    assert code == 0 and result["until_reached"]
    assert calls == [1, 1, 1]
    assert result["login_between"] == 0 and result["session_mode"] == "institution"
    assert cookie.read_bytes() == before


def test_institution_no_progress_stops_without_login_and_preserves_session(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANERA_ROOT", str(tmp_path))
    cookie = tmp_path / "cookies.json"
    cookie.write_text('[{"name":"session","value":"one"}]', encoding="utf-8")
    before = cookie.read_bytes()
    mark_institution_session(tmp_path, cookie)
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return 2

    with patch("acq.setup_check.preflight", return_value=None), patch("gleanera_cli.run_logged", side_effect=run), patch("gleanera_cli._try_merge_corpus", return_value=""):
        code = gleanera_cli.main(["cnki", "--query", "x", "--out-name", "failed", "--until", "3"])
    result = json.loads(capsys.readouterr().out)
    assert code == 1 and not result["until_reached"]
    assert len(calls) == 1 and "login.py" not in " ".join(map(str, calls[0]))
    assert result["login_between"] == 0 and "login.py --institution" in result["next_action"]
    assert cookie.read_bytes() == before


def test_changed_institution_cookie_stops_before_any_subprocess(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANERA_ROOT", str(tmp_path))
    cookie = tmp_path / "cookies.json"
    cookie.write_text("[]", encoding="utf-8")
    mark_institution_session(tmp_path, cookie)
    cookie.write_text("different", encoding="utf-8")
    with patch("gleanera_cli.run_logged") as run:
        code = gleanera_cli.main(["cnki", "--query", "x", "--until", "2"])
    assert code == 1 and json.loads(capsys.readouterr().out)["error"] == "institution_session_invalid"
    run.assert_not_called()


def test_failed_session_marker_write_rolls_back_cookie_replacement(tmp_path, monkeypatch):
    import login
    cookie = tmp_path / "cookies.json"
    original = b'[{"name":"session","value":"old"}]'
    cookie.write_bytes(original)
    mark_institution_session(tmp_path, cookie)
    monkeypatch.setattr(login, "COOKIES_FILE", cookie)
    monkeypatch.setattr(login, "institution_name", lambda page: "测试大学")
    monkeypatch.setattr(login, "institution_captcha_visible", lambda page: False)

    def fail(*args):
        raise PermissionError("marker locked")

    monkeypatch.setattr("acq.cnki_session.mark_institution_session", fail)
    context = SimpleNamespace(cookies=lambda: [{"name": "session", "value": "new", "domain": ".cnki.net"}])
    assert not login.persist_institution_cookies(context, SimpleNamespace())
    assert cookie.read_bytes() == original
    assert resolve_session_mode(tmp_path) == "institution"


def test_invalid_institution_status_marks_cnki_not_ready(tmp_path, monkeypatch, capsys):
    cookie = tmp_path / "cookies.json"
    cookie.write_text("original", encoding="utf-8")
    mark_institution_session(tmp_path, cookie)
    cookie.write_text("changed", encoding="utf-8")
    payload = {"ok": True, "lines": {"cnki": {"ready": True, "cookies": {"ok": True}}, "elsevier": {"ready": False}}}
    with patch("acq.setup_check.check_setup", return_value=payload):
        gleanera_cli.cmd_status(tmp_path)
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False and result["ready_any_line"] is False
    assert result["lines"]["cnki"]["ready"] is False
    assert result["lines"]["cnki"]["cookies"]["status"] == "session_invalid"
