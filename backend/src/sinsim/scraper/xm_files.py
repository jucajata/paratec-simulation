"""Listado y descarga de los archivos públicos de XM (research R2, R3).

La biblioteca web de XM consume una API no documentada (puede cambiar sin aviso):

- Listar: `GET {BASE}?ruta=<carpeta>/<AAAA-MM>&contenedor=storageportalxm&...&nombre=<prefijo>`
- Descargar: `GET {BASE}/descarga-archivo?ruta=<carpeta sin barra inicial>/<AAAA-MM>/<archivo>
  &nombreBlobContainer=storageportalxm`

Se descargan **todas** las versiones `dDEC<MMDD>*.txt` del día (D-3) y el `PRON_BARRA<MMDD>`.
La fecha de modificación que reporta el listado se guarda en el manifiesto (FR-003). Un JSON
con otra estructura es `XM_FILE_SCHEMA_CHANGED`; un día sin archivo es `XM_FILE_NOT_FOUND`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final

from sinsim.adapters.sources_to_pandapower.xm_dispatch import STANDARD_VERSION, dispatch_version_of
from sinsim.domain.entities import SourceFile
from sinsim.domain.errors import DomainError
from sinsim.scraper.http import RateLimitedClient

BASE_URL: Final = "https://api-portalxm.xm.com.co/administracion-archivos/ficheros"
CONTAINER: Final = "storageportalxm"
DISPATCH_DIR: Final = "/M:/InformacionAgentes/Usuarios/Publico/DESPACHO"
DEMAND_DIR: Final = "/M:/InformacionAgentes/Usuarios/Publico/DEMANDAS/Pronostico Oficial"

_NAME_KEYS = ("nombre", "name", "Nombre", "Name")
_MODIFIED_KEYS = ("fechaModificacion", "FechaModificacion", "modified", "lastModified")


@dataclass(frozen=True)
class FileInfo:
    """Archivo listado por el portal de XM."""

    name: str
    modified_at: datetime | None


def list_url_params(directory: str, month: str, prefix: str) -> dict[str, str]:
    """Parámetros del listado para una carpeta, un mes `AAAA-MM` y un prefijo de nombre."""
    return {
        "ruta": f"{directory}/{month}",
        "contenedor": CONTAINER,
        "ordenarPor": "nombre",
        "orden": "DESC",
        "pagina": "1",
        "resultadosPorPagina": "50",
        "nombre": prefix,
    }


def download_url_params(directory: str, month: str, filename: str) -> dict[str, str]:
    """Parámetros de descarga: la ruta va sin la barra inicial."""
    return {
        "ruta": f"{directory.lstrip('/')}/{month}/{filename}",
        "nombreBlobContainer": CONTAINER,
    }


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_listing(payload: bytes) -> list[FileInfo]:
    """Interpreta el JSON del listado de forma tolerante a la envoltura.

    Acepta una lista de registros o un objeto con una lista bajo cualquier clave; cada
    registro debe traer un nombre. Cualquier otra forma es `XM_FILE_SCHEMA_CHANGED`.
    """
    try:
        doc = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DomainError(
            "XM_FILE_SCHEMA_CHANGED", "el listado del portal de XM no es JSON"
        ) from exc
    items: list[Any] | None = None
    if isinstance(doc, list):
        items = doc
    elif isinstance(doc, dict):
        for value in doc.values():
            if isinstance(value, list):
                items = value
                break
    if items is None:
        raise DomainError(
            "XM_FILE_SCHEMA_CHANGED", "el listado del portal de XM no contiene una lista"
        )
    files: list[FileInfo] = []
    for item in items:
        if not isinstance(item, dict):
            raise DomainError(
                "XM_FILE_SCHEMA_CHANGED", "registro del listado sin estructura de objeto"
            )
        name = next((str(item[k]) for k in _NAME_KEYS if k in item), None)
        if not name:
            raise DomainError("XM_FILE_SCHEMA_CHANGED", "registro del listado sin nombre")
        modified = next((_parse_datetime(item[k]) for k in _MODIFIED_KEYS if k in item), None)
        files.append(FileInfo(name=name.strip(), modified_at=modified))
    return files


def list_files(
    client: RateLimitedClient, directory: str, month: str, prefix: str
) -> list[FileInfo]:
    """Lista los archivos de una carpeta y mes que empiezan por `prefix`."""
    fetched = client.get(BASE_URL, params=list_url_params(directory, month, prefix))
    return [f for f in parse_listing(fetched.content) if f.name.upper().startswith(prefix.upper())]


def download(
    client: RateLimitedClient, directory: str, month: str, filename: str
) -> tuple[bytes, str]:
    """Descarga un archivo; devuelve `(bytes, url)`."""
    fetched = client.get(
        f"{BASE_URL}/descarga-archivo", params=download_url_params(directory, month, filename)
    )
    if not fetched.content.strip():
        raise DomainError(
            "XM_FILE_SCHEMA_CHANGED", f"{filename}: el portal devolvió un archivo vacío"
        )
    return fetched.content, fetched.url


def fetch_for_date(
    client: RateLimitedClient, day: date
) -> tuple[dict[str, bytes], list[SourceFile]]:
    """Descarga `dDEC<MMDD>*` (todas las versiones) y `PRON_BARRA<MMDD>` de un día.

    Returns:
        `(archivos por nombre, fuentes para el manifiesto)`.

    Raises:
        DomainError: `XM_FILE_NOT_FOUND` si falta el despacho o el pronóstico del día.
    """
    month = day.strftime("%Y-%m")
    mmdd = day.strftime("%m%d")
    files: dict[str, bytes] = {}
    sources: list[SourceFile] = []

    dispatch_files = [
        f
        for f in list_files(client, DISPATCH_DIR, month, f"dDEC{mmdd}")
        if dispatch_version_of(f.name) is not None
    ]
    if not dispatch_files:
        raise DomainError("XM_FILE_NOT_FOUND", f"no hay dDEC{mmdd}*.txt en {DISPATCH_DIR}/{month}")
    for info in sorted(dispatch_files, key=lambda f: f.name):
        content, url = download(client, DISPATCH_DIR, month, info.name)
        files[info.name] = content
        sources.append(
            SourceFile(
                entity="xm.dispatch",
                url=url,
                source_modified_at=info.modified_at,
                standard_version=STANDARD_VERSION,
            )
        )

    demand_files = _unique_names(list_files(client, DEMAND_DIR, month, f"PRON_BARRA{mmdd}"))
    if not demand_files:
        raise DomainError("XM_FILE_NOT_FOUND", f"no hay PRON_BARRA{mmdd} en {DEMAND_DIR}/{month}")
    info = demand_files[0]
    content, url = download(client, DEMAND_DIR, month, info.name)
    files[info.name] = content
    sources.append(
        SourceFile(
            entity="xm.demand",
            url=url,
            source_modified_at=info.modified_at,
            standard_version=STANDARD_VERSION,
        )
    )
    return files, sources


def _unique_names(files: Iterable[FileInfo]) -> list[FileInfo]:
    seen: set[str] = set()
    out: list[FileInfo] = []
    for f in files:
        if f.name not in seen:
            seen.add(f.name)
            out.append(f)
    return out
