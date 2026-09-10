"""Shared theme: brand palette, page CSS and small HTML rendering helpers.

The presentation layer uses a small amount of carefully escaped HTML for
layout cards and badges, on top of Streamlit's own widgets.
"""

from __future__ import annotations

import html
import re

import streamlit as st

from nexora import __app_name__, __tagline__, __version__

# Brand ------------------------------------------------------------------------
BRAND = __app_name__
TAGLINE = __tagline__
VERSION = __version__

PRIMARY_HEX = "#6C5CE7"
PRIMARY_LIGHT_HEX = "#EFEBFC"

PAGE_CSS = """
<style>
:root {
  --nex-accent: #6C5CE7;
  --nex-accent-soft: #EFEBFC;
  --nex-ink: #1B1F2A;
  --nex-muted: #6B7280;
  --nex-line: #E6E2F2;
  --nex-panel: #FAF9FE;
  --nex-ok: #14804A;
  --nex-ok-bg: #E5F5EC;
  --nex-bad: #C0392B;
  --nex-bad-bg: #FCEBEA;
  --nex-warn: #8A6D00;
  --nex-warn-bg: #FBF3D9;
}

.stApp { background: #FFFFFF; }
.block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1240px; }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }

/* Hero ------------------------------------------------------------- */
.nex-hero {
  background: linear-gradient(120deg, #F6F4FE 0%, #EEF0FC 55%, #F2FAF8 100%);
  border: 1px solid var(--nex-line);
  border-radius: 18px;
  padding: 1.4rem 1.6rem 1.2rem;
  margin-bottom: 1.1rem;
}
.nex-hero .nex-brand {
  display: flex; align-items: baseline; gap: 0.8rem; flex-wrap: wrap;
}
.nex-hero .nex-wordmark {
  font-size: 1.9rem; font-weight: 800; letter-spacing: -0.02em;
  color: var(--nex-ink); line-height: 1;
}
.nex-hero .nex-tag {
  font-size: 0.95rem; font-weight: 600; color: var(--nex-accent);
  letter-spacing: 0.01em;
}
.nex-hero .nex-lede {
  color: var(--nex-muted); font-size: 0.95rem; margin: 0.5rem 0 0.85rem;
  max-width: 900px; line-height: 1.5;
}
.nex-pipeline {
  display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center;
  color: var(--nex-muted); font-size: 0.78rem;
}
.nex-stage {
  background: #FFFFFF; border: 1px solid var(--nex-line); border-radius: 999px;
  padding: 0.22rem 0.7rem; font-weight: 600; color: #4B4453;
}
.nex-arrow { color: var(--nex-accent); font-weight: 700; }

/* Status pills ----------------------------------------------------- */
.status-pill { display: inline-block; padding: 0.12rem 0.65rem; border-radius: 999px;
  font-size: 0.75rem; font-weight: 650; vertical-align: middle; }
.pill-ok   { background: var(--nex-ok-bg); color: var(--nex-ok); }
.pill-bad  { background: var(--nex-bad-bg); color: var(--nex-bad); }
.pill-muted{ background: #EEEEF4; color: #6B7280; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 0.35rem; }
.dot-ok { background: #23A55A; }
.dot-bad { background: #E5484D; }
.dot-idle { background: #C6C6D2; }

/* Answer card ------------------------------------------------------ */
.nex-card {
  background: var(--nex-panel); border: 1px solid var(--nex-line);
  border-radius: 14px; padding: 1rem 1.25rem; margin: 0.5rem 0 1rem;
}
.nex-card-label {
  font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.1em;
  color: var(--nex-accent); font-weight: 750; margin-bottom: 0.45rem;
}
.nex-card p { margin: 0.4rem 0; line-height: 1.55; color: var(--nex-ink); }
.nex-card ul { margin: 0.3rem 0 0.3rem 1.1rem; padding-left: 0.4rem; }
.nex-card li { margin: 0.2rem 0; line-height: 1.5; }

/* Metric cards ----------------------------------------------------- */
.nex-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.7rem; margin: 0.4rem 0 0.9rem; }
.nex-metric {
  background: #FFFFFF; border: 1px solid var(--nex-line); border-radius: 12px;
  padding: 0.7rem 0.9rem;
}
.nex-metric .num { font-size: 1.5rem; font-weight: 800; color: var(--nex-accent); line-height: 1.1; }
.nex-metric .lab { font-size: 0.74rem; color: var(--nex-muted); text-transform: uppercase; letter-spacing: 0.06em; margin-top: 0.15rem; }

/* Small utilities -------------------------------------------------- */
.nex-note { color: var(--nex-muted); font-size: 0.85rem; }
.nex-code { font-family: ui-monospace, "Cascadia Code", Consolas, monospace; font-size: 0.84em; background: #F1EFFA; border-radius: 5px; padding: 0.05rem 0.35rem; }
.section-title { font-size: 1.15rem; font-weight: 700; color: var(--nex-ink); margin-top: 0.4rem; }
div[data-testid="stExpander"] details summary { font-weight: 600; }
.stTabs [data-baseweb="tab-list"] { gap: 0.4rem; }
.stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; padding: 0.45rem 1rem; font-weight: 600; }
</style>
"""


def render_raw(markup: str) -> None:
    """Emit trusted, pre-escaped HTML."""
    st.markdown(markup, unsafe_allow_html=True)


def render_hero() -> None:
    """Render the Nexora masthead with the core pipeline callout."""
    render_raw(PAGE_CSS)
    render_raw(
        f"""
        <div class="nex-hero">
          <div class="nex-brand">
            <span class="nex-wordmark">Nexora</span>
            <span class="nex-tag">{TAGLINE}</span>
          </div>
          <p class="nex-lede">
            Turn your documents into a queryable knowledge graph. Nexora
            extracts typed entities and relationships into Neo4j, retrieves
            evidence by walking the graph (multi-hop), and answers natural
            language questions with Google Gemini - every claim traceable to
            the source it came from.
          </p>
          <div class="nex-pipeline">
            <span class="nex-stage">Document</span><span class="nex-arrow">→</span>
            <span class="nex-stage">Extraction</span><span class="nex-arrow">→</span>
            <span class="nex-stage">Neo4j graph</span><span class="nex-arrow">→</span>
            <span class="nex-stage">Multi-hop retrieval</span><span class="nex-arrow">→</span>
            <span class="nex-stage">Grounded answer</span><span class="nex-arrow">→</span>
            <span class="nex-stage">Citations</span>
          </div>
        </div>
        """
    )


def render_metric_grid(items: list[tuple[str, str]]) -> None:
    """Render value/label tiles (``value`` is pre-escaped)."""
    tiles = "".join(
        f"<div class='nex-metric'><div class='num'>{value}</div>"
        f"<div class='lab'>{html.escape(label)}</div></div>"
        for label, value in items
    )
    render_raw(f"<div class='nex-metrics'>{tiles}</div>")


def status_pill(available: bool) -> str:
    css = "pill-ok" if available else "pill-bad"
    text = "Available" if available else "Unavailable"
    return f"<span class='status-pill {css}'>{text}</span>"


def status_dot(available: bool | None) -> str:
    css = "dot-ok" if available else "dot-bad" if available is False else "dot-idle"
    return f"<span class='dot {css}'></span>"


def _bold_aware(value: str) -> str:
    """Turn escaped ``**text**`` markers into strong elements."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)


def render_answer_markup(text: str) -> str:
    """Render model output as safe HTML inside an answer card.

    Plain text is HTML-escaped first, so model output can never inject
    markup.  ``**bold**`` spans and ``- bullet`` lines are then promoted to
    simple formatting for readability.
    """
    escaped = html.escape(text)
    rendered: list[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            rendered.append("</ul>")
            in_list = False

    for raw_line in escaped.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            close_list()
            continue
        if re.match(r"^[-*•]\s+", line):
            if not in_list:
                rendered.append("<ul>")
                in_list = True
            item = re.sub(r"^[-*•]\s+", "", line)
            rendered.append(f"<li>{_bold_aware(item)}</li>")
            continue
        close_list()
        rendered.append(f"<p>{_bold_aware(line)}</p>")
    close_list()
    return "".join(rendered) if rendered else escaped


def render_answer_card(text: str) -> None:
    markup = (
        "<div class='nex-card'><div class='nex-card-label'>Answer</div>"
        f"{render_answer_markup(text)}</div>"
    )
    render_raw(markup)
