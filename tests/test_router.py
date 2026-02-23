import pytest

from app.auth.strategies import NoAuth
from app.providers.base import Provider
from app.providers.router import ModelRouter


def test_router_rejects_duplicate_alias() -> None:
    router = ModelRouter()
    provider_a = Provider(
        provider_id="a",
        base_url="http://example-a.local",
        auth_strategy=NoAuth(),
    )
    provider_b = Provider(
        provider_id="b",
        base_url="http://example-b.local",
        auth_strategy=NoAuth(),
    )
    router.register("qwen3_coder", "qwen3_coder", provider_a)
    with pytest.raises(RuntimeError):
        router.register("qwen3_coder", "another", provider_b)

