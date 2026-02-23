import asyncio
import base64
import json

from app.auth.strategies import AuthContext, QwenSignatureAuth, _get_capability_name_24


def test_capability_name_is_padded_to_24_chars() -> None:
    assert _get_capability_name_24("qwen3_coder") == "qwen3_coder0000000000000"
    assert len(_get_capability_name_24("qwen3_coder")) == 24


def test_qwen_signature_headers_shape() -> None:
    auth = QwenSignatureAuth(
        appid="deepinsi",
        appkey="secret",
        capability_from="upstream_model",
    )
    headers = asyncio.run(
        auth.headers(AuthContext(provider_id="corp-qwen", upstream_model="qwen3_coder"))
    )
    assert "X-Server-Param" in headers
    assert "X-CurTime" in headers
    assert "X-CheckSum" in headers

    decoded = base64.b64decode(headers["X-Server-Param"]).decode("utf-8")
    parsed = json.loads(decoded)
    assert parsed["appid"] == "deepinsi"
    assert "csid" in parsed


def test_qwen_signature_can_attach_authorization_header() -> None:
    auth = QwenSignatureAuth(
        appid="deepinsi",
        appkey="secret-appkey",
        capability_from="upstream_model",
        token_header="Authorization",
        token_prefix="Bearer ",
    )
    headers = asyncio.run(
        auth.headers(AuthContext(provider_id="corp-qwen", upstream_model="qwen3_coder"))
    )
    assert headers["Authorization"] == "Bearer secret-appkey"
