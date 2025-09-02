import os

from databases import Database
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the database URL from the environment variable
DATABASE_URL = os.getenv("DATABASE_URL")

# Create the database instance
database = Database(DATABASE_URL)
