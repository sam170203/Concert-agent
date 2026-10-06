FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY concert_agent ./concert_agent
RUN pip install --no-cache-dir .

ENV PORT=8000
CMD ["sh", "-c", "uvicorn concert_agent.main:app --host 0.0.0.0 --port ${PORT}"]
