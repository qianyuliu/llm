"""Tests for _deep_merge and provider_defaults functionality."""
import json
import tempfile
from pathlib import Path

from app.config import GatewayConfig, _deep_merge


def test_deep_merge_basic() -> None:
    base = {"a": 1, "b": 2}
    override = {"b": 3, "c": 4}
    result = _deep_merge(base, override)
    assert result == {"a": 1, "b": 3, "c": 4}


def test_deep_merge_nested_dicts() -> None:
    base = {"auth": {"key1": "v1", "key2": "v2"}}
    override = {"auth": {"key2": "override", "key3": "v3"}}
    result = _deep_merge(base, override)
    assert result == {"auth": {"key1": "v1", "key2": "override", "key3": "v3"}}


def test_deep_merge_override_replaces_non_dict() -> None:
    base = {"auth": {"key": "v"}, "timeout": 300}
    override = {"auth": "replaced", "timeout": 60}
    result = _deep_merge(base, override)
    assert result == {"auth": "replaced", "timeout": 60}


def test_provider_defaults_applied(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_BASE", "http://test:9060/api")
    monkeypatch.setenv("OPENAI_API_ID", "test-id")
    monkeypatch.setenv("OPENAI_API_SECRET", "test-secret")
    monkeypatch.setenv("MODELSOURCE", "private")
    monkeypatch.setenv("TRACE_ID", "trace-123")

    registry = {
        "provider_defaults": {
            "juzhi": {
                "base_url_env": "OPENAI_API_BASE",
                "timeout_seconds": 300,
                "auth": {
                    "api_id_env": "OPENAI_API_ID",
                    "api_secret_env": "OPENAI_API_SECRET",
                    "model_id_from": "env",
                    "model_source_env": "MODELSOURCE",
                    "trace_id_env": "TRACE_ID",
                },
                "path_overrides": {"/chat/completions": ""},
            }
        },
        "providers": [
            {
                "id": "juzhi_test",
                "provider_type": "juzhi",
                "auth": {"model_id_env": "TEST_MODEL_ID"},
                "models": [{"alias": "juzhi_test", "upstream_model": "test_model"}],
            }
        ],
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(registry, f)
        f.flush()
        config = GatewayConfig.from_file(Path(f.name))

    provider = config.providers[0]
    assert provider.base_url_env == "OPENAI_API_BASE"
    assert provider.timeout_seconds == 300
    assert provider.path_overrides == {"/chat/completions": ""}
    # auth should be deep-merged: defaults + override
    assert provider.auth["api_id_env"] == "OPENAI_API_ID"
    assert provider.auth["model_id_env"] == "TEST_MODEL_ID"
    assert provider.auth["model_id_from"] == "env"
