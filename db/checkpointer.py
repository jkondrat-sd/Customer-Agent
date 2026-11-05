"""Checkpointer factory for LangGraph state persistence.

Abstracts away the database adapter selection (PostgreSQL vs SQLite) from the
core graph definition, adhering to Dependency Inversion.
"""

import logging
import sqlite3
from contextlib import contextmanager

import config

logger = logging.getLogger(__name__)

@contextmanager
def get_checkpointer():
    """Auto-detect DATABASE_URL to choose PostgresSaver vs SqliteSaver.
    
    Uses PostgreSQL in production and gracefully falls back to SQLite for
    local development if PostgreSQL is unavailable or unconfigured.
    Yields a context manager that should be entered to maintain connection pool.
    """
    db_url = config.settings.database_url

    if db_url.startswith("postgresql"):
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg_pool import ConnectionPool

            logger.info("Using PostgreSQL checkpointer: %s", db_url[:30] + "...")
            
            # Use explicit pool to disable prepared statements (fixes Supabase pooler hangs)
            # and set a connection timeout so it fails cleanly instead of hanging forever.
            pool_kwargs = {
                "kwargs": {
                    "connect_timeout": 10,
                    "prepare_threshold": None,
                },
                "max_size": 10,
            }
            
            # Since get_checkpointer is a generator, we must manage the pool lifecycle
            pool = ConnectionPool(db_url, **pool_kwargs)
            try:
                with PostgresSaver(pool) as memory:
                    memory.setup()
                    yield memory
            finally:
                pool.close()
            return
        except Exception as e:
            logger.warning(
                "Failed to initialize PostgreSQL checkpointer (%s), falling back to SQLite.",
                e,
            )

    # Fallback: SQLite for local dev
    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect("support_platform_checkpoints.db", check_same_thread=False)
    logger.info("Using SQLite checkpointer (local dev)")
    try:
        memory = SqliteSaver(conn)
        memory.setup()
        yield memory
    finally:
        conn.close()
