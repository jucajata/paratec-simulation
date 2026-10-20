"""Cliente HTTP del scraper (constitución III.10, FR-007).

- User-Agent descriptivo con la versión de `sinsim`.
- Espera mínima entre peticiones (`scraper.min_interval_s`); nunca en paralelo.
- Errores de conexión, tiempo de espera o 5xx → `NETWORK_ERROR` (código de salida 3).
- `transport` inyectable para pruebas (`httpx.MockTransport`); las pruebas nunca llaman a las
  fuentes reales (R-03).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass

import httpx

from sinsim.domain.errors import DomainError
from sinsim.observability import log_event

log = logging.getLogger("sinsim.scraper")

DEFAULT_TRANSPORT: httpx.BaseTransport | None = None
"""Transporte por defecto; las pruebas lo sustituyen por `httpx.MockTransport` (R-03)."""


@dataclass(frozen=True)
class Fetched:
    """Respuesta descargada."""

    url: str
    content: bytes
    headers: Mapping[str, str]
    status: int


class RateLimitedClient:
    """Cliente `httpx` con límite de tasa y manejo de errores de dominio."""

    def __init__(
        self,
        *,
        user_agent: str,
        min_interval_s: float,
        timeout_s: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Crea el cliente; `transport` permite inyectar respuestas grabadas."""
        self.min_interval_s = min_interval_s
        self._last = 0.0
        self._client = httpx.Client(
            headers={"User-Agent": user_agent, "Accept": "application/json, text/plain, */*"},
            timeout=timeout_s,
            transport=transport or DEFAULT_TRANSPORT,
            follow_redirects=True,
        )

    def close(self) -> None:
        """Cierra la conexión."""
        self._client.close()

    def __enter__(self) -> RateLimitedClient:
        """Soporte de `with`."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Cierra al salir del `with`."""
        self.close()

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last
        if elapsed < self.min_interval_s:
            time.sleep(self.min_interval_s - elapsed)
        self._last = time.monotonic()

    def get(self, url: str, params: Mapping[str, str] | None = None) -> Fetched:
        """Descarga `url` respetando el límite de tasa.

        Raises:
            DomainError: `NETWORK_ERROR` si no hay conexión, se agota el tiempo o el servidor
                responde 5xx; `XM_FILE_NOT_FOUND` ante un 404; otros 4xx → `NETWORK_ERROR`
                con el estado en `detail`.
        """
        self._wait()
        try:
            response = self._client.get(url, params=params)
        except httpx.TransportError as exc:
            raise DomainError("NETWORK_ERROR", f"{url}: {type(exc).__name__}: {exc}") from exc
        log_event(
            log,
            "GET",
            url=str(response.url),
            status=response.status_code,
            bytes=len(response.content),
        )
        if response.status_code == 404:
            raise DomainError("XM_FILE_NOT_FOUND", f"{response.url}: 404")
        if response.status_code >= 500:
            raise DomainError("NETWORK_ERROR", f"{response.url}: HTTP {response.status_code}")
        if response.status_code >= 400:
            raise DomainError("NETWORK_ERROR", f"{response.url}: HTTP {response.status_code}")
        return Fetched(
            url=str(response.url),
            content=response.content,
            headers=dict(response.headers),
            status=response.status_code,
        )
