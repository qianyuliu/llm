from __future__ import annotations

from dataclasses import dataclass

from app.providers.base import Provider


@dataclass(frozen=True)
class ModelRoute:
    alias: str
    upstream_model: str
    provider: Provider


class ModelRouter:
    def __init__(self) -> None:
        self._routes: dict[str, ModelRoute] = {}

    def register(self, alias: str, upstream_model: str, provider: Provider) -> None:
        if alias in self._routes:
            existing_provider = self._routes[alias].provider.provider_id
            raise RuntimeError(
                f"Model alias '{alias}' is duplicated between providers "
                f"'{existing_provider}' and '{provider.provider_id}'."
            )
        self._routes[alias] = ModelRoute(
            alias=alias,
            upstream_model=upstream_model,
            provider=provider,
        )

    def resolve(self, alias: str) -> ModelRoute:
        route = self._routes.get(alias)
        if route is None:
            supported = ", ".join(sorted(self._routes)) or "<empty>"
            raise RuntimeError(
                f"Unknown model '{alias}'. Supported models: {supported}"
            )
        return route

    def list_model_ids(self) -> list[str]:
        return sorted(self._routes.keys())

    def list_openai_models(self) -> dict[str, object]:
        return {
            "object": "list",
            "data": [
                {
                    "id": route.alias,
                    "object": "model",
                    "owned_by": route.provider.provider_id,
                }
                for route in sorted(self._routes.values(), key=lambda item: item.alias)
            ],
        }

