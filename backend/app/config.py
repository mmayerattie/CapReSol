import os
import json
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

    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Comma-separated origins, e.g. "http://localhost:3000,https://capresol.vercel.app"
    ALLOWED_ORIGINS: list = json.loads(
        os.getenv("ALLOWED_ORIGINS", '["http://localhost:3000"]')
    )

    # JSON array of {username, password} objects for seeding users
    USERS_CONFIG: list = json.loads(os.getenv("USERS_CONFIG", "[]"))

settings = Settings()
