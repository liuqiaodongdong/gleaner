# tests/test_oa.py
from acq.sources.oa import (_unpaywall_candidates, _crossref_candidates,
                            _doaj_candidates, _openalex_candidates)

UNPAYWALL = {"best_oa_location": {"host_type": "publisher", "url_for_pdf": "https://p/pub.pdf"},
             "oa_locations": [{"host_type": "repository", "url_for_pdf": "https://r/repo.pdf"},
                              {"host_type": "publisher", "url_for_pdf": "https://p/pub.pdf"}]}

def test_unpaywall_repo_first():
    c = _unpaywall_candidates(UNPAYWALL)
    assert c[0] == "https://r/repo.pdf"   # repo 优先于 publisher
    assert "https://p/pub.pdf" in c

def test_unpaywall_empty_closed():
    assert _unpaywall_candidates({"best_oa_location": None, "oa_locations": []}) == []

def test_crossref_pdf_link():
    cr = {"message": {"link": [{"content-type": "application/pdf", "URL": "https://x/a.pdf"},
                               {"content-type": "text/html", "URL": "https://x/h"}]}}
    assert _crossref_candidates(cr) == ["https://x/a.pdf"]

def test_doaj_fulltext_link():
    doaj = {"results": [{"bibjson": {"link": [
        {"type": "fulltext", "url": "https://example.com/paper.pdf"},
        {"type": "pdf", "url": "https://example.com/paper2.pdf"},
        {"type": "html", "url": "https://example.com/paper.html"},
    ]}}]}
    c = _doaj_candidates(doaj)
    assert "https://example.com/paper.pdf" in c
    assert "https://example.com/paper2.pdf" in c
    assert "https://example.com/paper.html" not in c

def test_doaj_empty():
    assert _doaj_candidates({"results": []}) == []
    assert _doaj_candidates({}) == []

def test_openalex_scans_all_locations():
    # 关键：locations[] 里的 green OA(NBER/EconStor 镜像)必须被扫到，不止 best/oa_url
    data = {"open_access": {"is_oa": True, "oa_url": "https://x/oa"},
            "best_oa_location": {"pdf_url": "https://x/best.pdf"},
            "locations": [{"pdf_url": "https://nber.org/w1.pdf"},
                          {"pdf_url": None},
                          {"pdf_url": "https://econstor/repo.pdf"}]}
    c = _openalex_candidates(data)
    assert "https://nber.org/w1.pdf" in c
    assert "https://econstor/repo.pdf" in c
    assert "https://x/best.pdf" in c and "https://x/oa" in c

def test_openalex_empty():
    assert _openalex_candidates({"open_access": {}, "locations": []}) == []
