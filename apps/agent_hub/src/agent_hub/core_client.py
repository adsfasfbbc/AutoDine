from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from .errors import CoreAPIError


class CoreClient:
    """HTTP client for the AutoDineCore (中台) REST API.

    This is the only place in agent_hub that talks to the Core. Agents never
    touch the Core database or import ``autodine_core`` internals; they go
    through this client and the tool layer.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 15.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        response = self._client.request(method, path, params=params, json=json)

        try:
            envelope = response.json()
        except ValueError:
            envelope = {}

        if response.is_error:
            if isinstance(envelope, dict):
                code = envelope.get("code")
                message = envelope.get("message") or response.text[:512]
            else:
                code = response.status_code
                message = response.text[:512]
            raise CoreAPIError(status_code=response.status_code, code=code, message=message)

        return envelope.get("data") if isinstance(envelope, dict) else envelope

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CoreClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
