"""Tests for nexora.config - the central settings record."""

from __future__ import annotations

import nexora.config as config
from nexora.config import Settings


def test_defaults_are_sensible():
    settings = Settings()
    assert settings.neo4j_uri == "bolt://127.0.0.1:7687"
    assert settings.neo4j_user == "neo4j"
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.model_name == "llama3.2"
    assert 1 <= settings.retrieval_depth <= 6
    assert settings.log_level == "INFO"


def test_from_environment_reads_process_env(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://remote:9999")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1:8b")
    settings = Settings.from_environment()
    assert settings.neo4j_uri == "bolt://remote:9999"
    assert settings.model_name == "llama3.1:8b"


def test_retrieval_depth_is_clamped(monkeypatch):
    monkeypatch.setenv("NEXORA_RETRIEVAL_DEPTH", "99")
    assert Settings.from_environment().retrieval_depth == 6
    monkeypatch.setenv("NEXORA_RETRIEVAL_DEPTH", "-3")
    assert Settings.from_environment().retrieval_depth == 1
    monkeypatch.setenv("NEXORA_RETRIEVAL_DEPTH", "not-a-number")
    assert Settings.from_environment().retrieval_depth == 2


def test_dotenv_used_as_fallback_when_env_missing(monkeypatch, tmp_path):
    env_file = tmp_path / "env"
    env_file.write_text(
        'NEO4J_URI="bolt://from-file:1111"\nNEO4J_USER=neo4j\n# comment\n',
        encoding="utf-8",
    )
    for key in ("NEO4J_URI", "NEO4J_USER"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(config, "_ENV_FILE", env_file)
    settings = Settings.from_environment()
    assert settings.neo4j_uri == "bolt://from-file:1111"
    assert settings.neo4j_user == "neo4j"


def test_process_env_wins_over_dotenv(monkeypatch, tmp_path):
    env_file = tmp_path / "env"
    env_file.write_text("NEO4J_PASSWORD=from-file\n", encoding="utf-8")
    monkeypatch.setenv("NEO4J_PASSWORD", "from-process")
    monkeypatch.setattr(config, "_ENV_FILE", env_file)
    assert Settings.from_environment().neo4j_password == "from-process"


def test_with_overrides_is_immutable():
    original = Settings()
    changed = original.with_overrides(retrieval_depth=4, model_name="qwen2.5")
    assert changed.retrieval_depth == 4
    assert changed.model_name == "qwen2.5"
    assert original.retrieval_depth == 2
    assert original.model_name == "llama3.2"


def test_signature_changes_when_credentials_change():
    base = Settings()
    assert base.signature() != base.with_overrides(neo4j_password="other").signature()


def test_read_dotenv_ignores_malformed_lines(tmp_path):
    env_file = tmp_path / "env"
    env_file.write_text("GOOD=1\n\n# c\nNOEQUALS\nSINGLE='quoted'\n", encoding="utf-8")
    loaded = config._read_dotenv(env_file)
    assert loaded == {"GOOD": "1", "SINGLE": "quoted"}
