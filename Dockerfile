FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY verigraph ./verigraph

EXPOSE 8501

ENV NEO4J_URI=bolt://127.0.0.1:7687 \
    NEO4J_USER=neo4j \
    NEO4J_PASSWORD=password \
    OLLAMA_BASE_URL=http://127.0.0.1:11434 \
    OLLAMA_MODEL=llama3.2

CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
