"""System status view: diagnostics, graph overview and the danger zone."""

from __future__ import annotations

import streamlit as st

from nexora.errors import AppError
from nexora.models import StoreOverview
from nexora.ui.state import (
    cached_overview,
    get_assistant,
    present_error,
    remember_overview,
    remember_probes,
)
from nexora.ui.theme import render_metric_grid, render_raw, status_pill


def _run_diagnostics() -> None:
    try:
        assistant = get_assistant()
        with st.spinner("Probing Neo4j and Ollama..."):
            probes = assistant.health_report()
            overview = assistant.overview()
        remember_probes(probes)
        remember_overview(overview)
    except AppError as exc:
        present_error(exc, hint="diagnostics")


def _render_probes(probes) -> None:
    for probe in probes:
        render_raw(
            f"<div style='margin:0.35rem 0;'>{status_pill(probe.available)} "
            f"<b>{_escape(probe.component)}</b> &nbsp;-&nbsp; {_escape(probe.message)}"
        )
        if probe.extra:
            with st.expander(f"Installed models ({len(probe.extra)})"):
                for tag in probe.extra:
                    st.code(tag, language=None)


def _render_overview(overview: StoreOverview | None) -> None:
    st.markdown("#### Current graph contents")
    if overview is None:
        st.caption("Not measured yet - run diagnostics to refresh.")
        return
    render_metric_grid(
        [
            ("Entities indexed", str(overview.node_count)),
            ("Relationships", str(overview.edge_count)),
            ("Source documents", str(overview.document_count)),
        ]
    )
    if overview.sources:
        st.markdown("**Indexed documents**")
        for source in overview.sources:
            st.markdown(f"- {source}")
    else:
        st.caption("No documents indexed yet. Ingest a document on the first tab.")


def _render_danger_zone() -> None:
    st.markdown("#### Danger zone")
    if not st.session_state.get("confirm_wipe", False):
        if st.button(
            "Erase the entire graph",
            help="Removes every entity, relationship and document record.",
        ):
            st.session_state["confirm_wipe"] = True
            st.rerun()
        return

    st.warning(
        "This removes every node and relationship from the database, "
        "including all document provenance records. This cannot be undone."
    )
    col_yes, col_no = st.columns(2)
    if col_yes.button("Yes, erase everything", type="primary"):
        st.session_state["confirm_wipe"] = False
        try:
            assistant = get_assistant()
            assistant.reset_graph()
            remember_overview(None)
            st.session_state.pop("last_probes", None)
            st.toast("The knowledge graph has been erased.")
            st.rerun()
        except AppError as exc:
            present_error(exc, hint="graph reset")
    if col_no.button("Cancel"):
        st.session_state["confirm_wipe"] = False
        st.rerun()


def _escape(value: object) -> str:
    import html

    return html.escape(str(value))


def render() -> None:
    st.header("System status")
    st.caption(
        "Probe the live connectivity of Neo4j and Ollama, review what is "
        "stored in the graph, or reset the workspace."
    )

    if st.button("Run diagnostics", type="primary"):
        _run_diagnostics()

    probes = st.session_state.get("last_probes")
    st.markdown("#### Service health")
    if probes is None:
        st.caption("Not checked yet - press **Run diagnostics** to probe services.")
    else:
        _render_probes(probes)

    st.divider()
    _render_overview(cached_overview())

    st.divider()
    _render_danger_zone()
