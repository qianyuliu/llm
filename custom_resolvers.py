from __future__ import annotations

import base64
import hashlib
import os
import hmac
from datetime import datetime, timezone
from urllib.parse import urlparse


def get_signature(host: str, date: str, request_line: str, api_secret: str) -> str:
    if not host:
        raise ValueError("host is empty")
    if not date:
        raise ValueError("date is empty")
    if not request_line:
        raise ValueError("request_line is empty")
    if not api_secret:
        raise ValueError("api_secret is empty")

    signing_str = f"host: {host}\ndate: {date}\n{request_line}"
    digest = hmac.new(
        api_secret.encode("utf-8"),
        signing_str.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def get_api_key(
    request_url: str,
    api_key: str,
    api_secret: str,
    model_id: str,
    model_source: str,
    trace_id: str,
) -> str:
    # Optional local bypass for debug only.
    override = os.getenv("INTERNAL_API_KEY_OVERRIDE", "").strip()
    if override:
        return override

    http_method = "POST"
    request_url = request_url.replace("ws://", "http://").replace("wss://", "https://")
    parsed_url = urlparse(request_url)
    host = parsed_url.hostname or ""
    date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    path = parsed_url.path or "/"
    request_line = f"{http_method} {path} HTTP/1.1"

    signature = get_signature(host, date_str, request_line, api_secret)
    auth_string = (
        f'hmac api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}", '
        f'modelId="{model_id}", modelSource="{model_source}", '
        f'traceId="{trace_id}", host="{host}", '
        f'date="{date_str}", request-line="{request_line}"'
    )
    return base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
