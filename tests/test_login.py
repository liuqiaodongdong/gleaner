# tests/test_login.py —— 登录录 cookie：过验证立刻写盘，无拼图不打码
from types import SimpleNamespace

import login


class _FakePage:
    def __init__(self, url="https://kns.cnki.net/kns8s/defaultresult/index"):
        self.url = url
        self.context = SimpleNamespace(pages=[])
        self.context.pages.append(self)


def test_try_auto_solve_calls_solve_slider(monkeypatch):
    calls = []
    monkeypatch.setattr(login, "apply_login_credentials", lambda: None)

    def fake_solve(page, max_attempts=2):
        calls.append((page, max_attempts))
        return True

    monkeypatch.setattr("captcha.solve_slider_captcha", fake_solve)
    page = _FakePage()
    assert login.try_auto_solve_login_captcha(page) is True
    assert calls == [(page, 2)]


def test_try_auto_solve_missing_cjy_falls_back(monkeypatch):
    monkeypatch.setattr(login, "apply_login_credentials", lambda: None)

    def boom(_page, max_attempts=2):
        raise RuntimeError("超级鹰账号未配置：请设置环境变量 CJY_USER / CJY_PASS / CJY_SOFTID")

    monkeypatch.setattr("captcha.solve_slider_captcha", boom)
    assert login.try_auto_solve_login_captcha(_FakePage()) is False


def test_try_auto_solve_still_present_returns_false(monkeypatch):
    monkeypatch.setattr(login, "apply_login_credentials", lambda: None)
    monkeypatch.setattr("captcha.solve_slider_captcha", lambda page, max_attempts=2: False)
    assert login.try_auto_solve_login_captcha(_FakePage()) is False


def test_still_on_captcha_ignores_verify_url(monkeypatch):
    monkeypatch.setattr("captcha.captcha_blocks_cookie_write", lambda page: False)
    assert (
        login._still_on_captcha(_FakePage(), "https://kns.cnki.net/verify/xxx")
        is False
    )
    monkeypatch.setattr("captcha.captcha_blocks_cookie_write", lambda page: True)
    assert (
        login._still_on_captcha(_FakePage(), "https://kns.cnki.net/kns8s/defaultresult/index")
        is True
    )


def test_cjy_reads_process_env_after_dotenv(monkeypatch):
    monkeypatch.delenv("CJY_USER", raising=False)
    monkeypatch.delenv("CJY_PASS", raising=False)
    monkeypatch.delenv("CJY_SOFTID", raising=False)
    import captcha
    monkeypatch.setattr(captcha, "CHAOJIYING_USER", "")
    monkeypatch.setattr(captcha, "CHAOJIYING_PASS", "")
    monkeypatch.setattr(captcha, "CHAOJIYING_SOFTID", "")
    try:
        captcha._require_cjy()
        raised = False
    except RuntimeError:
        raised = True
    assert raised
    monkeypatch.setenv("CJY_USER", "u")
    monkeypatch.setenv("CJY_PASS", "p")
    monkeypatch.setenv("CJY_SOFTID", "1")
    captcha._require_cjy()


def test_load_existing_session_refuses_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(login, "COOKIES_FILE", tmp_path / "cookies.json")
    monkeypatch.delenv("ACQ_ALLOW_COLD_LOGIN", raising=False)
    added = []

    class Ctx:
        def add_cookies(self, cookies):
            added.extend(cookies)

    try:
        login.load_existing_session(Ctx())
        raised = False
    except SystemExit as e:
        raised = True
        assert "拒绝冷启动" in str(e)
    assert raised
    assert added == []


def test_load_existing_session_warms_from_file(tmp_path, monkeypatch):
    ck = tmp_path / "cookies.json"
    ck.write_text(
        '[{"name":"Ecp_ClientId","value":"x","domain":".cnki.net","path":"/"}]',
        encoding="utf-8",
    )
    monkeypatch.setattr(login, "COOKIES_FILE", ck)
    added = []

    class Ctx:
        def add_cookies(self, cookies):
            added.extend(cookies)

    n = login.load_existing_session(Ctx())
    assert n == 1
    assert added[0]["name"] == "Ecp_ClientId"


def test_persist_warm_cookies_skips_when_widget(tmp_path, monkeypatch):
    ck = tmp_path / "cookies.json"
    ck.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(login, "COOKIES_FILE", ck)
    monkeypatch.setattr(login, "_still_on_captcha", lambda page, url: True)
    page = _FakePage("https://kns.cnki.net/verify")

    class Ctx:
        def cookies(self):
            return [{"name": "bad"}]

    assert login.persist_warm_cookies(Ctx(), page) is False
    assert ck.read_text(encoding="utf-8") == "[]"


def test_persist_writes_on_verify_url_if_passed(tmp_path, monkeypatch):
    """过了滑块但地址还带 /verify，必须立刻写盘。"""
    ck = tmp_path / "cookies.json"
    ck.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(login, "COOKIES_FILE", ck)
    monkeypatch.setattr(login, "_still_on_captcha", lambda page, url: False)
    page = _FakePage("https://kns.cnki.net/verify/slider")

    class Ctx:
        def cookies(self):
            return [{"name": "ok", "value": "1"}]

    assert login.persist_warm_cookies(Ctx(), page) is True
    assert "ok" in ck.read_text(encoding="utf-8")


def test_find_handle_in_frames_searches_iframe():
    import captcha

    class El:
        def is_visible(self):
            return True

    handle = El()

    class Frame:
        def query_selector(self, sel):
            if sel == ".verify-move-block":
                return handle
            return None

    class Page:
        frames = []

        def query_selector(self, sel):
            return None

    page = Page()
    page.frames = [page, Frame()]
    assert captcha._find_handle_in_frames(page) is handle
