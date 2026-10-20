"""Catálogo de endpoints de PARATEC y cliente de descarga (research R1).

En la fase fundacional este módulo solo expone el catálogo, que usan el escritor de snapshots
y las pruebas. El cliente HTTP (`fetch_all`) se completa en la historia de usuario 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from sinsim.domain.entities import SourceFile
from sinsim.domain.errors import DomainError
from sinsim.scraper.http import RateLimitedClient
from sinsim.scraper.validate import parse_paratec_response

BASE_URL: Final = "https://paratecbackend.xm.com.co"


@dataclass(frozen=True)
class Endpoint:
    """Un endpoint JSON de PARATEC."""

    entity: str
    service: str
    path: str

    @property
    def url(self) -> str:
        """URL completa del endpoint."""
        return f"{BASE_URL}/{self.service}/api/{self.path}"

    @property
    def raw_name(self) -> str:
        """Nombre del archivo crudo: `<servicio>__<Recurso_método>.json`."""
        return f"{self.service}__{self.path.replace('/', '_')}.json"


ENDPOINTS: Final[tuple[Endpoint, ...]] = (
    Endpoint("paratec.substations", "reportetransmision", "Substation/SubstationInfo"),
    Endpoint("paratec.lines", "reportetransmision", "Line/getAll"),
    Endpoint("paratec.line_map", "mapas", "TransmissionMap/getLines"),
    Endpoint("paratec.reactors", "reportetransmision", "Reactor/getAll"),
    Endpoint("paratec.svc_statcom", "reportetransmision", "StatcomSvc/getAll"),
    Endpoint(
        "paratec.transformers", "reportetransformacion", "PowerTransformer/PowerTransformerInfo"
    ),
    Endpoint("paratec.hydraulic_units", "reportegeneracion", "HydraulicUnit/HydraulicUnitInfo"),
    Endpoint("paratec.thermal_units", "reportegeneracion", "ThermalUnit/ThermalUnitInfo"),
    Endpoint("paratec.solar_plants", "reportegeneracion", "SolarPlant/getAll"),
    Endpoint("paratec.wind_plants", "reportegeneracion", "WindPlant/WindPlantInfo"),
    Endpoint("paratec.capacitors", "reportegeneracion", "Capacitor/getAll"),
)

BY_ENTITY: Final[dict[str, Endpoint]] = {e.entity: e for e in ENDPOINTS}


def fetch_all(client: RateLimitedClient) -> tuple[dict[str, bytes], list[SourceFile]]:
    """Descarga todas las entidades del catálogo y valida su envoltura JSON.

    Returns:
        `(bytes por entidad, fuentes para el manifiesto)`.

    Raises:
        DomainError: `NETWORK_ERROR` o `PARATEC_SCHEMA_CHANGED`.
    """
    payloads: dict[str, bytes] = {}
    sources: list[SourceFile] = []
    for ep in ENDPOINTS:
        try:
            fetched = client.get(ep.url)
        except DomainError as exc:
            if exc.code == "XM_FILE_NOT_FOUND":
                raise DomainError(
                    "PARATEC_SCHEMA_CHANGED", f"{ep.entity}: el endpoint ya no existe"
                ) from exc
            raise
        parse_paratec_response(ep.entity, fetched.content)
        payloads[ep.entity] = fetched.content
        sources.append(SourceFile(entity=ep.entity, url=ep.url))
    return payloads, sources
