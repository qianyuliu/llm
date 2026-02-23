import asyncio

from app.config import ModelConfig, ProviderConfig
from app.providers.factory import ProviderFactory


def test_panzhi_factory_uses_default_env_contract(monkeypatch) -> None:
    monkeypatch.setenv("PANZHI_BASE_URL", "http://example.local/v1")
    monkeypatch.setenv("PANZHI_APPID", "demo-app")
    monkeypatch.setenv("PANZHI_APPKEY", "demo-key")
    config = ProviderConfig(
        id="panzhi",
        provider_type="panzhi",
        models=[ModelConfig(alias="a", upstream="qwen3_coder")],
    )
    provider = ProviderFactory.create_provider(config)
    url, headers, _ = asyncio.run(provider.request_spec("/chat/completions", "qwen3_coder"))
    assert url == "http://example.local/v1/chat/completions"
    assert "X-Server-Param" in headers
    assert "X-CurTime" in headers
    assert "X-CheckSum" in headers
    assert headers["Authorization"] == "Bearer demo-key"


def test_neibu_factory_defaults_to_base_url_chat_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_BASE", "http://example.local/openapi/chat")
    monkeypatch.setenv("INTERNAL_API_KEY_OVERRIDE", "signed-token")
    config = ProviderConfig(
        id="neibu",
        provider_type="neibu",
        models=[ModelConfig(alias="b", upstream="qwen3")],
    )
    provider = ProviderFactory.create_provider(config)
    url, headers, _ = asyncio.run(provider.request_spec("/chat/completions", "qwen3"))
    assert url == "http://example.local/openapi/chat/chat/completions"
    assert headers["Authorization"] == "Bearer signed-token"
