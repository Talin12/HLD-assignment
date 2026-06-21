#!/bin/bash
set -e

echo "==> Waiting for PostgreSQL to be ready..."
until python -c "import psycopg2; psycopg2.connect(host='$DB_HOST', port='$DB_PORT', dbname='$DB_NAME', user='$DB_USER', password='$DB_PASSWORD')" 2>/dev/null; do
  sleep 1
done
echo "==> PostgreSQL is ready."

echo "==> Running DB migrations / table creation..."
python scripts/init_db.py

echo "==> Checking if dataset already seeded..."
COUNT=$(python -c "
import psycopg2, os
conn = psycopg2.connect(host=os.environ['DB_HOST'], port=os.environ['DB_PORT'],
  dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'])
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM search_queries')
print(cur.fetchone()[0])
conn.close()
")
if [ "$COUNT" -lt "1000" ]; then
  echo "==> Generating and seeding dataset (~100k rows)..."
  python scripts/generate_dataset.py | python scripts/seed_db.py
else
  echo "==> Dataset already present ($COUNT rows), skipping seed."
fi

echo "==> Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
