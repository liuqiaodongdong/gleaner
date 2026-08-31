import json
from pathlib import Path
from acq.sources import els

SAMPLE_XML = (Path(__file__).parent / "fixtures" / "els_sample.xml").read_bytes()


class FakeResp:
    def __init__(self, status, *, jdata=None, content=b""):
        self.status_code = status
        self._j = jdata
        self.content = content
        self.text = content.decode("utf-8", "ignore") if content else ""
        self.headers = {}

    def json(self):
        return self._j


class FakeSession:
    def __init__(self, put_resp=None, get_resp=None):
        self._put, self._get = put_resp, get_resp
        self.put_calls, self.get_calls = [], []

    def put(self, url, **kw):
        self.put_calls.append((url, kw)); return self._put

    def get(self, url, **kw):
        self.get_calls.append((url, kw)); return self._get


def test_search_journal_parses_results():
    j = {"results": [
        {"doi": "10.1016/x", "title": "T1", "sourceTitle": "J Public Econ",
         "publicationDate": "2024-01-01", "openAccess": False, "pii": "S1"},
        {"doi": "10.1016/y", "title": "T2", "sourceTitle": "J Public Econ",
         "publicationDate": "2023-05-01", "openAccess": True, "pii": "S2"}]}
    sess = FakeSession(put_resp=FakeResp(200, jdata=j))
    rows = els.search_journal(sess, qs="tax", pub="Journal of Public Economics",
                              date="2015-2026", count=25)
    assert [r["doi"] for r in rows] == ["10.1016/x", "10.1016/y"]
    assert rows[0]["journal"] == "J Public Econ" and rows[0]["year"] == "2024"
    body = json.loads(sess.put_calls[0][1]["data"])
    assert body["title"] == "tax"
    assert "qs" not in body
    assert body["display"]["sortBy"] == "relevance"
    assert body["display"]["show"] == 25


def test_search_journal_scope_qs_and_clamped_show():
    sess = FakeSession(put_resp=FakeResp(200, jdata={"results": []}))
    els.search_journal(sess, qs="tax AND evasion", pub="P", date="2020-2026",
                       count=8, scope="qs", sort="date")
    body = json.loads(sess.put_calls[0][1]["data"])
    assert body["qs"] == "tax AND evasion"
    assert "title" not in body
    assert body["display"]["show"] == 10
    assert body["display"]["sortBy"] == "date"


def test_search_journal_http_error_returns_empty():
    sess = FakeSession(put_resp=FakeResp(429, content=b"rate"))
    assert els.search_journal(sess, qs="x", pub="P", date="2020-2026") == []


def test_retrieve_fulltext_xml_returns_status_and_bytes():
    sess = FakeSession(get_resp=FakeResp(200, content=b"<xml/>"))
    st, body = els.retrieve_fulltext_xml(sess, "10.1016/x")
    assert st == 200 and body == b"<xml/>"


def test_download_els_writes_md_and_xml(tmp_path):
    sess = FakeSession(get_resp=FakeResp(200, content=SAMPLE_XML))
    md = tmp_path / "a.md"; xmlp = tmp_path / "a.xml"
    ok = els.download_els(sess, "10.1016/x", md, xmlp)
    assert ok is True
    assert md.read_text(encoding="utf-8").startswith("# A Test Article")
    assert "| GDP growth | 3.14 |" in md.read_text(encoding="utf-8")  # 表格数值进了 MD
    assert xmlp.read_bytes() == SAMPLE_XML


def test_download_els_fails_on_non200(tmp_path):
    sess = FakeSession(get_resp=FakeResp(404, content=b"no"))
    ok = els.download_els(sess, "10.1016/z", tmp_path / "a.md", tmp_path / "a.xml")
    assert ok is False
    assert not (tmp_path / "a.md").exists()
