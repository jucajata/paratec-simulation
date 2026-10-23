"""La API local rechaza peticiones de páginas ajenas (FR-047): DNS rebinding y CSRF."""

import pytest
from fastapi.testclient import TestClient

from sinsim.api.app import create_app
from sinsim.api.security import host_allowed, hostname_of, origin_allowed

EXISTING = "/api/snapshots/2026-10-20/descarga"  # ya existe: responde 409 sin descargar nada


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("127.0.0.1:8000", "127.0.0.1"),
        ("LOCALHOST", "localhost"),
        ("[::1]:8000", "[::1]"),
        ("sitio-malicioso.example:8000", "sitio-malicioso.example"),
    ],
)
def test_hostname_of_strips_the_port(header: str, expected: str):
    assert hostname_of(header) == expected


def test_only_local_hosts_are_allowed():
    assert host_allowed("127.0.0.1:8000") and host_allowed("localhost:5173")
    assert not host_allowed("sitio-malicioso.example")
    assert not host_allowed("127.0.0.1.sitio-malicioso.example")
    assert not host_allowed(None)


@pytest.mark.parametrize(
    ("method", "origin", "referer", "allowed"),
    [
        (
            "GET",
            "https://sitio-malicioso.example",
            None,
            True,
        ),  # lectura: el navegador no la expone
        ("POST", None, None, True),  # CLI, curl, scripts
        ("POST", "http://127.0.0.1:5173", None, True),  # interfaz en desarrollo (Vite)
        ("POST", "http://localhost:8000", None, True),  # interfaz servida por sinsim serve
        ("POST", "https://sitio-malicioso.example", None, False),
        ("POST", None, "https://sitio-malicioso.example/pagina", False),
        ("DELETE", "null", None, False),  # iframe aislado o archivo local
    ],
)
def test_origin_rules(method: str, origin: str | None, referer: str | None, allowed: bool):
    assert origin_allowed(method, origin, referer) is allowed


@pytest.fixture
def client(app_context) -> TestClient:
    return TestClient(create_app(app_context), base_url="http://127.0.0.1:8000")


def test_a_foreign_host_gets_a_problem_and_no_data(client: TestClient):
    r = client.get("/api/snapshots", headers={"host": "sitio-malicioso.example"})
    assert r.status_code == 400
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["code"] == "HOST_NOT_ALLOWED" and body["trace_id"]
    assert "2026-10-20" not in r.text


def test_localhost_is_accepted(client: TestClient):
    assert client.get("/api/snapshots", headers={"host": "localhost:8000"}).status_code == 200


def test_a_foreign_page_cannot_start_a_download(client: TestClient):
    r = client.post(EXISTING, headers={"origin": "https://sitio-malicioso.example"})
    assert r.status_code == 403 and r.json()["code"] == "ORIGIN_NOT_ALLOWED"


def test_the_local_interface_and_the_cli_still_can(client: TestClient):
    from_ui = client.post(EXISTING, headers={"origin": "http://127.0.0.1:8000"})
    without_origin = client.post(EXISTING)
    assert from_ui.json()["code"] == without_origin.json()["code"] == "SNAPSHOT_EXISTS"
