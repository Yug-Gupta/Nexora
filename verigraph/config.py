"""Central configuration for Verigraph.

All runtime settings live in one place.  Values are read from environment
variables (optionally loaded from a ``.env`` file at the repository root)
and exposed through a frozen :class:`Settings` record that modules consume
instead of reaching into ``os.environ`` themselves.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


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
    if raw is None:
        return fallback
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of every tunable used by the application."""

    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str | None = None
    ollama_url: str = "http://127.0.0.1:11434"
    model_name: str = "llama3.2"
    retrieval_depth: int = 2
    entry_limit: int = 8
    context_cap: int = 18
    log_level: str = "INFO"

    def with_overrides(self, **changes: object) -> "Settings":
        """Return a new settings record with only ``changes`` applied."""
        return replace(self, **changes)

    def signature(self) -> tuple[object, ...]:
        """Hashable fingerprint used to detect when connections must refresh."""
        return (
            self.neo4j_uri,
            self.neo4j_user,
            self.neo4j_password,
            self.neo4j_database,
            self.ollama_url,
            self.model_name,
            self.retrieval_depth,
            self.entry_limit,
            self.context_cap,
        )

    @classmethod
    def from_environment(cls) -> "Settings":
        """Build settings from the process environment plus an optional ``.env``."""
        env = dict(os.environ)
        env.update(_read_dotenv(_ENV_FILE))
        env = {key: value for key, value in env.items() if value is not None}

        return cls(
            neo4j_uri=env.get("NEO4J_URI", "bolt://127.0.0.1:7687"),
            neo4j_user=env.get("NEO4J_USER", "neo4j"),
            neo4j_password=env.get("NEO4J_PASSWORD", ""),
            neo4j_database=env.get("NEO4J_DATABASE") or None,
            ollama_url=env.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            model_name=env.get("OLLAMA_MODEL", "llama3.2"),
            retrieval_depth=_as_int(env.get("VERIGRAPH_DEPTH"), 2, 1, 6),
            entry_limit=_as_int(env.get("VERIGRAPH_ENTRY_LIMIT"), 8, 1, 30),
            context_cap=_as_int(env.get("VERIGRAPH_CONTEXT_LIMIT"), 18, 4, 60),
            log_level=env.get("VERIGRAPH_LOG_LEVEL", "INFO").upper(),
        )


def configure_logging(level_name: str = "INFO") -> None:
    """Install a single console handler for the ``verigraph`` logger tree."""
    root = logging.getLogger("verigraph")
    if root.handlers:
        return
    level = getattr(logging, level_name.upper(), logging.INFO)
    root.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    root.addHandler(handler)
