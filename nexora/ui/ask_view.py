"""Ask view: grounded question answering with traceable citations."""

from __future__ import annotations

import streamlit as st

from nexora.errors import AppError
from nexora.models import QueryAnswer
from nexora.samples import SUGGESTED_QUESTIONS
from nexora.ui.state import get_assistant, present_error
from nexora.ui.theme import render_answer_card, render_raw


def _question_picker() -> None:
    options = ["Custom question"] + list(SUGGESTED_QUESTIONS)
    suggestion = st.selectbox(
        "Try an example question",
        options,
        key="q_pick",
        help="Select an example to load it into the editor.",
    )
    if suggestion != "Custom question" and st.button(
        "Use this suggestion", use_container_width=True
    ):
        st.session_state["question_text"] = suggestion
        st.rerun()


def _ask() -> None:
    question = st.session_state.get("question_text", "").strip()
    if not question:
        st.warning("Type a question first.")
        return
    try:
        assistant = get_assistant()
        with st.spinner("Retrieving evidence from the graph and reasoning..."):
            answer = assistant.ask_question(question)
        st.session_state["last_question"] = question
        st.session_state["last_answer"] = answer
    except AppError as exc:
        present_error(exc, hint="question answering")


def _render_audit(audit: tuple[str, ...]) -> None:
    if not audit:
        return
    with st.expander("How this answer was assembled"):
        for step in audit:
            st.markdown(f"- {step}")


def _render_answer(answer: QueryAnswer) -> None:
    _render_audit(answer.audit)
    render_answer_card(answer.text)

    st.markdown("#### Source evidence")
    if not answer.references:
        st.caption(
            "The answer did not cite specific evidence entries. It may be a "
            "qualification or a general statement, or the model omitted "
            "inline references."
        )
        return

    for ref in answer.references:
        title = f"[{ref.index}] {ref.entity or 'Unnamed entity'}"
        if ref.document:
            title += f"  ·  {ref.document}"
        with st.expander(title):
            if ref.quote:
                st.markdown("**Excerpt from the source:**")
                st.write(ref.quote)
            if ref.route:
                st.markdown("**How this entity was reached in the graph:**")
                for hop in ref.route:
                    render_raw(
                        f"<div class='nex-code' style='padding:0.15rem 0.5rem;"
                        f"margin:0.15rem 0;'>{_escape(hop)}</div>"
                    )
            else:
                st.caption(
                    "Entry point - this entity matched your question keywords "
                    "directly in the graph."
                )


def _escape(value: str) -> str:
    import html

    return html.escape(value)


def render() -> None:
    st.header("Ask a question")
    st.caption(
        "Nexora turns your question into search terms, finds matching entry "
        "points in the graph, expands several hops through related entities "
        "and asks the local model to answer strictly from that evidence."
    )

    if "question_text" not in st.session_state:
        st.session_state["question_text"] = SUGGESTED_QUESTIONS[0]

    _question_picker()

    with st.form("nexora_question_form"):
        st.text_area(
            "Question",
            key="question_text",
            height=120,
            label_visibility="collapsed",
            placeholder=(
                "e.g. Who founded Aster Systems and which product did it build?"
            ),
        )
        ask_clicked = st.form_submit_button(
            "Get grounded answer", type="primary", use_container_width=True
        )

    if ask_clicked:
        _ask()

    last = st.session_state.get("last_answer")
    if last is None:
        st.info(
            "No answer rendered yet. Ask a question above - the answer and its "
            "sources will appear here."
        )
        return

    st.caption(f"Question: {st.session_state.get('last_question', '')}")
    st.divider()
    _render_answer(last)
