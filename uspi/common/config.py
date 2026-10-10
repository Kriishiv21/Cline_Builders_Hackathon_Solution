"""Centralized configuration loading.

All thresholds, weights, tiers and Cline model routing live in
`configs/*.yaml` or environment variables — never hardcoded in code, per
architecture doc section 14 ("Weights, thresholds and window parameters
are never hardcoded; every report and ledger record stores the
configuration ids that produced it.").
"""
from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"

load_dotenv(REPO_ROOT / ".env", override=False)


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float) -> float:
    val = os.environ.get(name)
    return float(val) if val not in (None, "") else default


def env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    return int(val) if val not in (None, "") else default


@functools.lru_cache(maxsize=None)
def load_yaml(relative_path: str) -> Dict[str, Any]:
    """Load and cache a YAML config file under configs/, keyed by relative path."""
    path = CONFIG_DIR / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    data["_config_version"] = data.get("version", "unversioned")
    data["_config_path"] = str(path.relative_to(REPO_ROOT))
    return data


def clear_config_cache() -> None:
    load_yaml.cache_clear()


class ClineSettings:
    """Reads Cline API connection + per-component model routing from env."""

    def __init__(self) -> None:
        self.api_key = env("CLINE_API_KEY", "")
        self.api_base = env("CLINE_API_BASE", "https://api.cline.bot/api/v1")
        self.default_model = env("CLINE_MODEL_ID", "cline/strong-default")
        self.timeout_seconds = env_float("CLINE_HTTP_TIMEOUT_SECONDS", 8.0)
        self.max_retries = env_int("CLINE_HTTP_MAX_RETRIES", 2)

    def model_for(self, component: str) -> str:
        """component in {TEXT_SLM, VOICE_AASIST, VOICE_PHONETIC, LIVE_ANALYSER,
        CONTENT_RISK, REPORT_WORDING}. Falls back to CLINE_MODEL_ID."""
        key = f"CLINE_MODEL_ID_{component.upper()}"
        return env(key, self.default_model) or self.default_model


@functools.lru_cache(maxsize=None)
def cline_settings() -> ClineSettings:
    return ClineSettings()
