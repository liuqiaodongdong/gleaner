from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import captcha
import login
import gleanera_cli


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




def test_login_failure_returns_nonzero_and_closes_browser(monkeypatch):
    monkeypatch.delenv('ACQ_PROXY',raising=False)
    monkeypatch.delenv('ACQ_MANUAL_CAPTCHA',raising=False)
    monkeypatch.setattr(login,'apply_login_credentials',lambda:None)
    monkeypatch.setattr(login,'wait_for_institution_login',lambda *a:False)
    pw=Mock()
    monkeypatch.setattr(login,'sync_playwright',lambda:SimpleNamespace(start=lambda:pw))
    assert login.main([])==1
    pw.chromium.launch.return_value.close.assert_called_once()
    pw.stop.assert_called_once()


@pytest.mark.parametrize('response',['{"err_no":-1,"err_str":"bad account"}','score err: network'])
def test_score_failure_returns_nonzero(monkeypatch,tmp_path,response):
    monkeypatch.setenv('GLEANERA_ROOT',str(tmp_path))
    monkeypatch.setattr(captcha,'chaojiying_score',lambda:response)
    assert gleanera_cli.main(['score'])==1


def test_placeholder_cjy_is_rejected_before_upload(monkeypatch):
    monkeypatch.setenv('CJY_USER','your_chaojiying_username')
    monkeypatch.setenv('CJY_PASS','your_chaojiying_password')
    monkeypatch.setenv('CJY_SOFTID','your_softid')
    with pytest.raises(RuntimeError):
        captcha._require_cjy()
