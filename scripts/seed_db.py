#!/usr/bin/env python3
"""
Read CSV rows from stdin and bulk-insert them into PostgreSQL using
COPY FROM (fastest method — avoids per-row round trips).
Duplicate queries are ignored (ON CONFLICT DO NOTHING).
"""

import os
import sys
import csv
import io
import psycopg2

conn = psycopg2.connect(
    host=os.environ["DB_HOST"],
    port=os.environ["DB_PORT"],
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
)
cur = conn.cursor()

# Read all CSV from stdin
reader = csv.DictReader(sys.stdin)
rows = list(reader)

# Use a temp table + COPY + INSERT ... SELECT for conflict-safe bulk load
cur.execute("""
    CREATE TEMP TABLE tmp_search_queries (
        query             VARCHAR(255),
        frequency         BIGINT,
        last_searched_at  DOUBLE PRECISION,
        recency_score     DOUBLE PRECISION
    ) ON COMMIT DROP
""")

buffer = io.StringIO()
csv_writer = csv.writer(buffer)
for row in rows:
    csv_writer.writerow([
        row["query"],
        row["frequency"],
        row["last_searched_at"],
        row["recency_score"],
    ])

buffer.seek(0)
cur.copy_expert(
    "COPY tmp_search_queries (query, frequency, last_searched_at, recency_score) FROM STDIN WITH CSV",
    buffer,
)

cur.execute("""
    INSERT INTO search_queries (query, frequency, last_searched_at, recency_score)
    SELECT query, frequency, last_searched_at, recency_score FROM tmp_search_queries
    ON CONFLICT (query) DO NOTHING
""")

conn.commit()
print(f"Seeded {cur.rowcount} rows into search_queries.", file=sys.stderr)
conn.close()
