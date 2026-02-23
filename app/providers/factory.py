from __future__ import annotations

import os
from typing import Any

from app.auth import build_auth_strategy
from app.config import ConfigError, ProviderConfig
from app.providers.base import Provider


class ProviderFactory:
    @staticmethod
    def create_provider(config: ProviderConfig) -> Provider:
        provider_type = config.provider_type.strip().lower()
        if provider_type == "panzhi":
            return ProviderFactory._create_panzhi_provider(config)
        if provider_type in {"neibu", "internal"}:
            return ProviderFactory._create_neibu_provider(config)
        return ProviderFactory._create_generic_provider(config)

    @staticmethod
    def _create_generic_provider(config: ProviderConfig) -> Provider:
        return Provider(
            provider_id=config.id,
            base_url=config.resolved_base_url(),
            auth_strategy=build_auth_strategy(config.id, config.auth),
            timeout_seconds=config.timeout_seconds,
            extra_headers=config.extra_headers,
            path_overrides=config.path_overrides,
        )

    @staticmethod
    def _create_panzhi_provider(config: ProviderConfig) -> Provider:
        auth = ProviderFactory._merge_defaults(
            defaults={
                "type": "qwen_signature",
                "appid_env": "PANZHI_APPID",
                "appkey_env": "PANZHI_APPKEY",
                "capability_from": "upstream_model",
                "token_header": "Authorization",
                "token_prefix": "Bearer ",
            },
            override=config.auth,
        )
        base_url = ProviderFactory._resolve_base_url(
            config,
            fallback_env="PANZHI_BASE_URL",
        )
        return Provider(
            provider_id=config.id,
            base_url=base_url,
            auth_strategy=build_auth_strategy(config.id, auth),
            timeout_seconds=config.timeout_seconds,
            extra_headers=config.extra_headers,
            path_overrides=config.path_overrides,
        )

    @staticmethod
    def _create_neibu_provider(config: ProviderConfig) -> Provider:
        auth = ProviderFactory._merge_defaults(
            defaults={
                "type": "internal_api_key",
                "resolver": "custom_resolvers:get_api_key",
                "request_url_env": "OPENAI_API_BASE",
                "api_id_env": "OPENAI_API_ID",
                "api_secret_env": "OPENAI_API_SECRET",
                "model_source_env": "MODELSOURCE",
                "trace_id_env": "TRACE_ID",
                "model_id_env": "MODEL_ID",
                "model_id_from": "env",
                "token_header": "Authorization",
                "token_prefix": "Bearer ",
            },
            override=config.auth,
        )
        base_url = ProviderFactory._resolve_base_url(
            config,
            fallback_env="OPENAI_API_BASE",
        )

        return Provider(
            provider_id=config.id,
            base_url=base_url,
            auth_strategy=build_auth_strategy(config.id, auth),
            timeout_seconds=config.timeout_seconds,
            extra_headers=config.extra_headers,
            path_overrides=config.path_overrides,
        )

    @staticmethod
    def _resolve_base_url(config: ProviderConfig, fallback_env: str | None = None) -> str:
        if config.base_url:
            return config.base_url.rstrip("/")
        if config.base_url_env:
            value = os.getenv(config.base_url_env, "").strip()
            if value:
                return value.rstrip("/")
            raise ConfigError(
                f"Provider '{config.id}' requires env '{config.base_url_env}' for base_url."
            )
        if fallback_env:
            fallback = os.getenv(fallback_env, "").strip()
            if fallback:
                return fallback.rstrip("/")
        source = f" or env '{fallback_env}'" if fallback_env else ""
        raise ConfigError(
            f"Provider '{config.id}' must set base_url/base_url_env{source}."
        )

    @staticmethod
    def _merge_defaults(
        *,
        defaults: dict[str, Any],
        override: dict[str, Any],
    ) -> dict[str, Any]:
        return {**defaults, **(override or {})}
