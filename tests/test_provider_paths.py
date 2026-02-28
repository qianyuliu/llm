import asyncio

from app.auth.strategies import NoAuth
from app.providers.base import Provider


def test_provider_path_override_can_use_base_url_directly() -> None:
    provider = Provider(
        provider_id="internal",
        base_url="http://example.local/openapi/chat",
        auth_strategy=NoAuth(),
        path_overrides={"/chat/completions": ""},
    )
    url, _, _ = asyncio.run(provider.request_spec("/chat/completions", "model-a"))
    assert url == "http://example.local/openapi/chat"


def test_provider_path_override_relative_path() -> None:
    provider = Provider(
        provider_id="internal",
        base_url="http://example.local/openapi",
        auth_strategy=NoAuth(),
        path_overrides={"/chat/completions": "/v2/chat"},
    )
    url, _, _ = asyncio.run(provider.request_spec("/chat/completions", "model-a"))
    assert url == "http://example.local/openapi/v2/chat"

