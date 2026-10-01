from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "EVision API"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/evision"

    jwt_secret_key: str = "dev-only-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12

    # Trained model artifacts (see ml/). Relative paths are resolved from the repo root.
    models_dir: Path = Path("ml/artifacts")

    @property
    def models_path(self) -> Path:
        return self.models_dir if self.models_dir.is_absolute() else REPO_ROOT / self.models_dir


settings = Settings()

# The fleet operates in India. Tariff hours and "local day" boundaries use IST; the same
# zone is hard-coded in the analytics SQL views.
LOCAL_TIMEZONE = "Asia/Kolkata"
