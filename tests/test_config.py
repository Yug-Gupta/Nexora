"""Tests for nexora.config - the central settings record."""

from __future__ import annotations

import nexora.config as config
from nexora.config import Settings


def test_defaults_are_sensible():
    settings = Settings()
    assert settings.neo4j_uri == "bolt://127.0.0.1:7687"
    assert settings.neo4j_user == "neo4j"
    assert settings.gemini_api_key == ""
    assert settings.gemini_model == "gemini-2.5-flash"
    assert 1 <= settings.retrieval_depth <= 6
    assert settings.log_level == "INFO"


def test_from_environment_reads_process_env(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://remote:9999")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-value")
    settings = Settings.from_environment()
    assert settings.neo4j_uri == "bolt://remote:9999"
    assert settings.gemini_model == "gemini-2.5-pro"
    assert settings.gemini_api_key == "test-key-value"


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
    env_file.write_text("GEMINI_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "from-process")
    monkeypatch.setattr(config, "_ENV_FILE", env_file)
    assert Settings.from_environment().gemini_api_key == "from-process"


def test_with_overrides_is_immutable():
    original = Settings()
    changed = original.with_overrides(retrieval_depth=4, gemini_model="gemini-2.5-pro")
    assert changed.retrieval_depth == 4
    assert changed.gemini_model == "gemini-2.5-pro"
    assert original.retrieval_depth == 2
    assert original.gemini_model == "gemini-2.5-flash"


def test_signature_changes_when_credentials_change():
    base = Settings()
    assert base.signature() != base.with_overrides(neo4j_password="other").signature()
    assert base.signature() != base.with_overrides(gemini_api_key="other").signature()


def test_read_dotenv_ignores_malformed_lines(tmp_path):
    env_file = tmp_path / "env"
    env_file.write_text("GOOD=1\n\n# c\nNOEQUALS\nSINGLE='quoted'\n", encoding="utf-8")
    loaded = config._read_dotenv(env_file)
    assert loaded == {"GOOD": "1", "SINGLE": "quoted"}
