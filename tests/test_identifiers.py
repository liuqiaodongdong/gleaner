# tests/test_identifiers.py
from acq.identifiers import normalize_doi, normalize_doi_unicode, safe_filename

def test_normalize_doi():
    assert normalize_doi("https://doi.org/10.1257/aer.91.5.1369") == "10.1257/aer.91.5.1369"
    assert normalize_doi("doi: 10.1093/qje/qjac001") == "10.1093/qje/qjac001"

def test_normalize_doi_unicode():
    # 全角连字符 U+2010 + 多余空格（PDF 复制常见）
    assert normalize_doi_unicode("10.1257/aer.91.5.1369") == "10.1257/aer.91.5.1369"
    assert normalize_doi_unicode("10.1257/aer‐5 1369") is not None
    assert normalize_doi_unicode("not-a-doi") is None

def test_safe_filename():
    assert safe_filename('a/b:c*?"d') == "a_b_c_d"
    assert safe_filename("") == "paper"
