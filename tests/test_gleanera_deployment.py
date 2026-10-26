import json
from pathlib import Path

import pytest

import gleanera_cli
from acq import cli_support
from acq.cnki_session import mark_institution_session


def test_install_keeps_ordinary_skill_and_existing_configuration(tmp_path):
    repo = tmp_path/'repo'
    source = repo/'skill/gleanera'
    source.mkdir(parents=True)
    (source/'SKILL.md').write_text('---\nname: gleanera\n---\n', encoding='utf-8')
    (repo/'.env').write_text('LOCAL_SETTING=keep\n', encoding='utf-8')
    home = tmp_path/'home'
    for client in ['.grok','.cursor','.codex']:
        ordinary = home/client/'skills/gleaner'
        ordinary.mkdir(parents=True)
        (ordinary/'SKILL.md').write_text('ordinary', encoding='utf-8')
        (ordinary/'.gleaner_root').write_text('ordinary-root', encoding='utf-8')
    cli_support.install_user_skill(repo, home)
    for client in ['.grok','.cursor','.codex']:
        base = home/client/'skills'
        assert (base/'gleaner/SKILL.md').read_text() == 'ordinary'
        assert (base/'gleaner/.gleaner_root').read_text() == 'ordinary-root'
        assert (base/'gleanera/.gleanera_root').read_text(encoding='utf-8') == str(repo.resolve())
    assert (repo/'.env').read_text() == 'LOCAL_SETTING=keep\n'


def test_ordinary_root_environment_does_not_select_gleanera_repository(monkeypatch,tmp_path):
    monkeypatch.setenv('GLEANER_ROOT', str(tmp_path/'ordinary'))
    monkeypatch.delenv('GLEANERA_ROOT', raising=False)
    assert cli_support.resolve_root() == cli_support.DEFAULT_ROOT.resolve()


@pytest.mark.parametrize('command', ['els','intl'])
def test_removed_commands_are_not_executable(command):
    with pytest.raises(SystemExit) as exc:
        gleanera_cli.build_parser().parse_args([command,'--query','test'])
    assert exc.value.code == 2


def test_default_session_is_institution():
    args = gleanera_cli.build_parser().parse_args(['cnki','--query','test'])
    assert args.session_mode == 'institution'


def test_list_stops_when_institution_identity_is_missing(monkeypatch,tmp_path):
    from unittest.mock import Mock
    import browser, scraper, run_list
    context, page = Mock(), Mock()
    monkeypatch.setattr(browser,'launch_browser',lambda:(None,None,context,page))
    monkeypatch.setattr(browser,'close_browser',lambda *a:None)
    monkeypatch.setattr(scraper,'search_keyword',lambda *a:None)
    monkeypatch.setattr('acq.cnki_session.wait_for_institution_identity',lambda p:False)
    monkeypatch.setattr(run_list,'harvest',lambda *a,**k:pytest.fail('未确认身份不应采集'))
    params=tmp_path/'params.json'
    params.write_text(json.dumps({'keyword':'test','num':1,'out':str(tmp_path/'out')}),encoding='utf-8')
    monkeypatch.setattr(run_list.sys,'argv',['run_list.py',str(params)])
    with pytest.raises(RuntimeError,match='机构身份'):
        run_list.main()
