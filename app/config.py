from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class ConfigError(RuntimeError):
    """Configuration-related error."""


class ModelConfig(BaseModel):
    alias: str
    upstream_model: str | None = None
    upstream_model_env: str | None = None

    def resolve_upstream_model(self, provider_id: str) -> str:
        if self.upstream_model_env:
            value = os.getenv(self.upstream_model_env, "").strip()
            if value:
                return value
            if self.upstream_model and self.upstream_model.strip():
                return self.upstream_model.strip()
            raise ConfigError(
                f"Model '{self.alias}' in provider '{provider_id}' requires env "
                f"'{self.upstream_model_env}' for upstream model."
            )
        if self.upstream_model and self.upstream_model.strip():
            return self.upstream_model.strip()
        raise ConfigError(
            f"Model '{self.alias}' in provider '{provider_id}' must set "
            "'upstream_model' or 'upstream_model_env'."
        )


class ProviderConfig(BaseModel):
    id: str
    provider_type: str = "generic"
    base_url: str | None = None
    base_url_env: str | None = None
    auth: dict[str, Any] = Field(default_factory=dict)
    models: list[ModelConfig]
    extra_headers: dict[str, str] = Field(default_factory=dict)
    path_overrides: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = 300.0

    def resolved_base_url(self) -> str:
        if self.base_url:
            return self.base_url.rstrip("/")
        if self.base_url_env:
            value = os.getenv(self.base_url_env, "").strip()
            if value:
                return value.rstrip("/")
            raise ConfigError(
                f"Provider '{self.id}' requires env '{self.base_url_env}' for base_url."
            )
        raise ConfigError(f"Provider '{self.id}' must set base_url or base_url_env.")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dicts. override takes precedence; nested dicts are merged recursively."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class GatewayConfig(BaseModel):
    providers: list[ProviderConfig]
    client_api_keys: list[str] = Field(default_factory=list)
    provider_defaults: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "GatewayConfig":
        if not path.exists():
            raise ConfigError(
                f"Model registry file not found: {path}. "
                "Set MODEL_REGISTRY_FILE or create config/model_registry.json."
            )
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ConfigError(f"Expected JSON object in {path}")
        raw = cls._apply_provider_defaults(raw)
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            raise ConfigError(f"Invalid registry schema in {path}: {exc}") from exc

    @staticmethod
    def _apply_provider_defaults(raw: dict[str, Any]) -> dict[str, Any]:
        defaults = raw.get("provider_defaults", {})
        if not defaults or not isinstance(defaults, dict):
            return raw
        providers = raw.get("providers", [])
        merged_providers = []
        for provider in providers:
            if not isinstance(provider, dict):
                merged_providers.append(provider)
                continue
            ptype = provider.get("provider_type", "generic")
            if ptype in defaults:
                provider = _deep_merge(defaults[ptype], provider)
            merged_providers.append(provider)
        raw["providers"] = merged_providers
        return raw


def _resolve_registry_path() -> Path:
    default_path = Path("config/model_registry.json")
    configured = os.getenv("MODEL_REGISTRY_FILE")
    path = Path(configured) if configured else default_path
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _parse_client_keys(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def load_gateway_config() -> GatewayConfig:
    config = GatewayConfig.from_file(_resolve_registry_path())
    env_keys = _parse_client_keys(os.getenv("GATEWAY_API_KEYS", ""))
    if env_keys:
        merged = list(dict.fromkeys([*config.client_api_keys, *env_keys]))
        config.client_api_keys = merged
    return config
