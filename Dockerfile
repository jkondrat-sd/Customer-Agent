# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder
WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies (frozen, no dev tools)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Final stage — lean runtime image
# ---------------------------------------------------------------------------
FROM python:3.11-slim
WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code (note: .dockerignore controls what gets included)
COPY . .

# Ensure the virtualenv is used by default
ENV PATH="/app/.venv/bin:$PATH"

# Make the startup script executable
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
