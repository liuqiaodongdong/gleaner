from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import captcha
import login
import gleaner_cli


def test_slider_moves_smoothly_without_overshoot_or_vertical_jitter(monkeypatch):
    monkeypatch.setattr(captcha.time,'sleep',lambda _:None)
    mouse = Mock()
    slider = SimpleNamespace(bounding_box=lambda:{'x':10,'y':20,'width':20,'height':20})
    captcha._human_like_drag(SimpleNamespace(mouse=mouse),slider,100)
    positions = [call.args for call in mouse.move.call_args_list]
    assert positions[0] == (20,30) and positions[-1] == (120,30)
    assert all(a[0] <= b[0] for a,b in zip(positions,positions[1:]))
    assert all(y == 30 for x,y in positions)
    mouse.down.assert_called_once()
    mouse.up.assert_called_once()


def test_slider_releases_mouse_on_failure(monkeypatch):
    mouse=Mock()
    mouse.move.side_effect=[None,RuntimeError('closed')]
    slider=SimpleNamespace(bounding_box=lambda:{'x':0,'y':0,'width':10,'height':10})
    with pytest.raises(RuntimeError):
        captcha._human_like_drag(SimpleNamespace(mouse=mouse),slider,100)
    mouse.up.assert_called_once()


def test_unknown_page_preserves_existing_session(monkeypatch,tmp_path):
    cookie=tmp_path/'cookies.json';cookie.write_bytes(b'original-session')
    monkeypatch.setattr(login,'COOKIES_FILE',cookie)
    monkeypatch.setattr(login,'_still_on_captcha',lambda *a:False)
    monkeypatch.setattr(captcha,'_has_pass_signal',lambda p:False)
    context=Mock()
    assert not login.persist_warm_cookies(context,SimpleNamespace(url='https://kns.cnki.net/verify'))
    assert cookie.read_bytes()==b'original-session'
    context.cookies.assert_not_called()


def test_login_failure_returns_nonzero_and_closes_browser(monkeypatch):
    monkeypatch.delenv('ACQ_PROXY',raising=False)
    monkeypatch.delenv('ACQ_MANUAL_CAPTCHA',raising=False)
    monkeypatch.setattr(login,'apply_login_credentials',lambda:None)
    monkeypatch.setattr(login,'load_existing_session',lambda c:0)
    monkeypatch.setattr(login,'wait_for_widget',lambda p:p)
    monkeypatch.setattr(login,'try_auto_solve_login_captcha',lambda p:False)
    monkeypatch.setattr(login,'wait_for_manual_pass',lambda *a:pytest.fail('不得默认进入人工等待'))
    pw=Mock()
    monkeypatch.setattr(login,'sync_playwright',lambda:SimpleNamespace(start=lambda:pw))
    assert login.main([])==1
    pw.chromium.launch.return_value.close.assert_called_once()
    pw.stop.assert_called_once()


@pytest.mark.parametrize('response',['{"err_no":-1,"err_str":"bad account"}','score err: network'])
def test_score_failure_returns_nonzero(monkeypatch,tmp_path,response):
    monkeypatch.setenv('GLEANER_ROOT',str(tmp_path))
    monkeypatch.setattr(captcha,'chaojiying_score',lambda:response)
    assert gleaner_cli.main(['score'])==1


def test_placeholder_cjy_is_rejected_before_upload(monkeypatch):
    monkeypatch.setenv('CJY_USER','your_chaojiying_username')
    monkeypatch.setenv('CJY_PASS','your_chaojiying_password')
    monkeypatch.setenv('CJY_SOFTID','your_softid')
    with pytest.raises(RuntimeError):
        captcha._require_cjy()
