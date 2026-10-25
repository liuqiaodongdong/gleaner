import json
from pathlib import Path
from unittest.mock import Mock

import gleaner_cli
import run_els_batch
from acq.sources import els, openalex


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


def test_openalex_all_disciplines_keeps_date_without_economics(monkeypatch):
    captured = {}
    def capture(params, num, mailto):
        captured.update(params)
        return []
    monkeypatch.setattr(openalex, '_iter_works', capture)
    openalex.search('real estate', econ_only=False, year_from='2022-01-01', mailto='test@example.org')
    assert 'concepts.id' not in captured['filter']
    assert 'from_publication_date:2022-01-01' in captured['filter']
    parser = gleaner_cli.build_parser()
    assert parser.parse_args(['intl', '--query', 'property', '--all-disciplines']).all_disciplines
    assert parser.parse_args(['els', '--query', 'property', '--all-journals']).all_journals
