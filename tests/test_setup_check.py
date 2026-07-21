# tests/test_setup_check.py —— 部署检查纯逻辑
import json
import acq_mcp
from acq import setup_check


def test_setup_status_registered():
    assert hasattr(acq_mcp, "setup_status")
    import inspect
    assert inspect.signature(acq_mcp.setup_status).return_annotation is inspect.Signature.empty


def test_check_setup_shape(monkeypatch, tmp_path):
    monkeypatch.delenv("CJY_USER", raising=False)
    monkeypatch.delenv("CJY_PASS", raising=False)
    monkeypatch.delenv("CJY_SOFTID", raising=False)
    monkeypatch.delenv("ELSEVIER_API_KEY", raising=False)
    monkeypatch.delenv("ACQ_PROXY", raising=False)
    # 避开本机真实 cookies/key 路径：临时改 ROOT 相关常量
    monkeypatch.setattr(setup_check, "COOKIES_FILE", tmp_path / "cookies.json")
    monkeypatch.setattr(setup_check, "ELS_KEY_FILE", tmp_path / ".elsevier_key")
    monkeypatch.setattr(setup_check, "CARSI_STATE", tmp_path / "carsi_state.json")
    # 伪装无系统代理
    monkeypatch.setattr(setup_check, "_proxy_detected", lambda: (False, "no proxy"))

    s = setup_check.check_setup()
    assert "next_steps_for_user" in s
    assert "blockers" in s
    assert s["lines"]["cnki"]["cnki_collect_ready"] is False
    assert s["lines"]["elsevier"]["ready"] is False
    assert s["lines"]["intl"]["ready"] is True
    # 应引导超级鹰与 Elsevier
    ids = {b["id"] for b in s["blockers"]}
    assert "chaojiying" in ids
    assert "elsevier_key" in ids
    assert any("Agent" in x for x in s["next_steps_for_user"])
    els_b = next(b for b in s["blockers"] if b["id"] == "elsevier_key")
    assert "dev.elsevier.com" in els_b["url"]
    assert els_b.get("apply_steps")
    assert any("Create API Key" in step for step in els_b["apply_steps"])
    assert s["lines"]["elsevier"]["api_key"].get("apply_steps")
    # 不泄露密钥字段
    blob = json.dumps(s)
    assert "utuf" not in blob


def test_check_setup_ready_when_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("CJY_USER", "u")
    monkeypatch.setenv("CJY_PASS", "p")
    monkeypatch.setenv("CJY_SOFTID", "1")
    monkeypatch.setenv("ELSEVIER_API_KEY", "K" * 16)
    monkeypatch.setenv("ACQ_PROXY", "http://127.0.0.1:9")
    ck = tmp_path / "cookies.json"
    ck.write_text(json.dumps([{"name": "a", "value": "b", "domain": ".cnki.net"}]), encoding="utf-8")
    monkeypatch.setattr(setup_check, "COOKIES_FILE", ck)
    monkeypatch.setattr(setup_check, "ELS_KEY_FILE", tmp_path / "no_key")
    monkeypatch.setattr(setup_check, "CARSI_STATE", tmp_path / "no_carsi")

    s = setup_check.check_setup()
    assert s["lines"]["cnki"]["cnki_collect_ready"] is True
    assert s["lines"]["elsevier"]["ready"] is True
    assert s["ok"] is True
    assert s["lines"]["elsevier"]["api_key"]["via"] == "env"
    # 不回显 key
    assert "KKKK" not in json.dumps(s)


def test_preflight_blocks_cnki_and_els(monkeypatch, tmp_path):
    monkeypatch.delenv("CJY_USER", raising=False)
    monkeypatch.delenv("CJY_PASS", raising=False)
    monkeypatch.delenv("CJY_SOFTID", raising=False)
    monkeypatch.delenv("ELSEVIER_API_KEY", raising=False)
    monkeypatch.delenv("ACQ_PROXY", raising=False)
    monkeypatch.setattr(setup_check, "COOKIES_FILE", tmp_path / "cookies.json")
    monkeypatch.setattr(setup_check, "ELS_KEY_FILE", tmp_path / ".elsevier_key")
    monkeypatch.setattr(setup_check, "CARSI_STATE", tmp_path / "x")
    monkeypatch.setattr(setup_check, "_proxy_detected", lambda: (False, "no"))

    assert setup_check.preflight("cnki_collect")["error"] == "setup_incomplete"
    assert setup_check.preflight("elsevier")["error"] == "setup_incomplete"


def test_preflight_pass_when_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("CJY_USER", "u")
    monkeypatch.setenv("CJY_PASS", "p")
    monkeypatch.setenv("CJY_SOFTID", "1")
    monkeypatch.setenv("ELSEVIER_API_KEY", "KEY")
    monkeypatch.setenv("ACQ_PROXY", "http://127.0.0.1:9")
    monkeypatch.setattr(setup_check, "COOKIES_FILE", tmp_path / "c.json")
    monkeypatch.setattr(setup_check, "ELS_KEY_FILE", tmp_path / "k")
    monkeypatch.setattr(setup_check, "CARSI_STATE", tmp_path / "x")
    assert setup_check.preflight("cnki_collect") is None
    assert setup_check.preflight("elsevier") is None


def test_setup_status_mcp_json():
    raw = acq_mcp.setup_status()
    data = json.loads(raw)
    assert "next_steps_for_user" in data
    assert "lines" in data
