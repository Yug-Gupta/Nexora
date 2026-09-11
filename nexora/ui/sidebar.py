"""Sidebar: live connection settings and session override management."""

from __future__ import annotations

import html

import streamlit as st

from nexora.ui.state import current_settings, reset_settings, update_settings
from nexora.ui.theme import BRAND, VERSION, render_raw


def _render_service_summary() -> None:
    """Compact status dots for the services most recently probed."""
    probes = {
        probe.component: probe for probe in st.session_state.get("last_probes", [])
    }
    if not probes:
        st.caption("Run diagnostics on the System tab to see service health.")
        return
    lines = []
    order = ("Graph database", "Gemini API", "Configured model")
    labels = {
        "Graph database": "Neo4j",
        "Gemini API": "Gemini",
        "Configured model": "Model",
    }
    for component in order:
        probe = probes.get(component)
        if probe is None:
            continue
        label = labels.get(component, component)
        dot = (
            "<span class='dot dot-ok'></span>"
            if probe.available
            else ("<span class='dot dot-bad'></span>")
        )
        body = (
            "ready"
            if probe.available and component == "Configured model"
            else (html.escape(str(probe.message)) if probe.message else "unavailable")
        )
        lines.append(
            f"<div style='margin:0.15rem 0;'>{dot}<b>{html.escape(label)}</b> "
            f"&nbsp;{body}</div>"
        )
    render_raw(
        "<div style='background:#FFFFFF;border:1px solid #E6E2F2;border-radius:10px;"
        "padding:0.55rem 0.8rem;'>" + "".join(lines) + "</div>"
    )


def render_sidebar() -> None:
    with st.sidebar:
        render_raw(
            "<div style='display:flex;align-items:baseline;gap:0.5rem;"
            "margin-bottom:0.1rem;'>"
            "<span style='font-size:1.35rem;font-weight:800;color:#1B1F2A;'>"
            f"{BRAND}</span>"
            "<span style='font-size:0.72rem;color:#6B7280;'>Knowledge Graph "
            "Intelligence Engine</span></div>"
        )
        st.caption(
            "Settings below override environment defaults for this browser "
            "session only."
        )

        with st.expander("Service status", expanded=False):
            _render_service_summary()

        with st.form("nexora_connection_form"):
            st.markdown("**Graph database (Neo4j)**")
            settings = current_settings()
            uri = st.text_input(
                "Connection URI",
                value=settings.neo4j_uri,
                key="field_uri",
                placeholder="bolt://127.0.0.1:7687",
            )
            col_user, col_db = st.columns(2)
            user = col_user.text_input(
                "User name", value=settings.neo4j_user, key="field_user"
            )
            database = col_db.text_input(
                "Database (optional)",
                value=settings.neo4j_database or "",
                key="field_database",
                help="Leave empty to use the server default database.",
            )
            password = st.text_input(
                "Password",
                value=settings.neo4j_password,
                type="password",
                key="field_password",
            )
            if password in ("", "change_me"):
                st.caption(
                    ":orange[Placeholder or empty password detected - set it "
                    "to the password your Neo4j server actually uses.]"
                )

            st.markdown("**Google Gemini API**")
            api_key = st.text_input(
                "API key",
                value=settings.gemini_api_key,
                type="password",
                key="field_api_key",
                help=(
                    "Create a key in Google AI Studio. Stored only for this "
                    "browser session; never written to disk."
                ),
            )
            model_name = st.text_input(
                "Model",
                value=settings.gemini_model,
                key="field_model",
                help="e.g. gemini-3.6-flash, gemini-3.5-flash.",
            )
            if not api_key.strip():
                st.caption(
                    ":orange[No Gemini API key set - extraction and answering "
                    "will fail until GEMINI_API_KEY is provided.]"
                )

            st.markdown("**Retrieval behaviour**")
            col_depth, col_cap = st.columns(2)
            depth = col_depth.slider(
                "Max graph hops", 1, 6, settings.retrieval_depth, key="field_depth"
            )
            cap = col_cap.slider(
                "Context entries", 4, 60, settings.context_cap, key="field_cap"
            )

            submitted = st.form_submit_button(
                "Save and reconnect", type="primary", width="stretch"
            )

        if submitted:
            updated = settings.with_overrides(
                neo4j_uri=uri.strip(),
                neo4j_user=user.strip(),
                neo4j_password=password,
                neo4j_database=(database.strip() or None),
                gemini_api_key=api_key.strip(),
                gemini_model=model_name.strip(),
                retrieval_depth=depth,
                context_cap=cap,
            )
            update_settings(updated)
            st.toast("Connection settings saved.")
            st.rerun()

        if st.button(
            "Reset to environment defaults",
            help="Discard manual overrides and reload values from .env.",
            width="stretch",
        ):
            reset_settings()
            st.toast("Reloaded environment defaults.")
            st.rerun()

        st.divider()
        with st.expander("About this workspace"):
            render_raw(
                "<p style='font-size:0.86rem;color:#6B7280;line-height:1.5;'>"
                "Nexora indexes documents as typed entities and links in Neo4j. "
                "Questions are answered by retrieving entry points, expanding "
                "through neighbouring entities and asking the Google Gemini API "
                "to reason over the assembled evidence. Every claim is expected "
                "to cite the evidence entries it relies on.</p>"
            )
        st.caption(f"{BRAND} {VERSION}")
