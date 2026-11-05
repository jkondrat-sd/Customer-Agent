#!/bin/sh
echo "Starting FlowDesk support-gateway..."
alembic upgrade head 2>&1 && echo "Migrations applied." || echo "Alembic skipped (non-fatal)."
echo "Launching uvicorn on port ${PORT:-8080}..."
exec uvicorn gateway.main:app --host 0.0.0.0 --port "${PORT:-8080}" --log-level info
