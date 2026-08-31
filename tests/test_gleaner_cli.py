# tests/test_gleaner_cli.py — gleaner_cli 子命令参数 → 调用链（mock 内核）
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import gleaner_cli

_MIN_SEARCH_MD = """## L1 — top

```text
(SU %= 'a') AND LY = ('经济研究') AND YE >= '2020'
```
"""


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
    assert by_name["oa"]["guard"]["today_used"] == 3
    assert by_name["cnki"]["status"] == "needs_setup"


def test_login_hint_mentions_login_py(capsys):
    code = gleaner_cli.main(["login-hint"])
    assert code == 0
    out = capsys.readouterr().out
    assert "login.py" in out
    assert "ACQ_BROWSER_CHANNEL" in out or "msedge" in out
    assert "超级鹰" in out


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

    def fake_run(cmd, *, cwd, log_path, env=None, timeout=None):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["log_path"] = log_path
        captured["timeout"] = timeout
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("ok\n", encoding="utf-8")
        # 模拟题录产物
        batch_dir = tmp_path / "corpus" / "主题A_L1"
        # slug may sanitize 主题A
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

    def fake_run(cmd, *, cwd, log_path, env=None, timeout=None):
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
            return_value={"error": "setup_incomplete", "line": "cnki_collect"},
        ) as m_pf,
        patch("gleaner_cli.run_logged") as m_run,
    ):
        code = gleaner_cli.main(
            ["cnki", "--root", str(tmp_path), "--query", "x", "--out-name", "e"]
        )
    assert code != 0
    m_pf.assert_called_once_with("cnki_collect")
    m_run.assert_not_called()
    data = json.loads(capsys.readouterr().out)
    assert data.get("error") == "setup_incomplete"


def test_cnki_list_aborts_when_preflight_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    with (
        patch(
            "acq.setup_check.preflight",
            return_value={"error": "setup_incomplete", "line": "cnki_list"},
        ) as m_pf,
        patch("gleaner_cli.run_logged") as m_run,
    ):
        code = gleaner_cli.main(
            ["cnki-list", "--root", str(tmp_path), "--query", "x"]
        )
    assert code != 0
    m_pf.assert_called_once_with("cnki_list")
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

    def fake_run(cmd, *, cwd, log_path, env=None, timeout=None):
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
    # summarize 应传 *.md
    assert m_sum.call_args.kwargs.get("file_glob") == "*.md"
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


def test_els_strips_tak_wrapper(tmp_path, monkeypatch):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))

    def fake_run(cmd, *, cwd, log_path, env=None, timeout=None):
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
    assert code == 0
    params = json.loads((tmp_path / "corpus" / "_cli_els_params.json").read_text(encoding="utf-8"))
    assert params["qs"] == '"supply chain" AND "green transition"'
    assert params["scope"] == "title"


def test_intl_default_sources(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))
    captured: dict = {}

    def fake_run(cmd, *, cwd, log_path, env=None, timeout=None):
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("intl ok\n", encoding="utf-8")
        return 0

    with (
        patch("gleaner_cli.run_logged", side_effect=fake_run),
        patch(
            "gleaner_cli.summarize_batch",
            return_value={
                "local_dir": str(tmp_path / "corpus" / "intl_x"),
                "metadata_csv": "",
                "metadata_rows": 0,
                "downloaded_files": 0,
                "titles": [],
            },
        ) as m_sum,
        patch("gleaner_cli._try_merge_corpus", return_value=""),
    ):
        code = gleaner_cli.main(
            [
                "intl",
                "--root", str(tmp_path),
                "--query", "minimum wage employment",
                "--num", "3",
                "--out-name", "intl_x",
            ]
        )
    assert code == 0
    cmd_joined = " ".join(str(x) for x in captured["cmd"])
    assert "run_intl_batch.py" in cmd_joined
    assert captured["timeout"] is None
    assert m_sum.call_args.kwargs.get("file_glob") == "*.pdf"
    pfile = tmp_path / "corpus" / "_cli_intl_params.json"
    params = json.loads(pfile.read_text(encoding="utf-8"))
    assert params["query"] == "minimum wage employment"
    assert params["num"] == 3
    assert params["sources"] == ["oa", "nber", "scihub"]
    assert params["email"] == "Libby_Stantoncsc@writeme.com"
    assert "intl_x" in params["out"]
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["command"] == "intl"
    assert out["sources"] == ["oa", "nber", "scihub"]


def test_intl_custom_sources_and_filters(tmp_path, monkeypatch):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path))

    with (
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
            [
                "intl",
                "--root", str(tmp_path),
                "--query", "innovation",
                "--sources", "oa,scihub",
                "--year-from", "2020",
                "--issn", "1234-5678",
                "--out-name", "intl_filt",
            ]
        )
    assert code == 0
    params = json.loads(
        (tmp_path / "corpus" / "_cli_intl_params.json").read_text(encoding="utf-8")
    )
    assert params["sources"] == ["oa", "scihub"]
    assert params["year_from"] == "2020"
    assert params["issn"] == "1234-5678"
