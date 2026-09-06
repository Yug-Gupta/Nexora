"""Verigraph - Streamlit interface.

This module is intentionally the *only* one that imports Streamlit.
It renders screens, collects user intent and delegates every real action
to :class:`~verigraph.service.KnowledgeAssistant`.  No Cypher, prompts or
connection strings appear here.
"""

from __future__ import annotations

import html
import logging

import streamlit as st

from verigraph.config import Settings, configure_logging
from verigraph import __version__
from verigraph.errors import AppError
from verigraph.models import IngestReport, QueryAnswer, StoreOverview
from verigraph.samples import SAMPLE_DOCUMENTS, SUGGESTED_QUESTIONS
from verigraph.service import KnowledgeAssistant

logger = logging.getLogger(__name__)

_BRAND = "Verigraph"

_PAGE_CSS = """
<style>
.block-container { padding-top: 2.2rem; max-width: 1200px; }
.hero { border-bottom: 1px solid #ece7f6; margin-bottom: 1.4rem; }
.hero h1 { font-size: 2.1rem; font-weight: 750; letter-spacing: -0.02em;
           color: #241d3a; margin-bottom: 0.15rem; }
.hero p { color: #6b7280; margin-top: 0; }
.answer-card { background: #faf8ff; border: 1px solid #e5ddf7; border-radius: 14px;
               padding: 1.1rem 1.3rem; margin-top: 0.3rem; }
.answer-card .answer-label { font-size: 0.78rem; text-transform: uppercase;
               letter-spacing: 0.08em; color: #7c6bb5; font-weight: 650; }
.status-pill { display: inline-block; padding: 0.1rem 0.7rem; border-radius: 999px;
               font-size: 0.78rem; font-weight: 600; margin-right: 0.4rem; }
.status-ok { background: #e6f6ee; color: #157347; }
.status-bad { background: #fdeaea; color: #b02a37; }
</style>
"""


# --------------------------------------------------------------------------- #
# Small UI primitives
# --------------------------------------------------------------------------- #

def _markdown(text: str) -> None:
    st.markdown(text, unsafe_allow_html=True)


def _render_hero() -> None:
    _markdown(_PAGE_CSS)
    _markdown(
        f"""
        <div class="hero">
          <h1>{_BRAND}</h1>
          <p>Graph-grounded question answering with traceable source evidence.
          Documents become an entity graph in Neo4j; questions are answered by
          a local model over facts retrieved by walking that graph.</p>
        </div>
        """
    )


def _overview_metrics(overview: StoreOverview | None) -> None:
    if overview is None:
        st.caption("Run a graph overview to see its contents.")
        return
    first, second, third = st.columns(3)
    first.metric("Entities indexed", overview.node_count)
    second.metric("Relationships", overview.edge_count)
    third.metric("Source documents", len(overview.sources))


def _present_error(exc: Exception, *, hint: str = "") -> None:
    """Render any expected failure in a readable way and log the detail."""
    if isinstance(exc, AppError):
        logger.warning("%s (user=%s): %s", hint or exc.message, exc.message, exc.detail)
        st.error(exc.message)
        if exc.detail:
            st.caption(f"Diagnostic detail: {exc.detail}")
    else:
        logger.exception("Unexpected failure during %s", hint or "operation")
        st.error("Something unexpected went wrong. See the logs for details.")


# --------------------------------------------------------------------------- #
# Session plumbing
# --------------------------------------------------------------------------- #

def _seed_settings() -> Settings:
    if "settings" not in st.session_state:
        st.session_state["settings"] = Settings.from_environment()
    return st.session_state["settings"]


def _get_assistant() -> KnowledgeAssistant:
    """Return a cached assistant or rebuild it when settings changed."""
    settings = _seed_settings()
    slot = st.session_state.get("assistant_slot")
    if slot is not None and slot[0] == settings.signature():
        return slot[1]
    if slot is not None:
        try:
            slot[1].close()
        except Exception:
            logger.debug("Closed previous assistant", exc_info=True)
    assistant = KnowledgeAssistant(settings)
    st.session_state["assistant_slot"] = (settings.signature(), assistant)
    st.session_state.pop("cached_overview", None)
    return assistant


def _remember_overview(overview: StoreOverview | None) -> None:
    st.session_state["cached_overview"] = overview


def _cached_overview() -> StoreOverview | None:
    return st.session_state.get("cached_overview")


# --------------------------------------------------------------------------- #
# Sidebar: connections + about
# --------------------------------------------------------------------------- #

def _sidebar(settings: Settings) -> None:
    with st.sidebar:
        _markdown(f"### {_BRAND}")
        st.caption("Settings below override environment defaults for the "
                   "current browser session.")

        with st.form("connection_form"):
            st.markdown("**Graph database**")
            uri = st.text_input(
                "Connection URI", value=settings.neo4j_uri, key="field_uri"
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

            st.markdown("**Local model service**")
            ollama_url = st.text_input(
                "Ollama endpoint", value=settings.ollama_url, key="field_ollama"
            )
            model_name = st.text_input(
                "Model tag", value=settings.model_name, key="field_model",
                help="Run 'ollama list' to see installed tags.",
            )

            st.markdown("**Retrieval behaviour**")
            col_depth, col_cap = st.columns(2)
            depth = col_depth.slider(
                "Max graph hops", 1, 4, settings.retrieval_depth, key="field_depth"
            )
            cap = col_cap.slider(
                "Context entries", 4, 40, settings.context_cap, key="field_cap"
            )

            submitted = st.form_submit_button(
                "Save and reconnect", type="primary"
            )

        if submitted:
            updated = settings.with_overrides(
                neo4j_uri=uri.strip(),
                neo4j_user=user.strip(),
                neo4j_password=password,
                neo4j_database=(database.strip() or None),
                ollama_url=ollama_url.strip(),
                model_name=model_name.strip(),
                retrieval_depth=depth,
                context_cap=cap,
            )
            st.session_state["settings"] = updated
            st.session_state.pop("assistant_slot", None)
            st.toast("Connection settings saved.")
            st.rerun()

        st.divider()
        with st.expander("About this workspace"):
            _markdown(
                f"<p style='font-size:0.9rem; color:#6b7280;'>"
                f"{_BRAND} indexes documents as typed entities and links in "
                "Neo4j. Questions are answered by retrieving entry points, "
                "expanding through neighbouring entities and asking a local "
                "model to reason over the assembled evidence. Every claim is "
                "expected to cite the evidence entries it relies on.</p>"
            )
        st.caption(f"{_BRAND} {__version__}")


# --------------------------------------------------------------------------- #
# Tab 1 - source intake
# --------------------------------------------------------------------------- #

def _tab_ingest() -> None:
    st.header("Add source documents")
    st.caption(
        "Paste text below, or load one of the built-in examples. The local "
        "model extracts entities and relationships, which are then written "
        "into the graph."
    )

    picker_options = ["Custom text"] + list(SAMPLE_DOCUMENTS)
    if "sample_pick" not in st.session_state:
        st.session_state["sample_pick"] = picker_options[0]
    picked = st.selectbox(
        "Start from", picker_options, key="sample_pick", label_visibility="collapsed"
    )

    first_label = "Unlabelled note"
    if "src_label" not in st.session_state:
        st.session_state["src_label"] = first_label
    if "src_text" not in st.session_state:
        st.session_state["src_text"] = ""

    if picked != "Custom text" and st.button("Load this example into the editor"):
        st.session_state["src_text"] = SAMPLE_DOCUMENTS[picked]
        st.session_state["src_label"] = picked
        st.rerun()

    col_text, col_side = st.columns([3, 1])
    with col_text:
        st.text_area(
            "Document text",
            key="src_text",
            height=300,
            label_visibility="collapsed",
            placeholder=(
                "Paste a paragraph describing an organisation, product or "
                "event here..."
            ),
        )
    with col_side:
        st.markdown("**Reference label**")
        st.text_input(
            "Label", key="src_label", label_visibility="collapsed",
            placeholder=first_label,
        )
        st.caption("Used to name this source in citations.")
        run_ingest = st.button(
            "Analyse and index", type="primary"
        )

    if run_ingest:
        if not st.session_state["src_text"].strip():
            st.warning("Add some document text before analysing.")
            return
        try:
            assistant = _get_assistant()
            with st.spinner("Extracting entities and relationships..."):
                report = assistant.ingest_document(
                    document_text=st.session_state["src_text"],
                    source_label=st.session_state["src_label"] or first_label,
                )
            _render_ingest_report(report)
            _remember_overview(assistant.overview())
        except AppError as exc:
            _present_error(exc, hint="document ingestion")


def _render_ingest_report(report: IngestReport) -> None:
    first, second = st.columns(2)
    first.success(
        f"Indexed {report.entity_count} entities and "
        f"{report.relation_count} relationships from "
        f"'{report.source_label}'."
    )
    if report.dropped_relations:
        second.warning(
            f"{report.dropped_relations} relationship(s) skipped because an "
            "endpoint entity was not present in the graph."
        )
    else:
        second.info("All extracted relationships connected to known entities.")

    tab_entities, tab_relations = st.tabs(["Entities", "Relationships"])
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
            )
        else:
            st.write("No entities were extracted.")
    with tab_relations:
        if report.relations:
            st.dataframe(
                [
                    {
                        "From": rel.subject,
                        "Predicate": rel.predicate,
                        "To": rel.object,
                        "Context": rel.rationale,
                    }
                    for rel in report.relations
                ],
                hide_index=True,
            )
        else:
            st.write("No relationships were extracted.")


# --------------------------------------------------------------------------- #
# Tab 2 - questions
# --------------------------------------------------------------------------- #

def _tab_ask() -> None:
    st.header("Ask a question")
    st.caption(
        "Your question is turned into search terms, entry points in the graph "
        "are expanded a few hops, and the gathered evidence is passed to the "
        "local model with an instruction to cite each claim."
    )

    if "question_text" not in st.session_state:
        st.session_state["question_text"] = SUGGESTED_QUESTIONS[0]

    suggestion = st.selectbox(
        "Suggested questions",
        ["Custom"] + list(SUGGESTED_QUESTIONS),
        key="q_pick",
        label_visibility="collapsed",
    )
    if suggestion != "Custom" and st.button("Use this suggestion"):
        st.session_state["question_text"] = suggestion
        st.rerun()

    with st.form("question_form"):
        st.text_area(
            "Question",
            key="question_text",
            height=100,
            label_visibility="collapsed",
            placeholder="e.g. Who built Cirrus and which firm funds its growth?",
        )
        ask_clicked = st.form_submit_button(
            "Get grounded answer", type="primary"
        )

    if ask_clicked:
        question = st.session_state["question_text"].strip()
        if not question:
            st.warning("Type a question first.")
            return
        try:
            assistant = _get_assistant()
            with st.spinner("Retrieving evidence and reasoning..."):
                answer = assistant.ask_question(question)
            st.session_state["last_answer"] = answer
            st.session_state["last_question"] = question
        except AppError as exc:
            _present_error(exc, hint="question answering")

    last = st.session_state.get("last_answer")
    if last is None:
        st.info(
            "No answer rendered yet. Ask a question above; the result and its "
            "sources will appear here."
        )
        return
    _render_answer(st.session_state.get("last_question", ""), last)


def _render_answer(question: str, answer: QueryAnswer) -> None:
    st.divider()
    st.caption(f"Question: {question}")

    with st.expander(f"Show reasoning log ({len(answer.audit)} steps)"):
        for step in answer.audit:
            st.markdown(f"- {step}")

    _markdown(
        "<div class='answer-card'>"
        "<span class='answer-label'>Answer</span>"
        f"<div style='margin-top:0.4rem;'>{_as_paragraphs(answer.text)}</div>"
        "</div>"
    )

    st.subheader("Source evidence")
    if not answer.references:
        st.caption(
            "The answer did not cite specific evidence entries. It may be a "
            "qualification or a general statement."
        )
        return

    for ref in answer.references:
        title = f"[{ref.index}] {ref.entity or 'Unnamed entity'}"
        if ref.document:
            title += f"  -  {ref.document}"
        with st.expander(title):
            if ref.quote:
                st.markdown("**Excerpt from the source:**")
                st.write(ref.quote)
            if ref.route:
                st.markdown("**How this entity was reached in the graph:**")
                for hop in ref.route:
                    st.markdown(f"- `{hop}`")


def _as_paragraphs(text: str) -> str:
    """Render model output inside a styled card, honouring line breaks."""
    escaped = html.escape(text)
    paragraphs = [
        f"<p style='margin:0.35rem 0;'>{chunk}</p>"
        for chunk in escaped.splitlines()
        if chunk.strip()
    ]
    return "".join(paragraphs) if paragraphs else escaped


# --------------------------------------------------------------------------- #
# Tab 3 - system status
# --------------------------------------------------------------------------- #

def _tab_status() -> None:
    st.header("System status")
    st.caption(
        "Checks the live connectivity of Neo4j and the Ollama service, and "
        "shows what is currently stored in the graph."
    )

    if st.button("Run diagnostics", type="primary"):
        try:
            assistant = _get_assistant()
            with st.spinner("Probing services..."):
                probes = assistant.health_report()
                overview = assistant.overview()
        except AppError as exc:
            _present_error(exc, hint="diagnostics")
            return
        st.session_state["last_probes"] = probes
        st.session_state["last_overview_run"] = overview
        _remember_overview(overview)

    probes = st.session_state.get("last_probes")
    if probes is not None:
        for probe in probes:
            pill = (
                "<span class='status-pill status-ok'>Available</span>"
                if probe.available
                else "<span class='status-pill status-bad'>Unavailable</span>"
            )
            _markdown(f"{pill} **{probe.component}**  -  {probe.message}")
            if probe.extra:
                st.caption("Installed: " + ", ".join(probe.extra))

    overview = _cached_overview()
    st.markdown("**Current graph contents**")
    if overview is None:
        st.caption("Not measured yet. Run diagnostics to refresh.")
    else:
        _overview_metrics(overview)
        if overview.sources:
            st.markdown("**Indexed documents**")
            for source in overview.sources:
                st.markdown(f"- {source}")

    st.divider()
    st.markdown("**Danger zone**")
    if not st.session_state.get("confirm_wipe", False):
        if st.button("Erase the entire graph"):
            st.session_state["confirm_wipe"] = True
            st.rerun()
    else:
        st.warning(
            "This removes every entity and relationship from the database. "
            "This cannot be undone."
        )
        col_yes, col_no = st.columns(2)
        if col_yes.button("Yes, erase everything", type="primary"):
            st.session_state["confirm_wipe"] = False
            try:
                assistant = _get_assistant()
                assistant.reset_graph()
                _remember_overview(None)
                st.session_state.pop("last_overview_run", None)
                st.success("The graph has been erased.")
            except AppError as exc:
                _present_error(exc, hint="graph reset")
        if col_no.button("Cancel"):
            st.session_state["confirm_wipe"] = False
            st.rerun()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main() -> None:
    configure_logging(Settings.from_environment().log_level)
    st.set_page_config(
        page_title=f"{_BRAND} - Graph Grounded QA",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _render_hero()
    _sidebar(_seed_settings())

    tab_intake, tab_ask, tab_status = st.tabs(
        ["Add sources", "Ask questions", "System status"]
    )
    with tab_intake:
        _tab_ingest()
    with tab_ask:
        _tab_ask()
    with tab_status:
        _tab_status()


if __name__ == "__main__":
    main()
