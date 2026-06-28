from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 7861
    log_level: str = "INFO"

    login_list: list[str] = ["ww", "dna", "nte"]

    shared_secret: str = ""
    session_ttl_s: int = 600
    sig_ttl_s: int = 300


settings = Settings()
