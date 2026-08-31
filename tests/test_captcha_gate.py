# tests/test_captcha_gate.py —— 过验证判定：无面板不打码，/verify URL 不挡写 cookie
from __future__ import annotations

import captcha


class _El:
    def __init__(self, visible=True):
        self._visible = visible

    def is_visible(self):
        return self._visible


class _Page:
    def __init__(self, url="", title="", body="", visible=None):
        self.url = url
        self._title = title
        self._body = body
        self._visible = visible or {}
        self.frames = []
        self.main_frame = self

    def title(self):
        return self._title

    def inner_text(self, _sel, timeout=1000):
        return self._body

    def query_selector(self, sel):
        if sel in self._visible:
            return self._visible[sel]
        for key, el in self._visible.items():
            if key in sel:
                return el
        return None

    def screenshot(self, **_kwargs):
        return b""


def test_has_pass_signal_search_box():
    page = _Page(
        url="https://kns.cnki.net/verify/xxx",
        visible={"input.search-input, input#txt_SearchText": _El()},
    )
    assert captcha._has_pass_signal(page) is True
    assert captcha._captcha_present(page) is False
    assert captcha.captcha_blocks_cookie_write(page) is False


def test_has_pass_signal_done_text():
    page = _Page(
        url="https://bar.cnki.net/foo",
        body="验证完成，已进入下载",
    )
    assert captcha._has_pass_signal(page) is True
    assert captcha.captcha_blocks_cookie_write(page) is False


def test_verify_url_without_widget_does_not_block_cookie():
    page = _Page(url="https://kns.cnki.net/verify/slider", title="安全验证")
    assert captcha._captcha_url_hint(page) is True
    assert captcha._captcha_widget_visible(page) is False
    assert captcha.captcha_blocks_cookie_write(page) is False


def test_widget_blocks_cookie_write():
    page = _Page(
        url="https://kns.cnki.net/kns8s/defaultresult/index",
        visible={".verify-img-panel": _El()},
    )
    assert captcha._captcha_widget_visible(page) is True
    assert captcha.captcha_blocks_cookie_write(page) is True


def test_solve_does_not_call_cjy_without_panel(monkeypatch):
    monkeypatch.setattr(captcha.time, "sleep", lambda _s: None)

    def boom(*_a, **_k):
        raise AssertionError("无面板不应调用超级鹰")

    monkeypatch.setattr(captcha, "_cjy_solve", boom)
    page = _Page(url="https://kns.cnki.net/verify/foo", title="安全验证")
    assert captcha.solve_slider_captcha(page) is False


def test_save_cookies_skips_when_widget(tmp_path, monkeypatch):
    import browser

    ck = tmp_path / "cookies.json"
    ck.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(browser, "COOKIES_FILE", ck)
    monkeypatch.setattr(browser, "_any_page_blocks_cookie_write", lambda _ctx: True)

    class Ctx:
        def cookies(self):
            return [{"name": "bad"}]

    browser._save_cookies(Ctx())
    assert ck.read_text(encoding="utf-8") == "[]"


def test_wait_for_captcha_skips_without_widget(monkeypatch):
    import scraper

    monkeypatch.setattr(scraper.time, "sleep", lambda _s: None)
    called = []

    def boom(_page, max_attempts=4):
        called.append(1)
        raise AssertionError("无拼图不应打码")

    monkeypatch.setattr("captcha.solve_slider_captcha", boom)
    page = _Page(url="https://kns.cnki.net/verify/x", title="安全验证")
    scraper.wait_for_captcha(page)
    assert called == []
