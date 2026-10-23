# Plan: sinsim instalable como herramienta

**Feature**: 002-paquete-instalable | **Spec**: [spec.md](./spec.md) | **Fecha**: 2026-10-23
**Constitución**: v1.2.0 (esta feature la enmienda: ver «Revisión de cumplimiento»).

## Resumen

sinsim pasa a tener dos modos. En **modo repositorio** todo sigue igual. En **modo instalado**
la configuración, las equivalencias, el mapa base, un snapshot de demostración y la interfaz
viajan dentro del paquete como recursos de solo lectura, y lo que el usuario genera (snapshots
descargados y casos) va a una carpeta de datos del usuario. Un comando nuevo, `sinsim serve`,
levanta API e interfaz juntas. Una acción de GitHub adjunta el paquete a cada release.

## Contexto técnico

- Empaquetado: hatchling con un *build hook* propio (`backend/hatch_build.py`) que copia los
  recursos del repositorio al paquete: `sinsim/_bundled/` (config, equivalencias, geo, snapshot)
  y `sinsim/web/` (interfaz). El sdist los lleva en `_bundle_src/` para poder construir el wheel
  desde el sdist.
- Rutas: `sinsim.config.resolve_paths()` reemplaza a `repo_paths()` y devuelve `RepoPaths` con dos
  campos nuevos: `mode` y `bundled_snapshots`, más `web`. `repo_paths()` se conserva para el modo
  repositorio.
- Carpeta de datos: función pura `user_data_dir(env, platform, home)`; sin dependencias nuevas.
- Snapshots: `ParquetSnapshotRepository(root, read_only_roots=())` busca cada fecha primero en
  `root` y luego en las raíces de solo lectura. Escribe solo en `root`.
- Interfaz: `StaticFiles(html=True)` montado en `/` después de los routers de `/api`.
- `sinsim serve`: `uvicorn.run(create_app(), host="127.0.0.1", port=…)`; abre el navegador con
  `webbrowser` cuando el servidor está listo.
- Distribución: `.github/workflows/release.yml`, disparado al publicar un release.

## Revisión de cumplimiento de la constitución

- **I. Naturaleza**: sin cambio de alcance. El principio de reproducibilidad se mantiene: el
  paquete incluye un snapshot y simula sin internet.
- **II. Stack**: sin dependencias nuevas; hatchling ya era el backend de construcción.
- **III. Reglas de dominio**: III.4 dice que cada snapshot vive en `data/paratec/<fecha>/`. En
  modo instalado vive en la carpeta de datos del usuario o dentro del paquete. Se enmienda III.4
  (MINOR) para nombrar las dos ubicaciones; la inmutabilidad, el manifiesto y la verificación no
  cambian. El snapshot incluido es una copia byte a byte del versionado.
- **IV. Estructura**: se añaden `backend/hatch_build.py`, `.github/workflows/release.yml` y el
  comando público `sinsim serve`. Se enmienda IV (MINOR).
- **V. Errores**: sin códigos nuevos.
- **VI. Agente**: esta spec, este plan y las tareas documentan el comando, la variable
  `SINSIM_HOME`, el *build hook* y la acción antes de implementarlos (VI.2). No se tocan archivos de
  `data/paratec/` (VI.5): el paquete los copia al construirse.

## Decisiones del usuario (2026-10-23)

1. Hacer los pasos 1 a 3: recursos en el paquete, datos separados del código, interfaz servida
   por la API.
2. Publicar en PyPI queda para después.

## Decisiones de diseño

- **Snapshot incluido**: el del 2026-10-20 (el de `make demo`). Unos 6 MB; deja el wheel muy por
  debajo de los límites habituales y permite simular sin internet.
- **Detección del modo**: la misma regla que ya usaba `find_repo_root`. Así quien ejecuta el
  paquete instalado dentro del repositorio trabaja con los datos del repositorio, que es lo
  esperable.
- **Mismo caso en ambos modos**: config, equivalencias y snapshot se copian sin transformar, así que
  sus SHA-256, y por tanto el `case_id`, coinciden (SC-011).

## Riesgos

- Un wheel construido sin `frontend/dist/` no trae interfaz. Mitigación: `make package` construye la
  interfaz primero; la acción de release también; `sinsim serve` avisa si falta.
- `requires-python` exige 3.12. `uv tool install` descarga Python 3.12 si hace falta.
