"""Nexora Streamlit application.

This is the only place that knows about page configuration and tab layout.
Every tab delegates to a dedicated view module; all domain work happens
behind :class:`nexora.service.KnowledgeAssistant`.
"""

from __future__ import annotations

import logging

import streamlit as st

from nexora.config import Settings, configure_logging
from nexora.ui import ask_view, ingest_view, sidebar, state, status_view, theme

logger = logging.getLogger(__name__)

_NAV = [
    ("Ingest knowledge", ingest_view.render),
    ("Ask a question", ask_view.render),
    ("System status", status_view.render),
]


def main() -> None:
    # Streamlit Community Cloud supplies configuration through st.secrets;
    # bridge it into the environment before settings/logging are read.
    state.hydrate_environment_from_secrets()
    configure_logging(Settings.from_environment().log_level)
    st.set_page_config(
        page_title="Nexora - Knowledge Graph Intelligence Engine",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    theme.render_hero()
    sidebar.render_sidebar()

    tabs = st.tabs([label for label, _ in _NAV])
    for tab, (_, render) in zip(tabs, _NAV, strict=True):
        with tab:
            render()


if __name__ == "__main__":  # pragma: no cover
    main()
