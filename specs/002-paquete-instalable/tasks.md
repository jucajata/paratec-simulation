# Tareas: sinsim instalable como herramienta

**Entrada**: [spec.md](./spec.md), [plan.md](./plan.md)
**Constitución**: v1.2.0. Las pruebas son condición de cierre (VI.6).

## Formato: `[ID] [P?] [Historia] Descripción con ruta`

## Fase 1: Gobernanza

- [X] T200 Enmendar la constitución a v1.2.0: III.4 nombra las ubicaciones de los snapshots en modo
  instalado; IV suma `hatch_build.py`, la acción de release y `sinsim serve`
  (`.specify/memory/constitution.md`).

## Fase 2: Rutas y datos (HU-5, HU-6)

- [X] T201 [US5] `user_data_dir()` pura, con `SINSIM_HOME` y convenciones por sistema; pruebas
  (`backend/src/sinsim/config.py`, `backend/tests/unit/test_paths.py`).
- [X] T202 [US5] `resolve_paths()`: modo repositorio o instalado; `RepoPaths` con `mode`,
  `bundled_snapshots` y `web`; `load_config` y `build_context` la usan; pruebas.
- [X] T203 [US5] `ParquetSnapshotRepository` con raíces de solo lectura; pruebas de lista, carga y
  precedencia (`backend/src/sinsim/adapters/storage/snapshots.py`,
  `backend/tests/unit/test_snapshot_roots.py`).

## Fase 3: Interfaz y comando (HU-5)

- [X] T204 [US5] Servir la interfaz construida desde `/` en la API; pruebas
  (`backend/src/sinsim/api/app.py`, `backend/tests/contract/test_web.py`).
- [X] T205 [US5] Comando `sinsim serve`; pruebas (`backend/src/sinsim/cli.py`).

## Fase 4: Empaquetado y distribución (HU-5)

- [X] T206 [US5] *Build hook* que copia config, equivalencias, geo, snapshot de demostración e
  interfaz al paquete (`backend/hatch_build.py`, `backend/pyproject.toml`).
- [X] T207 [US5] `make package` (`Makefile`).
- [X] T208 [US5] Acción de release que adjunta wheel y sdist (`.github/workflows/release.yml`).
- [X] T209 [US5] Verificación SC-010 y SC-011: instalar el wheel en un entorno limpio y ejecutar
  `snapshots list`, `run` y `serve` fuera del repositorio.

## Fase 5: Documentación y versión

- [X] T210 README: instalación como herramienta, carpeta de datos y `sinsim serve`; supuesto S22;
  CHANGELOG 0.5.0; versión 0.5.0 en backend y frontend.
