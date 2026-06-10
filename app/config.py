"""Runtime configuration loaded from env vars + a TOML config file.

Env vars cover secrets and per-deployment values (NV_TOKEN, upstream API
URLs/tokens). The TOML file holds the access allowlist (visibility ranks/teams).
"""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseModel):
    """Loaded from a TOML file. Unlike router's seeds config, the defaults here
    are populated so a deployment without a config file still gates sensibly
    instead of locking everyone out."""

    visibility_ranks: list[str] = Field(default_factory=lambda: ["CEO", "High Command"])
    visibility_teams: list[str] = Field(default_factory=lambda: ["Doctrine"])


class Settings(BaseSettings):
    """Env-driven secrets and locations."""

    nv_token: str = "dev-token-change-me"
    # Path prefix where the app is mounted (e.g. "/skillquery" when fronted by a
    # path-routing proxy). Empty string = serve at root, suitable for local dev.
    url_prefix: str = ""

    # "real" fetches the upstream APIs below; "demo" loads committed fixtures.
    data_source: Literal["real", "demo"] = "real"
    demo_data_dir: Path = Path("./data_demo")

    # Processed SDE skill catalogue (scripts/refresh_sde.py output). Baked into
    # the container image; gitignored locally.
    sde_dir: Path = Path("./var/sde")

    skills_api_url: str = ""
    skills_api_token: str = ""
    users_api_url: str = ""
    users_api_token: str = ""

    # Stale-while-revalidate TTL for the in-memory snapshot of both upstreams.
    # Skills change slowly; 30 minutes keeps queries snappy without going stale.
    snapshot_ttl_s: float = 1800.0
    upstream_timeout_s: float = 30.0
    query_cache_size: int = 500

    config_path: Path = Path("./config.toml")
    config_local_path: Path = Path("./config.local.toml")

    # Dev-mode header overrides — only consulted when DEV_MODE=true. The
    # fallback identity (Member/Admin) does NOT pass the skill-query gate;
    # set DEV_USER_RANK=CEO or DEV_USER_TEAMS=Doctrine to test gated paths.
    dev_user_rank: str = ""
    dev_user_teams: str = ""

    dev_mode: bool = False
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("url_prefix", mode="after")
    @classmethod
    def _normalise_url_prefix(cls, v: str) -> str:
        # Accept "skillquery", "/skillquery", "/skillquery/" — normalise to
        # "/skillquery" (or "").
        v = v.strip()
        if not v:
            return ""
        if not v.startswith("/"):
            v = "/" + v
        return v.rstrip("/")


def load_app_config(path: Path) -> AppConfig:
    """Load app config from TOML, falling back to baked-in defaults if missing."""
    if not path.exists():
        return AppConfig()
    with path.open("rb") as f:
        data = tomllib.load(f)
    return AppConfig.model_validate(data)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    settings = get_settings()
    # Prefer the local override (gitignored) over the committed example.
    if settings.config_local_path.exists():
        return load_app_config(settings.config_local_path)
    return load_app_config(settings.config_path)
