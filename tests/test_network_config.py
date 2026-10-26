import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import browser
import login
from acq.network_config import proxy_server, proxy_status
from acq import setup_check


@pytest.mark.parametrize('value', [None, '', '   '])
def test_default_direct_ignores_ambient_proxy(monkeypatch, value):
    monkeypatch.setenv('HTTP_PROXY', 'http://127.0.0.1:1')
    monkeypatch.setenv('HTTPS_PROXY', 'http://127.0.0.1:1')
    if value is None:
        monkeypatch.delenv('ACQ_PROXY', raising=False)
    else:
        monkeypatch.setenv('ACQ_PROXY', value)
    assert proxy_server() is None
    assert proxy_status()['ok'] and proxy_status()['mode'] == 'direct'
    assert 'proxy' not in login._context_kwargs()


@pytest.mark.parametrize('value', ['http://127.0.0.1:10808', 'https://proxy.example:443', 'socks5://localhost:1080'])
def test_explicit_proxy_is_used(monkeypatch, value):
    monkeypatch.setenv('ACQ_PROXY', value)
    assert proxy_status()['mode'] == 'proxy'
    assert login._context_kwargs()['proxy'] == {'server': value}


@pytest.mark.parametrize('value', ['http://127.0.0.1:PORT', '127.0.0.1:10808', 'http://localhost',
                                 'http://localhost:99999', 'http://localhost:0', 'file:///tmp/proxy',
                                 'http://user:private-password@localhost:88'])
def test_invalid_explicit_proxy_fails_without_echoing_value(monkeypatch, value):
    monkeypatch.setenv('ACQ_PROXY', value)
    status = proxy_status()
    assert not status['ok'] and status['mode'] == 'invalid'
    assert 'private-password' not in json.dumps(status)
    with pytest.raises(ValueError, match='ACQ_PROXY'):
        login._context_kwargs()


@pytest.mark.parametrize('proxy', [None, 'http://127.0.0.1:10808'])
def test_collection_browser_and_login_have_same_proxy_policy(monkeypatch, tmp_path, proxy):
    if proxy:
        monkeypatch.setenv('ACQ_PROXY', proxy)
    else:
        monkeypatch.delenv('ACQ_PROXY', raising=False)
    monkeypatch.setattr(browser, 'COOKIES_FILE', tmp_path/'missing.json')
    pw = Mock()
    monkeypatch.setattr(browser, 'sync_playwright', lambda: SimpleNamespace(start=lambda: pw))
    browser.launch_browser()
    launch = pw.chromium.launch.call_args.kwargs
    context = pw.chromium.launch.return_value.new_context.call_args.kwargs
    assert ('--no-proxy-server' in launch['args']) is (proxy is None)
    assert context.get('proxy') == login._context_kwargs().get('proxy')


def test_cnki_direct_preflight_with_cookie_needs_no_proxy(monkeypatch, tmp_path):
    monkeypatch.delenv('ACQ_PROXY', raising=False)
    for key in ('CJY_USER', 'CJY_PASS', 'CJY_SOFTID'):
        monkeypatch.delenv(key, raising=False)
    cookie = tmp_path/'cookies.json'
    cookie.write_text('[{"name":"session","value":"test"}]', encoding='utf-8')
    monkeypatch.setattr(setup_check, 'COOKIES_FILE', cookie)
    assert setup_check.preflight('cnki-list') is None
    assert setup_check.preflight('cnki')['error'] == 'setup_incomplete'
    for key, value in {'CJY_USER':'test-user','CJY_PASS':'test-password','CJY_SOFTID':'1'}.items():
        monkeypatch.setenv(key,value)
    assert setup_check.preflight('cnki') is None
    result = setup_check.check_setup()
    assert all(b['id'] != 'proxy' for b in result['blockers'])


def test_template_credentials_do_not_pass_preflight(monkeypatch, tmp_path):
    for key,value in {'CJY_USER':'your_chaojiying_username','CJY_PASS':'your_chaojiying_password',
                      'CJY_SOFTID':'your_softid','ELSEVIER_API_KEY':'your_elsevier_api_key_here'}.items():
        monkeypatch.setenv(key,value)
    monkeypatch.setattr(setup_check,'ELS_KEY_FILE',tmp_path/'missing')
    assert not setup_check._chaojiying()['ok']
    assert not setup_check._elsevier()['ok']
