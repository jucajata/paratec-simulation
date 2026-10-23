# Comandos públicos (constitución IV). Quien clona el repo solo necesita uv y pnpm.
PNPM ?= pnpm
DEMO_DATE ?= 2026-10-20
DEMO_PERIOD ?= 19

.PHONY: dev demo test package backend-dev frontend-dev

## Levanta backend (127.0.0.1:8000) y frontend (127.0.0.1:5173) en local.
dev:
	@$(MAKE) -j2 backend-dev frontend-dev

backend-dev:
	cd backend && uv run uvicorn sinsim.api.app:app --host 127.0.0.1 --port 8000 --reload

frontend-dev:
	cd frontend && $(PNPM) dev --host 127.0.0.1 --port 5173

## Ejecuta un caso de ejemplo con el snapshot incluido, sin red.
demo:
	cd backend && uv run sinsim run --fecha $(DEMO_DATE) --periodo $(DEMO_PERIOD) --exportar ../out/demo

## Corre todas las pruebas: backend (con cobertura), frontend y e2e.
test:
	cd backend && uv run pytest --cov --cov-report=term-missing
	cd frontend && $(PNPM) test
	cd frontend && $(PNPM) exec playwright test

## Construye la interfaz y el paquete instalable (wheel y sdist) en backend/dist/.
package:
	cd frontend && $(PNPM) install --frozen-lockfile && $(PNPM) build
	cd backend && uv build
