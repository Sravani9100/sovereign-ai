from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SOVEREIGN_",
        env_file=(".env", "../.env", ".env.local", "../.env.local"),
        extra="ignore",
    )

    # DATABASE_URL is what Neon (and most hosts) provision.
    database_url: str = Field(
        default="postgresql+psycopg://localhost/sovereign",
        validation_alias=AliasChoices("SOVEREIGN_DATABASE_URL", "DATABASE_URL"),
    )
    # Direct (non-pooled) connection for migrations. Falls back to database_url.
    migration_database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SOVEREIGN_MIGRATION_DATABASE_URL", "DATABASE_URL_UNPOOLED"),
    )
    cors_origins: list[str] = ["http://localhost:3000"]

    # Sessions are signed JWTs in an httpOnly cookie. Permissions are not in the token:
    # they are loaded from the database on every request, so revocation is immediate.
    jwt_secret: SecretStr = SecretStr("dev-only-secret-change-me-in-every-deployment")
    session_hours: int = 8
    cookie_secure: bool = False

    # Email sign-in codes. "console" prints them to the API log (development only).
    email_backend: Literal["console", "smtp"] = "console"
    email_from: str = "SovereignAI <no-reply@localhost>"
    smtp_host: str | None = None
    smtp_port: int = 587  # 587 = STARTTLS, 465 = implicit TLS
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    login_code_minutes: int = 10
    # Public demo: accounts on these domains can chat but not change anything.
    demo_read_only: bool = False
    demo_email_domains: list[str] = [
        "musterwerk.example",
        "rheintech.example",
        "consulting.example",
    ]
    # Spending guards. Per member per rolling hour, and across all tenants per UTC day
    # (0 = unlimited). Every question is one model call.
    chat_messages_per_hour: int = 30
    daily_message_limit: int = 0

    # The demo seed adds this person as a Musterwerk admin who signs in by email code.
    seed_admin_email: str | None = None
    seed_admin_name: str = "Admin"

    storage_dir: Path = Path("storage")
    max_upload_mb: int = 20
    # Run ingestion inside the API process after upload instead of a separate worker.
    inline_ingestion: bool = True

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dims: int = 384

    retrieval_k: int = 8
    retrieval_candidates: int = 30
    # Vector hits below this cosine similarity are dropped; keyword hits are always kept.
    min_similarity: float = 0.55

    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    anthropic_model: str = "claude-haiku-5-5"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    llm_timeout_s: float = 120.0


def is_demo_account(email: str, settings: Settings) -> bool:
    """A shared demo account that is read-only while demo_read_only is on."""
    domain = email.rsplit("@", 1)[-1].lower()
    return settings.demo_read_only and domain in settings.demo_email_domains


@lru_cache
def get_settings() -> Settings:
    return Settings()
