#!/usr/bin/env python3
"""Create all tables (sync, used at container startup before the async app starts)."""

import os
import psycopg2

DDL = """
CREATE TABLE IF NOT EXISTS search_queries (
    query             VARCHAR(255) PRIMARY KEY,
    frequency         BIGINT       NOT NULL DEFAULT 0,
    last_searched_at  DOUBLE PRECISION NOT NULL DEFAULT 0,
    recency_score     DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sq_recency  ON search_queries (recency_score DESC);
CREATE INDEX IF NOT EXISTS idx_sq_freq     ON search_queries (frequency DESC);
CREATE INDEX IF NOT EXISTS idx_sq_query_prefix ON search_queries (query text_pattern_ops);
"""

conn = psycopg2.connect(
    host=os.environ["DB_HOST"],
    port=os.environ["DB_PORT"],
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
)
conn.autocommit = True
cur = conn.cursor()
cur.execute(DDL)
conn.close()
print("Tables created / verified.")
