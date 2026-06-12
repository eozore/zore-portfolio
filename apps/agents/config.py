"""
Environment configuration for the Agents service.

Uses Pydantic Settings to load values from environment variables with
sensible defaults for local development.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # GCP
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"

    # Firebase
    firebase_service_account_path: str = ""

    # Firestore
    firestore_database: str = "(default)"

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    # Logging
    log_level: str = "INFO"


settings = Settings()
