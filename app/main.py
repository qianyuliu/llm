from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.responses import Response

from app.config import ConfigError, load_gateway_config
from app.gateway import Gateway


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    config = load_gateway_config()
    gateway = Gateway(config)
    app.state.gateway = gateway
    try:
        yield
    finally:
        await gateway.close()


app = FastAPI(
    title="OpenClaw Internal Model Gateway",
    version="0.1.0",
    lifespan=lifespan,
)


def _get_gateway(request: Request) -> Gateway:
    gateway: Gateway | None = getattr(request.app.state, "gateway", None)
    if gateway is None:
        raise HTTPException(status_code=500, detail="Gateway is not initialized.")
    return gateway


async def _proxy_request(
    request: Request,
    *,
    path: str,
) -> Response:
    gateway = _get_gateway(request)
    gateway.authorize_client(request)
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Body must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object.")
    return await gateway.proxy(path=path, payload=payload)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models(request: Request) -> dict[str, object]:
    gateway = _get_gateway(request)
    gateway.authorize_client(request)
    return gateway.list_models()


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(request: Request) -> Response:
    return await _proxy_request(request, path="/chat/completions")


@app.post("/v1/completions", response_model=None)
async def completions(request: Request) -> Response:
    return await _proxy_request(request, path="/completions")


@app.post("/v1/responses", response_model=None)
async def responses(request: Request) -> Response:
    return await _proxy_request(request, path="/responses")


def run() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "18080"))
    reload = os.getenv("RELOAD", "0") == "1"
    try:
        uvicorn.run("app.main:app", host=host, port=port, reload=reload)
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    run()
