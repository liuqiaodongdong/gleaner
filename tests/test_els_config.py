import os
import pytest
from acq import els_config


def test_env_var_takes_priority(monkeypatch):
    monkeypatch.setenv("ELSEVIER_API_KEY", "ENVKEY123")
    assert els_config.get_api_key() == "ENVKEY123"


def test_reads_file_when_no_env(monkeypatch, tmp_path):
    monkeypatch.delenv("ELSEVIER_API_KEY", raising=False)
    f = tmp_path / ".elsevier_key"
    f.write_text("FILEKEY456\n", encoding="utf-8")
    monkeypatch.setattr(els_config, "_KEY_FILE", f)
    assert els_config.get_api_key() == "FILEKEY456"


def test_raises_when_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("ELSEVIER_API_KEY", raising=False)
    monkeypatch.setattr(els_config, "_KEY_FILE", tmp_path / "nope")
    with pytest.raises(RuntimeError):
        els_config.get_api_key()
