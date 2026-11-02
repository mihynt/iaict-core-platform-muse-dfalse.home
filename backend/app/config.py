"""Runtime configuration from environment only. No secrets in code or repo."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.environ.get("APP_NAME", "iaict-core-platform")
    app_env: str = os.environ.get("APP_ENV", "local")
    api_prefix: str = "/api/v1"


settings = Settings()
