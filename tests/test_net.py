from unittest.mock import patch
import urllib.request
from acq import net


def test_direct_opener_has_no_proxy():
    # 模拟系统配置了 Clash 代理；direct_opener() 必须忽略系统代理
    # 注：ProxyHandler({}) 不注册 *_open 方法，故不进 op.handlers，
    # 正确的验证点是 op.handle_open['http'] 中无 ProxyHandler 实例
    fake = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
    with patch("urllib.request.getproxies", return_value=fake):
        op = net.direct_opener()
    assert not any(
        h.__class__.__name__ == "ProxyHandler"
        for h in op.handle_open.get("http", [])
    )


def test_user_agent_present():
    assert "Mozilla/5.0" in net.USER_AGENT
