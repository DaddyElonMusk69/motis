FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy workspace packages first (for layer caching)
COPY ../../packages /packages

# Install dependencies
COPY pyproject.toml .
RUN uv pip install --system -e /packages/shared -e /packages/operator_sdk -e .

# Copy source
COPY motis_agent ./motis_agent

ENV PYTHONPATH=/app
ENV PORT=8001

EXPOSE 8001

CMD ["uvicorn", "motis_agent.server:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
