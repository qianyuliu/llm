from __future__ import annotations

from dataclasses import dataclass, field

from app.auth import AuthContext, AuthStrategy


@dataclass
class Provider:
    provider_id: str
    base_url: str
    auth_strategy: AuthStrategy
    timeout_seconds: float = 300.0
    extra_headers: dict[str, str] = field(default_factory=dict)
    path_overrides: dict[str, str] = field(default_factory=dict)

    async def request_spec(
        self,
        path: str,
        upstream_model: str,
    ) -> tuple[str, dict[str, str], float]:
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            **self.extra_headers,
        }
        dynamic = await self.auth_strategy.headers(
            AuthContext(provider_id=self.provider_id, upstream_model=upstream_model)
        )
        headers.update(dynamic)
        url = self._resolve_url(path)
        return url, headers, self.timeout_seconds

    def _resolve_url(self, path: str) -> str:
        override = self.path_overrides.get(path)
        if override is None:
            return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        cleaned = override.strip()
        if not cleaned:
            return self.base_url
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            return cleaned
        return f"{self.base_url.rstrip('/')}/{cleaned.lstrip('/')}"
