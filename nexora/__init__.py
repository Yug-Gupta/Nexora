"""Nexora - Knowledge Graph Intelligence Engine.

Nexora turns unstructured documents into a typed knowledge graph inside
Neo4j, then answers natural-language questions by walking that graph
(multi-hop retrieval) and letting the Google Gemini API compose grounded,
traceable answers over the retrieved evidence.

The package is split into focused layers:

* ``nexora.config``     - central settings record + logging bootstrap
* ``nexora.errors``     - typed application errors and translator helpers
* ``nexora.models``     - domain records shared across every layer
* ``nexora.db``         - Neo4j connection, Cypher statements and repository
* ``nexora.llm``        - Gemini gateway and prompt templates
* ``nexora.pipeline``   - extraction, retrieval and answering stages
* ``nexora.ui``         - Streamlit presentation layer (imports Streamlit)
* ``nexora.service``    - the facade that wires everything for the UI
"""

__version__ = "1.0.0"
__app_name__ = "Nexora"
__tagline__ = "Knowledge Graph Intelligence Engine"
