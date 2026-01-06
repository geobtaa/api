from databases import Database
from db.config import DATABASE_URL

# Create the database instance
# Note: When running tests in parallel, limit the number of workers to avoid
# hitting PostgreSQL's max_connections limit. Each worker process creates
# its own connection pool. Default worker count is set to 4 in Makefile.
database = Database(DATABASE_URL)
