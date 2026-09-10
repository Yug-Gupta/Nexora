"""Ingest view: turn plain text into knowledge graph records."""

from __future__ import annotations

import streamlit as st

from nexora.errors import AppError
from nexora.models import IngestReport
from nexora.samples import SAMPLE_DOCUMENTS
from nexora.ui.state import get_assistant, present_error, remember_overview
from nexora.ui.theme import render_metric_grid

_DEFAULT_LABEL = "Unlabelled note"


def _select_source() -> str | None:
    picker_options = ["Custom text"] + list(SAMPLE_DOCUMENTS)
    if "sample_pick" not in st.session_state:
        st.session_state["sample_pick"] = picker_options[0]
    picked = st.selectbox(
        "Start from",
        picker_options,
        key="sample_pick",
        label_visibility="collapsed",
    )
    if picked != "Custom text" and st.button(
        "Load this example into the editor", use_container_width=True
    ):
        st.session_state["src_text"] = SAMPLE_DOCUMENTS[picked]
        st.session_state["src_label"] = picked
        st.rerun()
    return picked


def _run_ingestion() -> None:
    text = st.session_state.get("src_text", "")
    label = st.session_state.get("src_label", "").strip() or _DEFAULT_LABEL
    if not text.strip():
        st.warning("Add some document text before analysing.")
        return
    try:
        assistant = get_assistant()
        with st.spinner("Extracting entities and relationships with Gemini..."):
            report = assistant.ingest_document(
                document_text=text,
                source_label=label,
            )
        remember_overview(assistant.overview())
        _render_ingest_report(report)
    except AppError as exc:
        present_error(exc, hint="document ingestion")


def _render_ingest_report(report: IngestReport) -> None:
    st.success(
        f"Indexed **{report.entity_count}** entities and "
        f"**{report.relation_count}** relationships from "
        f"`{report.source_label}`."
    )
    render_metric_grid(
        [
            ("Entities indexed", str(report.entity_count)),
            ("Relationships", str(report.relation_count)),
            (
                "Relationships dropped",
                str(report.dropped_relations),
            ),
        ]
    )
    if report.dropped_relations:
        st.warning(
            f"{report.dropped_relations} relationship(s) were skipped because an "
            "endpoint entity was not present in the graph."
        )

    tab_entities, tab_relations = st.tabs(
        ["Extracted entities", "Extracted relationships"]
    )
    with tab_entities:
        if report.entities:
            st.dataframe(
                [
                    {
                        "Name": entity.name,
                        "Type": entity.kind,
                        "Summary": entity.summary,
                    }
                    for entity in report.entities
                ],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("No entities were extracted.")
    with tab_relations:
        if report.relations:
            st.dataframe(
                [
                    {
                        "From": rel.subject,
                        "Predicate": rel.predicate,
                        "To": rel.object,
                        "Rationale": rel.rationale,
                    }
                    for rel in report.relations
                ],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("No relationships were extracted.")


def render() -> None:
    st.header("Ingest knowledge")
    st.caption(
        "Paste a document below, or load one of the built-in examples. The "
        "Gemini model extracts typed entities and the relationships between "
        "them, and Nexora writes them into the Neo4j knowledge graph."
    )

    _select_source()

    col_text, col_side = st.columns([3, 1], gap="large")
    with col_text:
        st.text_area(
            "Document text",
            key="src_text",
            height=320,
            label_visibility="collapsed",
            placeholder=(
                "Paste a paragraph describing an organisation, a product, an "
                "event or any connected set of facts here..."
            ),
        )
        st.caption("The longer and clearer the text, the better the extraction.")
    with col_side:
        st.markdown("**Reference label**")
        st.text_input(
            "Label",
            key="src_label",
            label_visibility="collapsed",
            placeholder=_DEFAULT_LABEL,
        )
        st.caption("Used to name this source in the graph and in citations.")
        run_ingest = st.button(
            "Analyse and index", type="primary", use_container_width=True
        )
        with st.expander("What happens next?"):
            st.markdown(
                "- The model returns structured JSON (entities + relations).\n"
                "- Entities are merged into the graph by stable name.\n"
                "- Relationships are kept only when both endpoints exist.\n"
                "- Review the extraction below and then ask questions about it."
            )

    if run_ingest:
        _run_ingestion()
