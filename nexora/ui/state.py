"""Session plumbing and shared UI error rendering.

These helpers keep Streamlit ``session_state`` access in one place so views
stay declarative.  The assistant is cached per settings signature and rebuilt
whenever the sidebar settings change.
"""

from __future__ import annotations

import logging

import streamlit as st

from nexora.config import Settings
from nexora.errors import AppError
from nexora.models import StoreOverview
from nexora.service import KnowledgeAssistant

logger = logging.getLogger(__name__)


def current_settings() -> Settings:
    """Return the session settings, seeding from the environment on first use."""
    if "settings" not in st.session_state:
        st.session_state["settings"] = Settings.from_environment()
    return st.session_state["settings"]


def update_settings(updated: Settings) -> None:
    """Swap the active settings and release any assistant bound to the old ones."""
    previous = st.session_state.get("assistant_slot")
    if previous is not None:
        try:
            previous[1].close()
        except Exception:
            logger.debug("Ignored error while closing previous assistant", exc_info=True)
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
            logger.debug("Ignored error while closing previous assistant", exc_info=True)
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
