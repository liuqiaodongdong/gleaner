import json
from pathlib import Path
from unittest.mock import Mock

import gleaner_cli
import run_els_batch
from acq.sources import els


def test_unrestricted_els_request_omits_publisher():
    session = Mock()
    session.put.return_value.status_code = 200
    session.put.return_value.json.return_value = {"results": []}
    els.search_journal(session, qs='"real estate"', pub='', date='2022-2026')
    body = json.loads(session.put.call_args.kwargs['data'])
    assert 'pub' not in body
    assert body['title'] == '"real estate"'


def test_all_journals_keeps_property_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(els, 'search_journal', lambda *a, **k: [
        {'doi': '10.1234/property', 'title': 'Real estate operations',
         'journal': 'Property Management', 'year': '2024'}])
    monkeypatch.setattr(els, 'download_els', lambda *a, **k: {
        'ok': False, 'pdf_ok': False, 'xml_ok': False, 'error': 'xml_http_403',
        'pdf_pages': None, 'expected_pdf_pages': None, 'pdf_page_count_verified': False})
    monkeypatch.setattr(run_els_batch, '_sleep', lambda *a: None)
    result = run_els_batch.run({'qs': 'property', 'out': str(tmp_path),
        'all_journals': True, 'journals': [{'name': ''}]}, session=object())
    assert result['found'] == 1
