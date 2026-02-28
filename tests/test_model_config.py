from app.config import ConfigError, ModelConfig


def test_model_config_reads_upstream_from_env(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_DEFAULT_MODEL", "model-x")
    model = ModelConfig(alias="qwen_internal", upstream_env="INTERNAL_DEFAULT_MODEL")
    assert model.resolved_upstream("provider-a") == "model-x"


def test_model_config_falls_back_to_literal_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("INTERNAL_DEFAULT_MODEL", raising=False)
    model = ModelConfig(
        alias="qwen_internal",
        upstream_env="INTERNAL_DEFAULT_MODEL",
        upstream="fallback-model",
    )
    assert model.resolved_upstream("provider-a") == "fallback-model"


def test_model_config_requires_upstream_or_env() -> None:
    model = ModelConfig(alias="broken")
    try:
        model.resolved_upstream("provider-a")
    except ConfigError:
        return
    raise AssertionError("Expected ConfigError for missing upstream config")
