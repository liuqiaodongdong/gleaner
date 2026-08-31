import ssl
import urllib.request

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

def _ctx(insecure: bool = False) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if insecure:  # Sci-Hub CDN 偶发异常证书时用
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx

def direct_opener(insecure: bool = False):
    # 关键：ProxyHandler({}) 忽略环境/系统代理，避免代理导致 SSL UNEXPECTED_EOF
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=_ctx(insecure)),
    )

def _req(url, headers=None):
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    return urllib.request.Request(url, headers=h)

def get(url, headers=None, timeout=25, insecure=False):
    op = direct_opener(insecure)
    with op.open(_req(url, headers), timeout=timeout) as r:
        return r.status, dict(r.headers), r.read()

def get_stream(url, headers=None, timeout=25, insecure=False):
    op = direct_opener(insecure)
    return op.open(_req(url, headers), timeout=timeout)  # 调用方 with/close

def direct_requests_session():
    import requests
    s = requests.Session()
    s.trust_env = False          # 忽略 HTTP_PROXY 等环境代理，国际/OA 走直连
    s.headers.update({"User-Agent": USER_AGENT})
    return s
