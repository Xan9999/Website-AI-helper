# Website-AI-helper app container (the FastAPI backend only — the LLM servers
# and Qdrant run as separate services; see docker-compose.yml).
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY website_ai_helper ./website_ai_helper
RUN pip install --no-cache-dir .

# Conversations DB + (embedded-mode) vector data land here; mount a volume.
ENV DATA_DIR=/app/data
EXPOSE 8000

CMD ["website-ai-helper", "serve", "--host", "0.0.0.0", "--port", "8000"]
