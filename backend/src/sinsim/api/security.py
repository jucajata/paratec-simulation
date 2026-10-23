"""Protección de la API local contra páginas ajenas (FR-047).

La API escucha solo en 127.0.0.1 y no tiene autenticación (NG-08). El riesgo no viene de la
red sino del navegador del propio usuario: cualquier página que visite puede enviar peticiones
a 127.0.0.1. Dos reglas lo cierran:

- **Host local**: toda petición debe ir dirigida a `127.0.0.1` o `localhost`. Bloquea el DNS
  rebinding, en el que un dominio ajeno pasa a resolver a 127.0.0.1 para leer las respuestas.
- **Origen local en cambios**: en métodos que modifican (POST, PUT, PATCH, DELETE), si el
  navegador declara un origen (`Origin`, o `Referer` en su defecto), debe ser local. Bloquea el
  CSRF. Sin esas cabeceras la petición no viene de una página web (CLI, curl, scripts) y se
  acepta: un navegador siempre envía `Origin` en un POST hacia otro sitio.

Funciones puras: el middleware de `api/app.py` solo las consulta.
"""

from __future__ import annotations

from urllib.parse import urlsplit

LOCAL_HOSTNAMES = frozenset({"127.0.0.1", "localhost"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def hostname_of(host_header: str) -> str:
    """Nombre de host de una cabecera `Host`, sin puerto y en minúsculas."""
    value = host_header.strip().lower()
    if value.startswith("["):  # IPv6 con puerto: [::1]:8000
        return value.split("]", 1)[0] + "]"
    return value.split(":", 1)[0]


def host_allowed(host_header: str | None) -> bool:
    """¿La petición va dirigida a 127.0.0.1 o localhost?"""
    return host_header is not None and hostname_of(host_header) in LOCAL_HOSTNAMES


def origin_allowed(method: str, origin: str | None, referer: str | None) -> bool:
    """¿Se acepta el origen de la petición? Solo se restringen los métodos que modifican."""
    if method.upper() in SAFE_METHODS:
        return True
    source = origin or referer
    if not source:
        return True
    if source.strip().lower() == "null":  # iframes aislados, archivos locales
        return False
    return urlsplit(source).hostname in LOCAL_HOSTNAMES
