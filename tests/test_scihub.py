# tests/test_scihub.py
from acq.sources.scihub import extract_pdf_url_from_html

def test_extract_citation_meta():
    html = '<meta name="citation_pdf_url" content="https://sci.bban.top/pdf/10.1/x.pdf">'
    assert extract_pdf_url_from_html(html, "https://sci-hub.x") == "https://sci.bban.top/pdf/10.1/x.pdf"

def test_extract_iframe():
    html = '<iframe src="//sci.bban.top/pdf/10.1/y.pdf#nav"></iframe>'
    got = extract_pdf_url_from_html(html, "https://sci-hub.usualwant.com")
    assert got.endswith("/pdf/10.1/y.pdf") and got.startswith("https://")

def test_extract_none():
    assert extract_pdf_url_from_html("<embed src=''>", "https://x") is None

def test_extract_collapses_double_slash():
    # 落地页偶发的 path 双斜杠畸形应被折叠（保留 scheme 的 ://）
    html = '<iframe src="//sci.bban.top/pdf//10.1/z.pdf"></iframe>'
    got = extract_pdf_url_from_html(html, "https://sci-hub.usualwant.com")
    assert got == "https://sci.bban.top/pdf/10.1/z.pdf"

def test_extract_backslash_escaped_bban():
    # 反斜杠转义的斜杠 + 双重编码 DOI 斜杠 + 内嵌 bban CDN 绝对地址(实测畸形 URL)
    html = r'<a href="\/\/sci.bban.top\/pdf\/10.1093\/qje%252Fqjw018.pdf?download=true">PDF</a>'
    got = extract_pdf_url_from_html(html, "https://sci-hub.usualwant.com/10.1093/qje/qjw018")
    assert got == "https://sci.bban.top/pdf/10.1093/qje/qjw018.pdf"
