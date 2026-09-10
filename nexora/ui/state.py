"""Session plumbing and shared UI error rendering.

These helpers keep Streamlit ``session_state`` access in one place so views
stay declarative.  The assistant is cached per settings signature and rebuilt
whenever the sidebar settings change.

It is also the bridge that lets the engine stay Streamlit-free: on Streamlit
Community Cloud configuration arrives through ``st.secrets``, so this module
copies the recognised keys into the process environment before settings are
read.
"""

from __future__ import annotations

import logging
import os

import streamlit as st

from nexora.config import Settings
from nexora.errors import AppError
from nexora.models import StoreOverview
from nexora.service import KnowledgeAssistant

logger = logging.getLogger(__name__)

# Only these keys are ever copied out of Streamlit secrets, so an unexpected
# secret can never silently influence the engine.
SECRET_KEYS = (
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "NEO4J_DATABASE",
    "NEXORA_RETRIEVAL_DEPTH",
    "NEXORA_CONTEXT_LIMIT",
    "NEXORA_ENTRY_LIMIT",
    "NEXORA_LLM_TIMEOUT",
    "NEXORA_LOG_LEVEL",
)


def hydrate_environment_from_secrets() -> tuple[str, ...]:
    """Copy recognised ``st.secrets`` values into the process environment.

    The engine only ever reads configuration from the environment, which works
    for local ``.env`` files and container deployments. Streamlit Community
    Cloud injects secrets through ``st.secrets`` instead, so this bridge makes
    Cloud deployments work without the engine importing Streamlit.

    Real environment variables take precedence (``os.environ.setdefault``), and
    the names of the keys that were applied are returned for testing.
    """
    try:
        secrets = st.secrets
    except Exception:
        return ()

    applied: list[str] = []
    for key in SECRET_KEYS:
        try:
            value = secrets[key]
        except Exception:
            continue
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        if key not in os.environ:
            os.environ[key] = text
            applied.append(key)
    return tuple(applied)


def current_settings() -> Settings:
    """Return the session settings, seeding from the environment on first use."""
    if "settings" not in st.session_state:
        hydrate_environment_from_secrets()
        st.session_state["settings"] = Settings.from_environment()
    return st.session_state["settings"]


def update_settings(updated: Settings) -> None:
    """Swap the active settings and release any assistant bound to the old ones."""
    previous = st.session_state.get("assistant_slot")
    if previous is not None:
        try:
            previous[1].close()
        except Exception:
            logger.debug(
                "Ignored error while closing previous assistant", exc_info=True
            )
    st.session_state["settings"] = updated
    st.session_state.pop("assistant_slot", None)
    st.session_state.pop("cached_overview", None)
    st.session_state.pop("last_probes", None)


def reset_settings() -> None:
    """Discard manual overrides and fall back to environment defaults."""
    update_settings(Settings.from_environment())


def get_assistant() -> KnowledgeAssistant:
    """Return a cached assistant or rebuild it when settings changed."""
    settings = current_settings()
    slot = st.session_state.get("assistant_slot")
    if slot is not None and slot[0] == settings.signature():
        return slot[1]
    if slot is not None:
        try:
            slot[1].close()
        except Exception:
            logger.debug(
                "Ignored error while closing previous assistant", exc_info=True
            )
    assistant = KnowledgeAssistant(settings)
    st.session_state["assistant_slot"] = (settings.signature(), assistant)
    st.session_state.pop("cached_overview", None)
    return assistant


def cached_overview() -> StoreOverview | None:
    return st.session_state.get("cached_overview")


def remember_overview(overview: StoreOverview | None) -> None:
    st.session_state["cached_overview"] = overview


def last_probes():
    return st.session_state.get("last_probes")


def remember_probes(probes) -> None:
    st.session_state["last_probes"] = probes


def present_error(exc: Exception, *, hint: str = "operation") -> None:
    """Render any expected failure in a readable way and log the detail."""
    if isinstance(exc, AppError):
        logger.warning("%s failed: %s | detail: %s", hint, exc.message, exc.detail)
        st.error(exc.message)
        if exc.detail:
            st.caption(f"Diagnostic detail: {exc.detail}")
    else:
        logger.exception("Unexpected failure during %s", hint)
        st.error("Something unexpected went wrong. See the logs for details.")
