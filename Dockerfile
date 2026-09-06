FROM python:3.11-slim

# Non-interactive pip and Streamlit (no first-run prompts in containers).
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code and the visual theme configuration.
COPY app.py .
COPY nexora ./nexora
COPY .streamlit ./.streamlit

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 nexora
USER nexora

EXPOSE 8501

ENV NEO4J_URI=bolt://127.0.0.1:7687 \
    NEO4J_USER=neo4j \
    NEO4J_PASSWORD=password \
    OLLAMA_BASE_URL=http://127.0.0.1:11434 \
    OLLAMA_MODEL=llama3.2

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=5)"

CMD ["streamlit", "run", "app.py", \
     "--server.address", "0.0.0.0", \
     "--server.port", "8501", \
     "--server.headless", "true", \
     "--server.fileWatcherType", "none"]
