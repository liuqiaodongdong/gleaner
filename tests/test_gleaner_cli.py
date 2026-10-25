# tests/test_gleaner_cli.py — gleaner_cli 子命令参数 → 调用链（mock 内核）
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import gleaner_cli

_MIN_SEARCH_MD = """## L1 — top

```text
(SU %= 'a') AND LY = ('经济研究') AND YE >= '2020'
```
"""


def test_install_skill_cli(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "repo"
    src = repo / "skill" / "gleaner"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("# gleaner\n", encoding="utf-8")
    (repo / "gleaner_cli.py").write_text("# stub\n", encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("GLEANER_ROOT", str(repo))
    monkeypatch.setenv("GLEANER_SKILL_HOME", str(home))
    code = gleaner_cli.main(["install-skill", "--root", str(repo)])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True
    assert data["command"] == "install-skill"
    dest = home / ".grok" / "skills" / "gleaner"
    assert (dest / "SKILL.md").is_file()
    assert (dest / ".gleaner_root").read_text(encoding="utf-8") == str(repo.resolve())


def test_install_skill_missing_source(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    monkeypatch.setenv("GLEANER_SKILL_HOME", str(tmp_path / "home"))
    code = gleaner_cli.main(["install-skill", "--root", str(tmp_path)])
    assert code == 1
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False
    assert data["error"] == "skill_source_missing"


def test_status_prints_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    fake = {"ok": True, "lines": {}, "blockers": [], "next_steps_for_user": []}
    with patch("acq.setup_check.check_setup", return_value=fake):
        code = gleaner_cli.main(["status", "--root", str(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    # status 应打印完整 JSON
    assert json.loads(out)["ok"] is True


def test_prepare_calls_prepare_search(tmp_path, monkeypatch):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    groups = json.dumps(
        [{"name": "A", "keywords": ["数字经济"]}, {"name": "B", "keywords": ["创新"]}],
        ensure_ascii=False,
    )
    fake = {"ok": True, "search_md": str(tmp_path / "s.md"), "levels": {"L1": "x"}}
    with patch("acq.sources.cnki_query.prepare_search", return_value=fake) as m:
        code = gleaner_cli.main(
            [
                "prepare",
                "--root", str(tmp_path),
                "--topic", "测试主题",
                "--concept-groups", groups,
                "--year-from", "2020",
            ]
        )
    assert code == 0
    m.assert_called_once()
    kwargs = m.call_args.kwargs
    assert kwargs["topic"] == "测试主题"
    assert kwargs["year_from"] == "2020"
    assert kwargs["workspace_root"] == Path(tmp_path).resolve()


def test_prepare_concept_groups_from_at_file(tmp_path, monkeypatch):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    groups = [{"name": "A", "keywords": ["x"]}]
    gpath = tmp_path / "groups.json"
    gpath.write_text(json.dumps(groups, ensure_ascii=False), encoding="utf-8")
    fake = {"search_md": "s.md", "levels": {}}
    with patch("acq.sources.cnki_query.prepare_search", return_value=fake) as m:
        code = gleaner_cli.main(
            [
                "prepare",
                "--root", str(tmp_path),
                "--topic", "T",
                "--concept-groups", f"@{gpath}",
            ]
        )
    assert code == 0
    # prepare_search 应收到文件内容（字符串），而非 @path
    assert m.call_args.kwargs["concept_groups"] == gpath.read_text(encoding="utf-8")


def test_sources_reads_guard_state(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    gdir = tmp_path / "acq" / "guard_state"
    gdir.mkdir(parents=True)
    (gdir / "guard_oa.json").write_text(
        json.dumps({"count": 3, "tripped": False, "day": "2026-08-10", "fail_count": 0}),
        encoding="utf-8",
    )
    fake_setup = {
        "ok": True,
        "next_steps_for_user": [],
        "lines": {
            "cnki": {"cnki_collect_ready": False},
            "elsevier": {"ready": False},
            "intl": {"carsi_optional": {"ok": False}},
        },
    }
    with patch("acq.setup_check.check_setup", return_value=fake_setup):
        code = gleaner_cli.main(["sources", "--root", str(tmp_path)])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["setup_ok"] is True
    by_name = {s["name"]: s for s in data["sources"]}
    assert set(by_name) == {"cnki", "elsevier"}
    assert by_name["cnki"]["status"] == "needs_setup"


def test_login_hint_mentions_login_py(capsys):
    code = gleaner_cli.main(["login-hint"])
    assert code == 0
    out = capsys.readouterr().out
    assert "login.py" in out
    assert "ACQ_BROWSER_CHANNEL" in out or "msedge" in out
    assert "超级鹰" in out
    assert "ACQ_ALLOW_COLD_LOGIN" in out
    assert "冷启动" in out
    assert "禁止" in out or "空烧" in out
    assert "自己" in out or "不要让用户" in out
    assert "login-hint" in out or "不要只" in out
    assert "--until" in out or "串行" in out


def test_score_prints_result(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    with patch("captcha.chaojiying_score", return_value='{"err_no":0,"tifen":99}'):
        code = gleaner_cli.main(["score", "--root", str(tmp_path)])
    assert code == 0
    assert "99" in capsys.readouterr().out


def test_cnki_list_invokes_run_list(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    topic = "主题A"
    d = tmp_path / "keyword_workspace" / topic / "2020_2026"
    d.mkdir(parents=True)
    (d / "search.md").write_text(_MIN_SEARCH_MD, encoding="utf-8")

    captured: dict = {}

    def fake_run(cmd, *, cwd, log_path, env=None, timeout=None, append=False):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["log_path"] = log_path
        captured["timeout"] = timeout
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("ok\n", encoding="utf-8")
        return 0

    def fake_summarize(out_dir, *, file_glob="*.pdf"):
        return {
            "local_dir": str(out_dir),
            "metadata_csv": str(Path(out_dir) / "metadata.csv"),
            "metadata_rows": 0,
            "downloaded_files": 0,
            "titles": [],
        }

    with (
        patch("acq.setup_check.preflight", return_value=None),
        patch("gleaner_cli.run_logged", side_effect=fake_run) as m_run,
        patch("gleaner_cli.summarize_batch", side_effect=fake_summarize),
        patch("gleaner_cli._try_merge_corpus", return_value="merged.csv"),
    ):
        code = gleaner_cli.main(
            [
                "cnki-list",
                "--root", str(tmp_path),
                "--level", "L1",
                "--topic", topic,
                "--num", "5",
            ]
        )
    assert code == 0
    assert m_run.called
    cmd_joined = " ".join(str(x) for x in captured["cmd"])
    assert "run_list.py" in cmd_joined
    assert captured["timeout"] is None
    # params 文件
    pfile = tmp_path / "corpus" / "_cli_cnki_list_params.json"
    assert pfile.is_file()
    params = json.loads(pfile.read_text(encoding="utf-8"))
    assert params["pro"] is True
    assert "LY =" in params["expression"]
    assert params["num"] == 5
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["command"] == "cnki-list"
    assert out["exit_code"] == 0
    assert "log_path" in out


def test_cnki_invokes_run_batch_keyword(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    captured: dict = {}

    def fake_run(cmd, *, cwd, log_path, env=None, timeout=None, append=False):
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("", encoding="utf-8")
        return 0

    with (
        patch("acq.setup_check.preflight", return_value=None),
        patch("gleaner_cli.run_logged", side_effect=fake_run),
        patch(
            "gleaner_cli.summarize_batch",
            return_value={
                "local_dir": str(tmp_path / "corpus" / "batch_x"),
                "metadata_csv": "",
                "metadata_rows": 0,
                "downloaded_files": 0,
                "titles": [],
            },
        ),
        patch("gleaner_cli._try_merge_corpus", return_value="skip"),
    ):
        code = gleaner_cli.main(
            [
                "cnki",
                "--root", str(tmp_path),
                "--query", "数字经济",
                "--num", "3",
                "--out-name", "demo_kw",
            ]
        )
    assert code == 0
    cmd_joined = " ".join(str(x) for x in captured["cmd"])
    assert "run_batch.py" in cmd_joined
    assert captured["timeout"] is None
    pfile = tmp_path / "corpus" / "_cli_cnki_params.json"
    params = json.loads(pfile.read_text(encoding="utf-8"))
    assert params["keyword"] == "数字经济"
    assert "pro" not in params or params.get("pro") is not True
    assert "demo_kw" in params["out"]
    out = json.loads(capsys.readouterr().out)
    assert out["command"] == "cnki"
    assert out["mode"] == "keyword"
    assert out["num"] == 3
    assert out["num_randomized"] is False


def test_cnki_omitted_num_rolls_between_40_and_60(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    monkeypatch.setattr(gleaner_cli.random, "randint", lambda a, b: 47)
    with (
        patch("acq.setup_check.preflight", return_value=None),
        patch("gleaner_cli.run_logged", return_value=0),
        patch(
            "gleaner_cli.summarize_batch",
            return_value={
                "local_dir": "x",
                "metadata_csv": "x",
                "metadata_rows": 0,
                "downloaded_files": 0,
                "titles": [],
            },
        ),
        patch("gleaner_cli._try_merge_corpus", return_value=""),
    ):
        code = gleaner_cli.main(
            ["cnki", "--root", str(tmp_path), "--query", "x", "--out-name", "e"]
        )
    assert code == 0
    params = json.loads(
        (tmp_path / "corpus" / "_cli_cnki_params.json").read_text(encoding="utf-8")
    )
    assert params["num"] == 47
    out = json.loads(capsys.readouterr().out)
    assert out["num"] == 47
    assert out["num_randomized"] is True


def test_cnki_list_requires_query_without_level(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    with patch("acq.setup_check.preflight", return_value=None):
        code = gleaner_cli.main(["cnki-list", "--root", str(tmp_path), "--num", "1"])
    assert code == 1
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False
    assert "query" in data["error"].lower() or "query" in data["error"]


def test_cnki_aborts_when_preflight_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    with (
        patch(
            "acq.setup_check.preflight",
            return_value={"error": "setup_incomplete", "line": "cnki"},
        ) as m_pf,
        patch("gleaner_cli.run_logged") as m_run,
    ):
        code = gleaner_cli.main(
            ["cnki", "--root", str(tmp_path), "--query", "x", "--out-name", "e"]
        )
    assert code != 0
    m_pf.assert_called_once_with("cnki")
    m_run.assert_not_called()
    data = json.loads(capsys.readouterr().out)
    assert data.get("error") == "setup_incomplete"


def test_cnki_list_aborts_when_preflight_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    with (
        patch(
            "acq.setup_check.preflight",
            return_value={"error": "setup_incomplete", "line": "cnki-list"},
        ) as m_pf,
        patch("gleaner_cli.run_logged") as m_run,
    ):
        code = gleaner_cli.main(
            ["cnki-list", "--root", str(tmp_path), "--query", "x"]
        )
    assert code != 0
    m_pf.assert_called_once_with("cnki-list")
    m_run.assert_not_called()
    data = json.loads(capsys.readouterr().out)
    assert data.get("error") == "setup_incomplete"


def test_cnki_sets_headless_env(tmp_path, monkeypatch):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    monkeypatch.delenv("ACQ_HEADLESS", raising=False)
    monkeypatch.delenv("ACQ_BROWSER_CHANNEL", raising=False)

    with (
        patch("acq.setup_check.preflight", return_value=None),
        patch("gleaner_cli.run_logged", return_value=0),
        patch(
            "gleaner_cli.summarize_batch",
            return_value={
                "local_dir": "x",
                "metadata_csv": "x",
                "metadata_rows": 0,
                "downloaded_files": 0,
                "titles": [],
            },
        ),
        patch("gleaner_cli._try_merge_corpus", return_value=""),
    ):
        gleaner_cli.main(
            ["cnki", "--root", str(tmp_path), "--query", "x", "--out-name", "e"]
        )
    import os

    assert os.environ.get("ACQ_HEADLESS") == "1"
    assert os.environ.get("ACQ_BROWSER_CHANNEL") == "msedge"


def test_els_aborts_when_preflight_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    with patch(
        "acq.setup_check.preflight",
        return_value={"error": "setup_incomplete", "setup_incomplete": True},
    ):
        code = gleaner_cli.main(
            ["els", "--root", str(tmp_path), "--query", "innovation"]
        )
    assert code != 0
    data = json.loads(capsys.readouterr().out)
    assert data.get("error") == "setup_incomplete" or data.get("setup_incomplete")


def test_els_invokes_run_els_batch(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    fake_journals = [
        {"name": "J1", "issn": "1234-5678", "level": "A++", "tier": 1},
    ]
    captured: dict = {}

    def fake_run(cmd, *, cwd, log_path, env=None, timeout=None, append=False):
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("els ok\n", encoding="utf-8")
        return 0

    with (
        patch("acq.setup_check.preflight", return_value=None),
        patch("acq.sources.els_query.load_tiers", return_value={}),
        patch(
            "acq.sources.els_query.select_journals",
            return_value=fake_journals,
        ) as m_sel,
        patch("gleaner_cli.run_logged", side_effect=fake_run),
        patch(
            "gleaner_cli.summarize_batch",
            return_value={
                "local_dir": str(tmp_path / "corpus" / "els_demo"),
                "metadata_csv": "",
                "metadata_rows": 1,
                "downloaded_files": 1,
                "titles": ["T1"],
            },
        ) as m_sum,
        patch("gleaner_cli._try_merge_corpus", return_value="merged.csv"),
    ):
        code = gleaner_cli.main(
            [
                "els",
                "--root", str(tmp_path),
                "--query", '("digital economy") AND innovation',
                "--num", "5",
                "--tier", "1",
                "--year-from", "2020",
                "--per-journal", "10",
                "--out-name", "els_demo",
            ]
        )
    assert code == 0
    m_sel.assert_called_once()
    assert m_sel.call_args.args[1] == "1"
    cmd_joined = " ".join(str(x) for x in captured["cmd"])
    assert "run_els_batch.py" in cmd_joined
    assert captured["timeout"] is None
    # PDF 为主计数，XML 单独计数
    assert [c.kwargs["file_glob"] for c in m_sum.call_args_list] == ["*.pdf", "*.xml"]
    pfile = tmp_path / "corpus" / "_cli_els_params.json"
    params = json.loads(pfile.read_text(encoding="utf-8"))
    assert params["qs"] == '("digital economy") AND innovation'
    assert params["sort"] == "relevance"
    assert params["scope"] == "title"
    assert params["journals"] == fake_journals
    assert params["date_from"] == "2020"
    assert params["per_journal"] == 10
    assert params["num"] == 5
    assert "els_demo" in params["out"]
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["command"] == "els"
    assert out["journals_searched"] == 1
    assert out["exit_code"] == 0


def test_els_rejects_chinese_only_query(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    with patch("acq.setup_check.preflight", return_value=None):
        code = gleaner_cli.main(
            ["els", "--root", str(tmp_path), "--query", "绿色转型 供应链"]
        )
    assert code != 0
    data = json.loads(capsys.readouterr().out)
    assert data.get("ok") is False
    assert "英文" in data.get("error", "")


@pytest.mark.parametrize("pdf_count,xml_count,exit_code,expected_ok", [
    (0, 2, 1, False), (1, 2, 1, False), (2, 2, 0, True), (0, 0, 0, False),
])
def test_els_reports_pdf_and_xml_counts(tmp_path, monkeypatch, capsys, pdf_count, xml_count, exit_code, expected_ok):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    def fake_run(cmd, **kwargs):
        papers = tmp_path / "corpus" / "counts" / "papers"
        papers.mkdir(parents=True)
        for i in range(pdf_count):
            (papers / f"{i}.pdf").write_bytes(b"PDF stub")
        for i in range(xml_count):
            (papers / f"{i}.xml").write_bytes(b"XML stub")
        (papers / "old.md").write_text("legacy", encoding="utf-8")
        (papers.parent / "metadata.csv").write_text("title\nA\nB\n", encoding="utf-8")
        return exit_code
    with (patch("acq.setup_check.preflight", return_value=None),
          patch("gleaner_cli.run_logged", side_effect=fake_run),
          patch("gleaner_cli._try_merge_corpus", return_value="merged.csv")):
        code = gleaner_cli.main(["els", "--root", str(tmp_path), "--query", "innovation", "--all-journals", "--out-name", "counts"])
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is expected_ok
    assert (code == 0) is expected_ok
    assert result["downloaded_files"] == pdf_count
    assert result["downloaded_xml"] == xml_count
    assert result["failed_downloads"] == 2 - pdf_count


def test_els_strips_tak_wrapper(tmp_path, monkeypatch):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))

    def fake_run(cmd, *, cwd, log_path, env=None, timeout=None, append=False):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("ok\n", encoding="utf-8")
        return 0

    with (
        patch("acq.setup_check.preflight", return_value=None),
        patch("acq.sources.els_query.load_tiers", return_value={}),
        patch(
            "acq.sources.els_query.select_journals",
            return_value=[{"name": "J1", "issn": "1", "level": "A", "tier": 1}],
        ),
        patch("gleaner_cli.run_logged", side_effect=fake_run),
        patch(
            "gleaner_cli.summarize_batch",
            return_value={
                "local_dir": str(tmp_path / "corpus" / "x"),
                "metadata_csv": "",
                "metadata_rows": 0,
                "downloaded_files": 0,
                "titles": [],
            },
        ),
        patch("gleaner_cli._try_merge_corpus", return_value=""),
    ):
        code = gleaner_cli.main(
            [
                "els",
                "--root", str(tmp_path),
                "--query", 'tak("supply chain") and tak("green transition")',
                "--out-name", "els_tak",
            ]
        )
    assert code == 1  # 没有下载到 PDF，不能报告成功
    params = json.loads((tmp_path / "corpus" / "_cli_els_params.json").read_text(encoding="utf-8"))
    assert params["qs"] == '"supply chain" AND "green transition"'
    assert params["scope"] == "title"


@pytest.mark.parametrize("extra", [[], ["--sources", "oa,scihub", "--year-from", "2020", "--issn", "1234-5678"]])
def test_intl_disabled_before_subprocess_or_output(tmp_path, monkeypatch, capsys, extra):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    with patch("gleaner_cli.run_logged") as run:
        code = gleaner_cli.main(["intl", "--root", str(tmp_path), "--query", "innovation", *extra])
    assert code == 1
    assert json.loads(capsys.readouterr().out)["error"] == "line_disabled"
    run.assert_not_called()
    assert not (tmp_path / "corpus").exists()


def test_help_only_advertises_active_lines(capsys):
    with pytest.raises(SystemExit) as exc:
        gleaner_cli.build_parser().parse_args(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "cnki" in out and "els" in out
    assert "intl" not in out


def test_cnki_until_serial_runs_login_between_batches(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    calls: list[dict] = []

    def fake_run(cmd, *, cwd, log_path, env=None, timeout=None, append=False):
        calls.append(
            {
                "cmd": [str(x) for x in cmd],
                "append": append,
                "headless": None if env is None else env.get("ACQ_HEADLESS"),
                "cold": None if env is None else env.get("ACQ_ALLOW_COLD_LOGIN"),
            }
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write("ok\n")
        joined = " ".join(str(x) for x in cmd)
        if "login.py" in joined:
            return 0
        pfile = tmp_path / "corpus" / "_cli_cnki_params.json"
        n = json.loads(pfile.read_text(encoding="utf-8"))["num"]
        papers = tmp_path / "corpus" / "serial_demo" / "papers"
        papers.mkdir(parents=True, exist_ok=True)
        have = len(list(papers.glob("*.pdf")))
        for i in range(n):
            (papers / f"p{have + i}.pdf").write_bytes(b"%PDF")
        return 0

    with (
        patch("acq.setup_check.preflight", return_value=None),
        patch("gleaner_cli.run_logged", side_effect=fake_run),
        patch("gleaner_cli._try_merge_corpus", return_value=""),
    ):
        code = gleaner_cli.main(
            [
                "cnki",
                "--root",
                str(tmp_path),
                "--query",
                "x",
                "--out-name",
                "serial_demo",
                "--num",
                "5",
                "--until",
                "12",
            ]
        )
    assert code == 0
    batch_calls = [c for c in calls if "run_batch.py" in " ".join(c["cmd"])]
    login_calls = [c for c in calls if "login.py" in " ".join(c["cmd"])]
    assert [c["append"] for c in batch_calls] == [False, True, True]
    assert len(login_calls) == 2
    assert all(c["headless"] == "0" for c in login_calls)
    assert all(c["cold"] is None for c in login_calls)
    out = json.loads(capsys.readouterr().out)
    assert out["until"] == 12
    assert out["serial_batches"] == [5, 5, 2]
    assert out["login_between"] == 2
    assert out["downloaded_files"] == 12
    assert out["num"] == 2
    assert out["num_randomized"] is False
    assert out["until_reached"] is True
    assert out["ok"] is True


def test_cnki_until_login_fail_stops(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    calls: list[str] = []

    def fake_run(cmd, *, cwd, log_path, env=None, timeout=None, append=False):
        joined = " ".join(str(x) for x in cmd)
        calls.append(joined)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("x\n", encoding="utf-8")
        if "login.py" in joined:
            return 3
        papers = tmp_path / "corpus" / "e" / "papers"
        papers.mkdir(parents=True, exist_ok=True)
        (papers / "a.pdf").write_bytes(b"%PDF")
        return 0

    with (
        patch("acq.setup_check.preflight", return_value=None),
        patch("gleaner_cli.run_logged", side_effect=fake_run),
        patch("gleaner_cli._try_merge_corpus", return_value=""),
    ):
        code = gleaner_cli.main(
            [
                "cnki",
                "--root",
                str(tmp_path),
                "--query",
                "x",
                "--out-name",
                "e",
                "--num",
                "5",
                "--until",
                "20",
            ]
        )
    assert code != 0
    assert sum("run_batch.py" in c for c in calls) == 1
    assert sum("login.py" in c for c in calls) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["login_between"] == 1
    assert out["serial_batches"] == [5]
    assert out["exit_code"] == 3
    assert out["until_reached"] is False
    assert out["ok"] is False


def test_cnki_until_no_progress_stops_without_login(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    calls: list[str] = []

    def fake_run(cmd, *, cwd, log_path, env=None, timeout=None, append=False):
        calls.append(" ".join(str(x) for x in cmd))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("x\n", encoding="utf-8")
        return 0

    with (
        patch("acq.setup_check.preflight", return_value=None),
        patch("gleaner_cli.run_logged", side_effect=fake_run),
        patch("gleaner_cli._try_merge_corpus", return_value=""),
    ):
        code = gleaner_cli.main(
            [
                "cnki",
                "--root",
                str(tmp_path),
                "--query",
                "x",
                "--out-name",
                "e",
                "--until",
                "80",
            ]
        )
    assert code != 0
    assert sum("run_batch.py" in c for c in calls) == 1
    assert sum("login.py" in c for c in calls) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["until"] == 80
    assert len(out["serial_batches"]) == 1
    assert 40 <= out["serial_batches"][0] <= 60
    assert out["num_randomized"] is True
    assert out["until_reached"] is False
    assert out["ok"] is False


def test_cnki_until_already_enough_skips_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    papers = tmp_path / "corpus" / "e" / "papers"
    papers.mkdir(parents=True)
    for i in range(12):
        (papers / f"p{i}.pdf").write_bytes(b"%PDF")

    with (
        patch("acq.setup_check.preflight", return_value=None),
        patch("gleaner_cli.run_logged") as m_run,
        patch("gleaner_cli._try_merge_corpus", return_value=""),
    ):
        code = gleaner_cli.main(
            [
                "cnki",
                "--root",
                str(tmp_path),
                "--query",
                "x",
                "--out-name",
                "e",
                "--until",
                "10",
            ]
        )
    assert code == 0
    m_run.assert_not_called()
    out = json.loads(capsys.readouterr().out)
    assert out["until"] == 10
    assert out["serial_batches"] == []
    assert out["downloaded_files"] == 12
    assert out["until_reached"] is True
    assert out["ok"] is True


def test_cnki_until_small_num_keeps_going_past_old_round_cap(
    tmp_path, monkeypatch, capsys
):
    """旧公式 until//40+4 会让 --num 1 --until 8 只跑 4 批。"""
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    calls: list[str] = []

    def fake_run(cmd, *, cwd, log_path, env=None, timeout=None, append=False):
        calls.append(" ".join(str(x) for x in cmd))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write("ok\n")
        if "login.py" in calls[-1]:
            return 0
        papers = tmp_path / "corpus" / "e" / "papers"
        papers.mkdir(parents=True, exist_ok=True)
        have = len(list(papers.glob("*.pdf")))
        (papers / f"p{have}.pdf").write_bytes(b"%PDF")
        return 0

    with (
        patch("acq.setup_check.preflight", return_value=None),
        patch("gleaner_cli.run_logged", side_effect=fake_run),
        patch("gleaner_cli._try_merge_corpus", return_value=""),
    ):
        code = gleaner_cli.main(
            [
                "cnki",
                "--root",
                str(tmp_path),
                "--query",
                "x",
                "--out-name",
                "e",
                "--num",
                "1",
                "--until",
                "8",
            ]
        )
    assert code == 0
    assert sum("run_batch.py" in c for c in calls) == 8
    assert sum("login.py" in c for c in calls) == 7
    out = json.loads(capsys.readouterr().out)
    assert out["until_reached"] is True
    assert out["downloaded_files"] == 8
    assert out["serial_batches"] == [1] * 8


def test_cnki_list_rejects_until(tmp_path, monkeypatch):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    with pytest.raises(SystemExit):
        gleaner_cli.main(
            [
                "cnki-list",
                "--root",
                str(tmp_path),
                "--query",
                "x",
                "--until",
                "10",
            ]
        )


@pytest.mark.parametrize("tiered", [False, True])
def test_cnki_list_details_dispatch(tmp_path, monkeypatch, capsys, tiered):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    search = tmp_path / "search.md"
    search.write_text(_MIN_SEARCH_MD, encoding="utf-8")
    query_args = ["--level", "L1", "--search-md", str(search)] if tiered else ["--query", "数字经济"]
    with (
        patch("acq.setup_check.preflight", return_value=None) as preflight,
        patch("gleaner_cli.run_logged", return_value=0) as run,
        patch("gleaner_cli._try_merge_corpus", return_value=""),
    ):
        code = gleaner_cli.main(["cnki-list", "--details", "--root", str(tmp_path),
                                 "--num", "2", *query_args])
    assert code == 0
    preflight.assert_called_once_with("cnki-list")
    assert Path(run.call_args.args[0][1]).name == "run_list.py"
    params = json.loads((tmp_path / "corpus" / "_cli_cnki_list_params.json").read_text(encoding="utf-8"))
    assert params["details"] is True
    assert params["num"] == 2
    assert params["out"].endswith("_metadata")
    result = json.loads(capsys.readouterr().out)
    assert result["details"] is True
    assert len(result["fields"]) == 11
    assert result["downloaded_files"] == 0


def test_cnki_list_details_rejects_fulltext_batch(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    out = tmp_path / "corpus" / "existing"
    out.mkdir(parents=True)
    path = out / "metadata.csv"
    path.write_text("title,file_path\n甲,papers/a.pdf\n", encoding="utf-8-sig")
    before = path.read_bytes()
    with (
        patch("acq.setup_check.preflight", return_value=None),
        patch("gleaner_cli.run_logged") as run,
    ):
        code = gleaner_cli.main(["cnki-list", "--details", "--query", "x", "--out-name", "existing"])
    assert code == 1
    run.assert_not_called()
    assert "out-name" in json.loads(capsys.readouterr().out)["error"]
    assert path.read_bytes() == before
