from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import GatewayConfig
from app.providers import ModelRouter, ProviderFactory

logger = logging.getLogger(__name__)


class Gateway:
    def __init__(self, config: GatewayConfig) -> None:
        self.config = config
        self.router = self._build_router(config)
        self.client_api_keys = set(config.client_api_keys)
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=30.0))

    async def close(self) -> None:
        await self.client.aclose()

    @staticmethod
    def _extract_bearer_token(auth_header: str) -> str:
        if not auth_header:
            return ""
        lower = auth_header.lower()
        if lower.startswith("bearer "):
            return auth_header[7:].strip()
        return auth_header.strip()

    def authorize_client(self, request: Request) -> None:
        if not self.client_api_keys:
            return
        token = self._extract_bearer_token(request.headers.get("authorization", ""))
        if token not in self.client_api_keys:
            raise HTTPException(status_code=401, detail="Invalid gateway API key.")

    def list_models(self) -> dict[str, object]:
        return self.router.list_openai_models()

    async def proxy(self, path: str, payload: dict[str, Any]) -> JSONResponse | StreamingResponse:
        model_alias = str(payload.get("model", "")).strip()
        if not model_alias:
            raise HTTPException(status_code=400, detail="Request body must include 'model'.")

        try:
            route = self.router.resolve(model_alias)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        forwarded_payload = dict(payload)
        forwarded_payload["model"] = route.upstream_model
        if path == "/chat/completions" and "stream" not in forwarded_payload:
            forwarded_payload["stream"] = False
        upstream_url, headers, timeout_seconds = await route.provider.request_spec(
            path=path,
            upstream_model=route.upstream_model,
        )

        if bool(forwarded_payload.get("stream", False)):
            return await self._proxy_stream(
                url=upstream_url,
                headers=headers,
                payload=forwarded_payload,
                _timeout_seconds=timeout_seconds,
            )
        return await self._proxy_json(
            path=path,
            url=upstream_url,
            headers=headers,
            payload=forwarded_payload,
            timeout_seconds=timeout_seconds,
            requested_model=model_alias,
        )

    async def _proxy_json(
        self,
        *,
        path: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
        requested_model: str,
    ) -> JSONResponse:
        try:
            response = await self.client.post(
                url,
                json=payload,
                headers=headers,
                timeout=timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Upstream request failed: {exc}") from exc

        raw_text = response.text
        try:
            content = response.json()
        except json.JSONDecodeError:
            content = None

        if content is None and path == "/chat/completions":
            parsed_sse = self._merge_sse_chunks_to_chat_completion(
                raw_text=raw_text,
                requested_model=requested_model,
            )
            if parsed_sse is not None:
                return JSONResponse(status_code=response.status_code, content=parsed_sse)

        if content is None:
            content = {
                "error": {
                    "message": "Upstream returned non-JSON response.",
                    "upstream_status": response.status_code,
                    "upstream_content_type": response.headers.get("content-type", ""),
                    "upstream_location": response.headers.get("location", ""),
                    "raw": raw_text,
                }
            }

        if isinstance(content, dict) and "model" in content:
            content["model"] = requested_model

        return JSONResponse(status_code=response.status_code, content=content)

    async def _proxy_stream(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        _timeout_seconds: float,
    ) -> JSONResponse | StreamingResponse:
        try:
            upstream_request = self.client.build_request(
                "POST",
                url,
                json=payload,
                headers=headers,
            )
            response = await self.client.send(
                upstream_request,
                stream=True,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Upstream request failed: {exc}") from exc

        if response.status_code >= 400:
            try:
                body = await response.aread()
            except httpx.HTTPError as exc:
                body = (
                    json.dumps(
                        {"error": {"message": f"Failed to read upstream error body: {exc}"}}
                    ).encode("utf-8")
                )
            finally:
                await response.aclose()
            parsed = self._parse_error_body(body)
            return JSONResponse(status_code=response.status_code, content=parsed)

        media_type = response.headers.get("content-type", "text/event-stream")

        async def iter_chunks() -> Any:
            try:
                async for chunk in response.aiter_raw():
                    if chunk:
                        yield chunk
            except asyncio.CancelledError:
                raise
            except httpx.HTTPError as exc:
                logger.warning("Upstream stream interrupted: %s", exc)
                if "text/event-stream" in media_type:
                    yield self._to_sse_bytes({"error": {"message": f"upstream stream interrupted: {exc}"}})
                    yield b"data: [DONE]\n\n"
            finally:
                await response.aclose()

        passthrough_headers: dict[str, str] = {}
        if "x-request-id" in response.headers:
            passthrough_headers["x-request-id"] = response.headers["x-request-id"]
        return StreamingResponse(
            iter_chunks(),
            status_code=response.status_code,
            media_type=media_type,
            headers=passthrough_headers,
        )

    @staticmethod
    def _parse_error_body(raw: bytes) -> dict[str, Any]:
        try:
            parsed = json.loads(raw.decode("utf-8"))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        return {"error": {"message": raw.decode("utf-8", errors="replace")}}

    @staticmethod
    def _to_sse_bytes(payload: dict[str, Any]) -> bytes:
        return f"data:{json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

    @staticmethod
    def _merge_sse_chunks_to_chat_completion(
        *,
        raw_text: str,
        requested_model: str,
    ) -> dict[str, Any] | None:
        chunks: list[dict[str, Any]] = []
        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped or not stripped.lower().startswith("data:"):
                continue
            payload = stripped[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                chunks.append(obj)

        if not chunks:
            return None

        first = chunks[0]
        chat_id = str(first.get("id", f"chatcmpl-proxy-{int(time.time())}"))
        created = int(first.get("created", int(time.time())))
        usage: dict[str, Any] | None = None

        states: dict[int, dict[str, Any]] = {}
        for chunk in chunks:
            maybe_usage = chunk.get("usage")
            if isinstance(maybe_usage, dict):
                usage = maybe_usage
            for choice in chunk.get("choices", []):
                if not isinstance(choice, dict):
                    continue
                index = int(choice.get("index", 0))
                state = states.setdefault(
                    index,
                    {
                        "index": index,
                        "role": "assistant",
                        "content": "",
                        "finish_reason": None,
                    },
                )
                delta = choice.get("delta")
                if isinstance(delta, dict):
                    role = delta.get("role")
                    if isinstance(role, str) and role:
                        state["role"] = role
                    content = delta.get("content")
                    if isinstance(content, str):
                        state["content"] = f"{state['content']}{content}"
                finish_reason = choice.get("finish_reason")
                if finish_reason is not None:
                    state["finish_reason"] = finish_reason

        if not states:
            return None

        merged_choices: list[dict[str, Any]] = []
        for index in sorted(states):
            state = states[index]
            merged_choices.append(
                {
                    "index": state["index"],
                    "message": {
                        "role": state["role"],
                        "content": state["content"],
                    },
                    "finish_reason": state["finish_reason"] or "stop",
                }
            )

        result: dict[str, Any] = {
            "id": chat_id,
            "object": "chat.completion",
            "created": created,
            "model": requested_model,
            "choices": merged_choices,
        }
        if usage is not None:
            result["usage"] = usage
        return result

    @staticmethod
    def _build_router(config: GatewayConfig) -> ModelRouter:
        router = ModelRouter()
        for provider_config in config.providers:
            provider = ProviderFactory.create_provider(provider_config)
            for model in provider_config.models:
                upstream_model = model.resolved_upstream(provider_config.id)
                router.register(
                    alias=model.alias,
                    upstream_model=upstream_model,
                    provider=provider,
                )
        return router
