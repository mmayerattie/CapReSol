import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/capresol"
    )
    IDEALISTA_API_KEY: str = os.getenv("IDEALISTA_API_KEY", "")
    IDEALISTA_SECRET: str = os.getenv("IDEALISTA_SECRET", "")
    FIRECRAWL_API_KEY: str = os.getenv("FIRECRAWL_API_KEY", "")

settings = Settings()