FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY order-service/ ./order_service/

ENV PYTHONPATH=/app

EXPOSE 8001

CMD ["uv", "run", "python", "-m", "order_service.main"]