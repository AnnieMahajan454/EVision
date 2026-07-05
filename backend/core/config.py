from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="EVision API", validation_alias="APP_NAME")
    app_version: str = Field(default="0.1.0", validation_alias="APP_VERSION")
    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/evision",
        validation_alias="DATABASE_URL",
    )
    # When True, application will run Base.metadata.create_all(engine) on startup
    create_tables_on_start: bool = Field(default=False, validation_alias="CREATE_TABLES_ON_START")

    # Path where ML model artifacts are stored (absolute or repo-relative)
    models_dir: str = Field(default="ml/models", validation_alias="MODELS_DIR")
    jwt_secret_key: str = Field(
        default="replace-with-a-long-random-secret",
        validation_alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"], validation_alias="CORS_ORIGINS")


settings = Settings()
