import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://phish:phish@localhost:5432/phishdb")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SELENIUM_URL = os.getenv("SELENIUM_URL", "http://localhost:4444/wd/hub")

def _parse_cors_origins(value: str) -> list[str]:
    value = value.strip()
    if value == "*":
        return ["*"]
    return [origin.strip() for origin in value.split(",") if origin.strip()]

CORS_ALLOW_ORIGINS = _parse_cors_origins(os.getenv("CORS_ALLOW_ORIGINS", "*"))
