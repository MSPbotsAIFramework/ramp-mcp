"""Non-secret runtime settings.

Credentials are never part of this module -- they arrive per request on
HTTP headers (see server.py) and must never be read from the environment.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    mcp_http_host: str = "0.0.0.0"
    mcp_http_port: int = 8080
    ramp_base_url: str = "https://api.ramp.com"


def get_settings() -> Settings:
    return Settings()
