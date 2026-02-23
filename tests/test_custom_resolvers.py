import base64

from custom_resolvers import get_api_key


def test_get_api_key_contains_required_fields() -> None:
    token = get_api_key(
        request_url="http://example.local/openapi/flames/api/v1/openai/chat",
        api_key="api-id",
        api_secret="api-secret",
        model_id="model-id",
        model_source="private",
        trace_id="trace-1",
    )
    decoded = base64.b64decode(token).decode("utf-8")
    assert 'hmac api_key="api-id"' in decoded
    assert 'modelId="model-id"' in decoded
    assert 'modelSource="private"' in decoded
    assert 'traceId="trace-1"' in decoded
    assert "POST /openapi/flames/api/v1/openai/chat HTTP/1.1" in decoded

