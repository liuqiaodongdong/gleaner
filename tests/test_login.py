# tests/test_login.py —— 登录录 cookie：过验证立刻写盘，无拼图不打码
from types import SimpleNamespace
import json

import login


class _FakePage:
    def __init__(self, url="https://kns.cnki.net/kns8s/defaultresult/index"):
        self.url = url
        self.context = SimpleNamespace(pages=[])
        self.context.pages.append(self)










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












def test_find_handle_in_frames_searches_iframe():
    import captcha

    class El:
        def is_visible(self):
            return True

        def bounding_box(self):
            return {"x": 10, "y": 10, "width": 100, "height": 100}

        def evaluate(self, _script):
            return True

    handle = El()

    class Frame:
        def query_selector(self, sel):
            if sel == ".verify-move-block":
                return handle
            return None

    class Page:
        viewport_size = {"width": 1920, "height": 1080}
        frames = []

        def query_selector(self, sel):
            return None

    page = Page()
    frame = Frame()
    frame.page = page
    page.frames = [page, frame]
    assert captcha._find_handle_in_frames(page) is handle


def test_institution_name_requires_visible_official_unit_component():
    class Element:
        def __init__(self, text, visible=True):
            self.text, self.visible = text, visible

        def is_visible(self):
            return self.visible

        def inner_text(self, **_kwargs):
            return self.text

    elements = [Element("机构登录"), Element("旧机构", visible=False)]
    page = SimpleNamespace(
        url="https://www.cnki.net/",
        locator=lambda selector: SimpleNamespace(all=lambda: elements),
    )
    assert login.institution_name(page) == ""
    elements.append(Element("测试大学"))
    assert login.institution_name(page) == "测试大学"
    for url in ("https://cnki.net.example.org/", "https://school.edu/", "http://www.cnki.net/"):
        page.url = url
        assert login.institution_name(page) == ""


def test_institution_save_filters_school_cookies_and_backs_up_old_session(tmp_path, monkeypatch):
    ck = tmp_path / "cookies.json"
    original = b'[{"name":"old","value":"old-session"}]'
    ck.write_bytes(original)
    monkeypatch.setattr(login, "COOKIES_FILE", ck)
    monkeypatch.setattr(login, "institution_name", lambda page: "测试大学")
    monkeypatch.setattr(login, "institution_captcha_visible", lambda page: False)
    context = SimpleNamespace(cookies=lambda: [
        {"name": "session", "value": "new", "domain": ".cnki.net"},
        {"name": "sso", "value": "school-secret", "domain": "school.edu"},
        {"name": "lookalike", "value": "x", "domain": "fakecnki.net"},
    ])
    assert login.persist_institution_cookies(context, _FakePage())
    assert [cookie["name"] for cookie in json.loads(ck.read_text("utf-8"))] == ["session"]
    backups = list((tmp_path / "acq" / "cookies" / "cnki").glob("cookies-*.json"))
    assert len(backups) == 1 and backups[0].read_bytes() == original


def test_institution_save_does_not_overwrite_before_login(tmp_path, monkeypatch):
    ck = tmp_path / "cookies.json"
    ck.write_text("old-session", encoding="utf-8")
    monkeypatch.setattr(login, "COOKIES_FILE", ck)
    monkeypatch.setattr(login, "institution_name", lambda page: "")
    assert not login.persist_institution_cookies(None, _FakePage())
    assert ck.read_text("utf-8") == "old-session"


def test_institution_save_does_not_overwrite_during_captcha(tmp_path, monkeypatch):
    ck = tmp_path / "cookies.json"
    ck.write_text("old-session", encoding="utf-8")
    monkeypatch.setattr(login, "COOKIES_FILE", ck)
    monkeypatch.setattr(login, "institution_name", lambda page: "测试大学")
    monkeypatch.setattr(login, "institution_captcha_visible", lambda page: True)
    assert not login.persist_institution_cookies(None, _FakePage())
    assert ck.read_text("utf-8") == "old-session"


def test_institution_atomic_replace_failure_preserves_original(tmp_path, monkeypatch):
    ck = tmp_path / "cookies.json"
    ck.write_text("old-session", encoding="utf-8")
    monkeypatch.setattr(login, "COOKIES_FILE", ck)
    monkeypatch.setattr(login, "institution_name", lambda page: "测试大学")
    monkeypatch.setattr(login, "institution_captcha_visible", lambda page: False)

    def fail_replace(self, target):
        raise PermissionError("locked")

    monkeypatch.setattr(login.Path, "replace", fail_replace)
    context = SimpleNamespace(cookies=lambda: [{"name": "session", "value": "new", "domain": ".cnki.net"}])
    assert not login.persist_institution_cookies(context, _FakePage())
    assert ck.read_text("utf-8") == "old-session"
    assert not list(tmp_path.glob("*.tmp"))


def test_institution_wait_closed_window_never_saves(monkeypatch):
    monkeypatch.setattr(login, "persist_institution_cookies", lambda *args: (_ for _ in ()).throw(AssertionError("不能保存")))
    assert not login.wait_for_institution_login(SimpleNamespace(pages=[]), None, timeout_sec=1)


def test_institution_wait_requires_stable_identity_before_save(monkeypatch):
    clock = [0.0]
    page = SimpleNamespace(
        is_closed=lambda: False,
        wait_for_timeout=lambda ms: clock.__setitem__(0, clock[0] + ms / 1000),
    )
    monkeypatch.setattr(login.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(login, "institution_name", lambda p: "测试大学" if clock[0] >= 1 else "")
    saves = []
    monkeypatch.setattr(login, "persist_institution_cookies", lambda ctx, p: saves.append(clock[0]) or True)
    assert login.wait_for_institution_login(SimpleNamespace(pages=[page]), page, timeout_sec=6)
    assert saves == [4.0]


def test_institution_wait_retries_failed_save_without_closing_login(monkeypatch):
    clock = [0.0]
    page = SimpleNamespace(
        is_closed=lambda: False,
        wait_for_timeout=lambda ms: clock.__setitem__(0, clock[0] + ms / 1000),
    )
    monkeypatch.setattr(login.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(login, "institution_name", lambda p: "测试大学")
    saves = []

    def save(context, candidate):
        saves.append(clock[0])
        return len(saves) >= 2

    monkeypatch.setattr(login, "persist_institution_cookies", save)
    assert login.wait_for_institution_login(SimpleNamespace(pages=[page]), page, timeout_sec=8)
    assert saves == [3.0, 6.0]


def test_institution_save_ignores_homepage_carousel_handle(tmp_path, monkeypatch):
    monkeypatch.setattr(login, "COOKIES_FILE", tmp_path / "cookies.json")
    monkeypatch.setattr(login, "institution_name", lambda page: "测试大学")
    monkeypatch.setattr(login, "institution_captcha_visible", lambda page: False)
    monkeypatch.setattr("captcha._find_handle_in_frames", lambda page: object())
    context = SimpleNamespace(cookies=lambda: [{"name": "session", "value": "new", "domain": ".cnki.net"}])
    assert login.persist_institution_cookies(context, _FakePage())


def test_institution_captcha_ignores_offscreen_and_transparent_panels():
    page = SimpleNamespace(viewport_size={"width": 1920, "height": 1080})
    box = {"x": -9999, "y": 100, "width": 300, "height": 200}
    element = SimpleNamespace(
        is_visible=lambda: True,
        bounding_box=lambda: box,
        evaluate=lambda expression: False,
    )
    assert not login._visible_in_viewport(element, page)
    box["x"] = 100
    assert not login._visible_in_viewport(element, page)
    element.evaluate = lambda expression: True
    assert login._visible_in_viewport(element, page)


def test_institution_captcha_does_not_treat_verify_query_as_challenge():
    page = SimpleNamespace(url="https://www.cnki.net/?returnurl=/verify/old", frames=[])
    assert not login.institution_captcha_visible(page)
    page.url = "https://kns.cnki.net/verify/slider"
    assert login.institution_captcha_visible(page)
