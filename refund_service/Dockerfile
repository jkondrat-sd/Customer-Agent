FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY refund-service/ ./refund_service/

ENV PYTHONPATH=/app

EXPOSE 8002

CMD ["uv", "run", "python", "-m", "refund_service.main"]