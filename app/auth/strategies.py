from __future__ import annotations

import base64
import hashlib
import importlib
import inspect
import json
import os
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable


def _encode_base64(raw_data: dict[str, Any]) -> str:
    encoded = base64.b64encode(
        json.dumps(raw_data, sort_keys=True).encode("utf-8")
    )
    return str(encoded, encoding="utf-8")


def _cal_md5(raw_text: str) -> str:
    return hashlib.md5(raw_text.encode("utf-8")).hexdigest()


def _get_capability_name_24(capability_name: str) -> str:
    if len(capability_name) >= 24:
        return capability_name[:24]
    return capability_name.ljust(24, "0")


@dataclass(frozen=True)
class AuthContext:
    provider_id: str
    upstream_model: str


class AuthStrategy(ABC):
    @abstractmethod
    async def headers(self, context: AuthContext) -> dict[str, str]:
        pass


class NoAuth(AuthStrategy):
    async def headers(self, context: AuthContext) -> dict[str, str]:
        return {}


class StaticApiKeyAuth(AuthStrategy):
    def __init__(
        self,
        api_key: str,
        header: str = "Authorization",
        prefix: str = "Bearer ",
    ) -> None:
        self.api_key = api_key
        self.header = header
        self.prefix = prefix

    async def headers(self, context: AuthContext) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError(f"Provider '{context.provider_id}' resolved empty API key.")
        return {self.header: f"{self.prefix}{self.api_key}"}


class QwenSignatureAuth(AuthStrategy):
    def __init__(
        self,
        appid: str,
        appkey: str,
        capability_from: str = "upstream_model",
        fixed_capability_name: str | None = None,
        token_header: str | None = None,
        token_prefix: str = "Bearer ",
    ) -> None:
        self.appid = appid
        self.appkey = appkey
        self.capability_from = capability_from
        self.fixed_capability_name = fixed_capability_name
        self.token_header = token_header
        self.token_prefix = token_prefix

    async def headers(self, context: AuthContext) -> dict[str, str]:
        if not self.appid:
            raise RuntimeError(f"Provider '{context.provider_id}' resolved empty appid.")
        if not self.appkey:
            raise RuntimeError(f"Provider '{context.provider_id}' resolved empty appkey.")

        capability = self.fixed_capability_name or context.upstream_model
        if self.capability_from == "fixed" and not self.fixed_capability_name:
            raise RuntimeError(
                f"Provider '{context.provider_id}' sets capability_from=fixed "
                "but fixed_capability_name is empty."
            )
        capability_name = _get_capability_name_24(capability)
        request_id = uuid.uuid4().hex

        x_server_param = {
            "appid": self.appid,
            "csid": f"{self.appid}{capability_name}{request_id}",
        }
        encoded_param = _encode_base64(x_server_param)
        current_time = str(int(time.time()))
        checksum = _cal_md5(f"{self.appkey}{current_time}{encoded_param}")

        headers = {
            "X-Server-Param": encoded_param,
            "X-CurTime": current_time,
            "X-CheckSum": checksum,
        }
        if self.token_header:
            headers[self.token_header] = f"{self.token_prefix}{self.appkey}"
        return headers


class InternalApiKeyResolverAuth(AuthStrategy):
    def __init__(
        self,
        resolver: str,
        request_url_env: str = "OPENAI_API_BASE",
        api_id_env: str = "OPENAI_API_ID",
        api_secret_env: str = "OPENAI_API_SECRET",
        model_source_env: str = "MODELSOURCE",
        trace_id_env: str = "TRACE_ID",
        model_id_env: str = "MODEL_ID",
        model_id_from: str = "upstream_model",
        token_header: str = "Authorization",
        token_prefix: str = "Bearer ",
    ) -> None:
        self.request_url_env = request_url_env
        self.api_id_env = api_id_env
        self.api_secret_env = api_secret_env
        self.model_source_env = model_source_env
        self.trace_id_env = trace_id_env
        self.model_id_env = model_id_env
        self.model_id_from = model_id_from
        self.token_header = token_header
        self.token_prefix = token_prefix
        self._resolver = self._load_callable(resolver)

    @staticmethod
    def _load_callable(path: str) -> Callable[..., Any]:
        if ":" not in path:
            raise RuntimeError(
                f"Invalid resolver '{path}'. Expected '<module>:<callable>'."
            )
        module_name, fn_name = path.split(":", 1)
        module = importlib.import_module(module_name)
        fn = getattr(module, fn_name, None)
        if fn is None or not callable(fn):
            raise RuntimeError(f"Resolver '{path}' is not callable.")
        return fn

    async def headers(self, context: AuthContext) -> dict[str, str]:
        request_url = os.getenv(self.request_url_env, "")
        api_id = os.getenv(self.api_id_env, "")
        api_secret = os.getenv(self.api_secret_env, "")
        model_source = os.getenv(self.model_source_env, "")
        trace_id = os.getenv(self.trace_id_env, "") or uuid.uuid4().hex
        model_id = (
            context.upstream_model
            if self.model_id_from == "upstream_model"
            else os.getenv(self.model_id_env, "")
        )

        token = self._resolver(
            request_url=request_url,
            api_key=api_id,
            api_secret=api_secret,
            model_id=model_id,
            model_source=model_source,
            trace_id=trace_id,
        )
        if inspect.isawaitable(token):
            token = await token
        if not token:
            raise RuntimeError(
                f"Provider '{context.provider_id}' resolver returned empty API key."
            )
        return {self.token_header: f"{self.token_prefix}{token}"}


def _value_from_raw_or_env(
    raw_value: str | None,
    env_name: str | None,
    *,
    required: bool,
    field_name: str,
    provider_id: str,
) -> str:
    if raw_value is not None and str(raw_value).strip():
        return str(raw_value).strip()
    if env_name:
        value = os.getenv(env_name, "").strip()
        if value:
            return value
    if required:
        source = f" or env '{env_name}'" if env_name else ""
        raise RuntimeError(
            f"Provider '{provider_id}' requires '{field_name}' (literal{source})."
        )
    return ""


def build_auth_strategy(provider_id: str, auth_config: dict[str, Any]) -> AuthStrategy:
    auth_type = str(auth_config.get("type", "none")).strip().lower()

    if auth_type == "none":
        return NoAuth()

    if auth_type == "static_api_key":
        api_key = _value_from_raw_or_env(
            raw_value=auth_config.get("api_key"),
            env_name=auth_config.get("api_key_env"),
            required=True,
            field_name="api_key",
            provider_id=provider_id,
        )
        header = str(auth_config.get("header", "Authorization"))
        prefix = str(auth_config.get("prefix", "Bearer "))
        return StaticApiKeyAuth(api_key=api_key, header=header, prefix=prefix)

    if auth_type == "qwen_signature":
        appid = _value_from_raw_or_env(
            raw_value=auth_config.get("appid"),
            env_name=auth_config.get("appid_env"),
            required=True,
            field_name="appid",
            provider_id=provider_id,
        )
        appkey = _value_from_raw_or_env(
            raw_value=auth_config.get("appkey"),
            env_name=auth_config.get("appkey_env"),
            required=True,
            field_name="appkey",
            provider_id=provider_id,
        )
        capability_from = str(auth_config.get("capability_from", "upstream_model"))
        fixed_capability_name = auth_config.get("fixed_capability_name")
        if fixed_capability_name is not None:
            fixed_capability_name = str(fixed_capability_name)
        token_header = auth_config.get("token_header")
        if token_header is not None:
            token_header = str(token_header)
        token_prefix = str(auth_config.get("token_prefix", "Bearer "))
        return QwenSignatureAuth(
            appid=appid,
            appkey=appkey,
            capability_from=capability_from,
            fixed_capability_name=fixed_capability_name,
            token_header=token_header,
            token_prefix=token_prefix,
        )

    if auth_type == "internal_api_key":
        resolver = str(auth_config.get("resolver", "custom_resolvers:get_api_key"))
        return InternalApiKeyResolverAuth(
            resolver=resolver,
            request_url_env=str(auth_config.get("request_url_env", "OPENAI_API_BASE")),
            api_id_env=str(auth_config.get("api_id_env", "OPENAI_API_ID")),
            api_secret_env=str(auth_config.get("api_secret_env", "OPENAI_API_SECRET")),
            model_source_env=str(auth_config.get("model_source_env", "MODELSOURCE")),
            trace_id_env=str(auth_config.get("trace_id_env", "TRACE_ID")),
            model_id_env=str(auth_config.get("model_id_env", "MODEL_ID")),
            model_id_from=str(auth_config.get("model_id_from", "upstream_model")),
            token_header=str(auth_config.get("token_header", "Authorization")),
            token_prefix=str(auth_config.get("token_prefix", "Bearer ")),
        )

    raise RuntimeError(f"Provider '{provider_id}' uses unsupported auth type '{auth_type}'.")
