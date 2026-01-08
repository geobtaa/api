import os
from databases import Database
from db.config import DATABASE_URL

# Create the database instance
# Note: When running tests in parallel, limit the number of workers to avoid
# hitting PostgreSQL's max_connections limit. Each worker process creates
# its own connection pool. Default worker count is set to 4 in Makefile.
#
# In Celery, many short-lived tasks can otherwise create many pools quickly.
# Keep defaults conservative and allow override via env.
DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "5"))
database = Database(DATABASE_URL, min_size=DB_POOL_MIN, max_size=DB_POOL_MAX)
