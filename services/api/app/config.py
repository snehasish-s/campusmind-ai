from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/campusmind.db"
    redis_url: str = "redis://localhost:6379/0"
    app_origin: str = "http://localhost:3000"
    secure_cookies: bool = False
    session_hours: int = 12
    invitation_hours: int = 48
    storage_root: str = "./data/storage"
    queue_mode: Literal["rq", "sync"] = "rq"
    rate_limit_backend: Literal["redis", "memory", "database"] = "redis"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False
    mail_from: str = "CampusMind <no-reply@campusmind.test>"
    testing: bool = False
    ai_mode: Literal["fallback", "ollama"] = "fallback"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    ai_timeout_seconds: int = 45
    graph_checkpoint_url: str = ""
    embedding_mode: Literal["keyword", "sentence_transformers"] = "keyword"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    qdrant_url: str = "http://localhost:6333"
    storage_backend: Literal["local", "supabase"] = "local"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "campusmind-private"
    retention_days: int = 90
    deployment_mode: str = "local"
    bootstrap_token: str = ""
    automation_enabled: bool = True
    automation_interval_seconds: int = 60
    payment_provider: Literal["demo", "razorpay"] = "demo"
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    payment_institution_id: str = ""

    @model_validator(mode="after")
    def hosted_safety(self):
        if self.deployment_mode == "render":
            if not self.database_url.startswith("postgresql+psycopg://") or self.storage_backend != "supabase":
                raise ValueError("Render requires persistent PostgreSQL and private Supabase storage.")
            if (
                not self.app_origin.startswith("https://")
                or not self.secure_cookies
                or not self.graph_checkpoint_url.startswith("postgres")
            ):
                raise ValueError("Render requires HTTPS, secure cookies and persistent PostgreSQL graph checkpoints.")
        return self


@lru_cache
def settings():
    return Settings()
