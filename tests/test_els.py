import json
import io
from pathlib import Path
import pytest
import requests
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
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
        self.get_calls.append((url, kw))
        result = self._get.pop(0) if isinstance(self._get, list) else self._get
        if isinstance(result, Exception):
            raise result
        return result


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


def article_xml(*, pages=2, doi="10.1016/x", with_object=True):
    extra = f"<doi>{doi}</doi><pii>S1</pii>"
    if pages is not None:
        extra += f"<web-pdf-page-count>{pages}</web-pdf-page-count>"
    if with_object:
        extra += "<object>1-s2.0-S1-main.pdf</object>"
    return SAMPLE_XML.replace(b"</coredata>", extra.encode() + b"</coredata>")


def article_pdf(*, pages=2, text="A Test Article on Digital Economy 10.1016/x"):
    # 生成可真实解析的多页 PDF，避免仅用文件头模拟完整正文。
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                 NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        content = DecodedStreamObject()
        content.set_data(f"BT /F1 12 Tf 40 700 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(content)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def test_download_els_writes_validated_pdf_and_xml(tmp_path):
    xml = article_xml()
    pdf = article_pdf()
    sess = FakeSession(get_resp=[FakeResp(200, content=xml), FakeResp(200, content=pdf)])
    result = els.download_els(sess, "10.1016/x", tmp_path / "a.pdf", tmp_path / "a.xml")
    assert result["ok"] and result["xml_ok"] and result["pdf_ok"]
    assert result["pdf_pages"] == result["expected_pdf_pages"] == 2
    assert result["pdf_page_count_verified"]
    assert (tmp_path / "a.pdf").read_bytes() == pdf
    assert (tmp_path / "a.xml").read_bytes() == xml
    assert not list(tmp_path.glob("*.md")) and not list(tmp_path.glob("*.part"))
    assert "/content/object/eid/1-s2.0-S1-main.pdf" in sess.get_calls[1][0]
    assert all(call[1]["allow_redirects"] is False for call in sess.get_calls)


def test_download_els_fails_on_non200(tmp_path):
    sess = FakeSession(get_resp=FakeResp(404, content=b"no"))
    result = els.download_els(sess, "10.1016/z", tmp_path / "a.pdf", tmp_path / "a.xml")
    assert result["ok"] is False and result["error"] == "xml_http_404"
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("pdf,error", [
    (b"<html>login</html>", "pdf_invalid_signature_or_eof"),
    (article_pdf(pages=1), "pdf_page_count_mismatch"),
    (article_pdf(text="Completely different article 10.1016/other"), "pdf_identity_mismatch"),
    (article_pdf()[:-12], "pdf_invalid_signature_or_eof"),
])
def test_rejects_bad_pdf_but_preserves_fulltext_xml(tmp_path, pdf, error):
    sess = FakeSession(get_resp=[FakeResp(200, content=article_xml()), FakeResp(200, content=pdf)])
    result = els.download_els(sess, "10.1016/x", tmp_path / "a.pdf", tmp_path / "a.xml")
    assert not result["ok"] and result["xml_ok"] and not result["pdf_ok"]
    assert result["error"] == error
    assert (tmp_path / "a.xml").exists() and not (tmp_path / "a.pdf").exists()


def test_missing_object_uses_catalog_and_matches_pii(tmp_path):
    catalog = b'{"objects": ["1-s2.0-OTHER-main.pdf", "1-s2.0-S1-main.pdf"]}'
    sess = FakeSession(get_resp=[FakeResp(200, content=article_xml(with_object=False)),
                                FakeResp(200, content=catalog), FakeResp(200, content=article_pdf())])
    assert els.download_els(sess, "10.1016/x", tmp_path / "a.pdf", tmp_path / "a.xml")["ok"]
    assert "/content/object/doi/10.1016/x" in sess.get_calls[1][0]
    assert "S1-main.pdf" in sess.get_calls[2][0]


@pytest.mark.parametrize("status,body,error", [
    (200, b'{"objects": ["1-s2.0-OTHER-main.pdf", "1-s2.0-S1-mmc1.pdf"]}', "main_pdf_object_missing"),
    (403, b"denied", "object_list_http_403"),
])
def test_unavailable_main_object_is_not_downloaded(tmp_path, status, body, error):
    sess = FakeSession(get_resp=[FakeResp(200, content=article_xml(with_object=False)), FakeResp(status, content=body)])
    result = els.download_els(sess, "10.1016/x", tmp_path / "a.pdf", tmp_path / "a.xml")
    assert result["xml_ok"] and not result["pdf_ok"] and result["error"] == error
    assert len(sess.get_calls) == 2


def test_pdf_forbidden_keeps_xml_without_retry(tmp_path):
    sess = FakeSession(get_resp=[FakeResp(200, content=article_xml()), FakeResp(403, content=b"denied")])
    result = els.download_els(sess, "10.1016/x", tmp_path / "a.pdf", tmp_path / "a.xml")
    assert result["error"] == "pdf_http_403" and result["xml_ok"]
    assert len(sess.get_calls) == 2


@pytest.mark.parametrize("xml,error", [
    (b"<broken", "xml_invalid"),
    (article_xml(doi="10.1016/other"), "xml_doi_mismatch"),
    (b"<response><coredata><title>Only metadata</title></coredata></response>", "xml_missing_fulltext"),
])
def test_rejects_invalid_or_wrong_xml(tmp_path, xml, error):
    result = els.download_els(FakeSession(get_resp=FakeResp(200, content=xml)),
                              "10.1016/x", tmp_path / "a.pdf", tmp_path / "a.xml")
    assert result["error"] == error and not result["xml_ok"]
    assert not list(tmp_path.iterdir())


def test_actual_single_page_article_is_allowed(tmp_path):
    sess = FakeSession(get_resp=[FakeResp(200, content=article_xml(pages=1)),
                                FakeResp(200, content=article_pdf(pages=1))])
    assert els.download_els(sess, "10.1016/x", tmp_path / "a.pdf", tmp_path / "a.xml")["ok"]


def test_missing_page_metadata_is_reported(tmp_path):
    sess = FakeSession(get_resp=[FakeResp(200, content=article_xml(pages=None)),
                                FakeResp(200, content=article_pdf())])
    result = els.download_els(sess, "10.1016/x", tmp_path / "a.pdf", tmp_path / "a.xml")
    assert result["ok"] and not result["pdf_page_count_verified"]


@pytest.mark.parametrize("first", [FakeResp(503, content=b"busy"), requests.Timeout()])
def test_transient_failure_retries_once(monkeypatch, first):
    monkeypatch.setattr(els.time, "sleep", lambda _: None)
    sess = FakeSession(get_resp=[first, FakeResp(200, content=SAMPLE_XML)])
    assert els.retrieve_fulltext_xml(sess, "10.1016/x") == (200, SAMPLE_XML)
    assert len(sess.get_calls) == 2


def test_xml_write_error_is_reported(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError("disk full")
    monkeypatch.setattr(els, "_write_atomic", fail)
    result = els.download_els(FakeSession(get_resp=FakeResp(200, content=article_xml())),
                              "10.1016/x", tmp_path / "a.pdf", tmp_path / "a.xml")
    assert not result["ok"] and result["error"] == "xml_write_failed"
