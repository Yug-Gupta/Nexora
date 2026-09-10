"""Central configuration for Nexora.

Every runtime setting lives in one place.  Values are read from the process
environment (optionally loaded from a ``.env`` file at the repository root)
and exposed through a frozen :class:`Settings` record that the rest of the
code consumes instead of reaching into ``os.environ`` on its own.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"

_LOGGER_NAMESPACE = "nexora"

_ENV_DEFAULTS = {
    "neo4j_uri": "bolt://127.0.0.1:7687",
    "neo4j_user": "neo4j",
    "neo4j_database": None,
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "retrieval_depth": 2,
    "entry_limit": 8,
    "context_cap": 18,
    "llm_timeout": 300,
    "log_level": "INFO",
}

_ENV_MAP = {
    "neo4j_uri": "NEO4J_URI",
    "neo4j_user": "NEO4J_USER",
    "neo4j_password": "NEO4J_PASSWORD",
    "neo4j_database": "NEO4J_DATABASE",
    "gemini_api_key": "GEMINI_API_KEY",
    "gemini_model": "GEMINI_MODEL",
    "retrieval_depth": "NEXORA_RETRIEVAL_DEPTH",
    "entry_limit": "NEXORA_ENTRY_LIMIT",
    "context_cap": "NEXORA_CONTEXT_LIMIT",
    "llm_timeout": "NEXORA_LLM_TIMEOUT",
    "log_level": "NEXORA_LOG_LEVEL",
}


def _read_dotenv(path: Path) -> dict[str, str]:
    """Parse a minimal ``KEY=VALUE`` file without external dependencies."""
    loaded: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return loaded
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            loaded[key] = value
    return loaded


def _as_int(raw: str | None, fallback: int, minimum: int, maximum: int) -> int:
    """Parse an integer and clamp it into ``[minimum, maximum]``."""
    if raw is None:
        return fallback
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, value))


def _as_float(
    raw: str | None, fallback: float, minimum: float, maximum: float
) -> float:
    """Parse a float and clamp it into ``[minimum, maximum]``."""
    if raw is None:
        return fallback
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of every tunable used by the application.

    Neo4j defaults point at local development (``bolt://127.0.0.1:7687``), but
    every Neo4j value is configurable so the app can connect to a managed
    instance such as Neo4j AuraDB. Inference is provided by the Google Gemini
    API; ``gemini_api_key`` is empty by default and must be supplied through the
    environment, a ``.env`` file or Streamlit secrets.
    """

    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str | None = None
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    retrieval_depth: int = 2
    entry_limit: int = 8
    context_cap: int = 18
    llm_timeout: float = 300.0
    log_level: str = "INFO"

    def with_overrides(self, **changes: object) -> Settings:
        """Return a new settings record with only ``changes`` applied."""
        return replace(self, **changes)

    def signature(self) -> tuple[object, ...]:
        """Hashable fingerprint used to detect when connections must refresh."""
        return (
            self.neo4j_uri,
            self.neo4j_user,
            self.neo4j_password,
            self.neo4j_database,
            self.gemini_api_key,
            self.gemini_model,
            self.retrieval_depth,
            self.entry_limit,
            self.context_cap,
            self.llm_timeout,
        )

    @classmethod
    def from_environment(cls) -> Settings:
        """Build settings from the process environment plus an optional ``.env``.

        Real environment variables take precedence over values found in the
        ``.env`` file, which is the conventional dotenv behaviour.
        """
        env = _read_dotenv(_ENV_FILE)
        env.update(
            {key: value for key, value in os.environ.items() if value is not None}
        )

        return cls(
            neo4j_uri=env.get("NEO4J_URI", _ENV_DEFAULTS["neo4j_uri"]),
            neo4j_user=env.get("NEO4J_USER", _ENV_DEFAULTS["neo4j_user"]),
            neo4j_password=env.get("NEO4J_PASSWORD", ""),
            neo4j_database=env.get("NEO4J_DATABASE") or None,
            gemini_api_key=env.get("GEMINI_API_KEY", ""),
            gemini_model=env.get("GEMINI_MODEL", _ENV_DEFAULTS["gemini_model"]),
            retrieval_depth=_as_int(
                env.get("NEXORA_RETRIEVAL_DEPTH"),
                _ENV_DEFAULTS["retrieval_depth"],
                1,
                6,
            ),
            entry_limit=_as_int(
                env.get("NEXORA_ENTRY_LIMIT"),
                _ENV_DEFAULTS["entry_limit"],
                1,
                30,
            ),
            context_cap=_as_int(
                env.get("NEXORA_CONTEXT_LIMIT"),
                _ENV_DEFAULTS["context_cap"],
                4,
                60,
            ),
            llm_timeout=_as_float(
                env.get("NEXORA_LLM_TIMEOUT"),
                _ENV_DEFAULTS["llm_timeout"],
                5.0,
                3600.0,
            ),
            log_level=env.get("NEXORA_LOG_LEVEL", _ENV_DEFAULTS["log_level"]).upper(),
        )


def configure_logging(level_name: str = "INFO") -> None:
    """Install a single console handler for the ``nexora`` logger tree.

    The function is idempotent: repeated calls (e.g. one per Streamlit rerun)
    do not stack duplicate handlers.
    """
    root = logging.getLogger(_LOGGER_NAMESPACE)
    if root.handlers:
        return
    level = getattr(logging, level_name.upper(), logging.INFO)
    root.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    root.addHandler(handler)
