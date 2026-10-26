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
