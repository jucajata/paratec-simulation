# Spec: sinsim instalable como herramienta

**Feature**: 002-paquete-instalable | **Fecha**: 2026-10-23 | **Estado**: aprobada por el usuario
**Origen**: decisión del usuario del 2026-10-23 («Sí, hagámoslo») sobre los pasos 1 a 3 propuestos:
incluir configuración y equivalencias en el paquete, separar los datos del código y servir la
interfaz desde la API.

## Problema

Hoy sinsim solo funciona dentro de una copia del repositorio. Instalado como paquete
(`uv tool install …`), el comando `sinsim` falla porque busca `config/defaults.toml`,
`data/paratec/`, `data/equivalencias/` y `data/geo/` en la carpeta actual. La interfaz web,
además, solo corre con el servidor de desarrollo de Vite y pnpm.

## Historias de usuario

### HU-5. Instalar y usar sinsim sin clonar el repositorio (prioridad P1)

Como analista del SIN, quiero instalar sinsim con un comando y usarlo desde cualquier carpeta,
para simular sin preparar un entorno de desarrollo.

**Aceptación**

1. Con el paquete instalado y fuera del repositorio, `sinsim snapshots list` muestra el snapshot
   incluido en el paquete, sin acceso a internet.
2. `sinsim run --fecha 2026-10-20 --periodo 19` construye el caso y corre el flujo AC desde
   cualquier carpeta, con el mismo resultado que en el repositorio.
3. `sinsim scrape --fecha F` guarda el snapshot nuevo en la carpeta de datos del usuario, y
   desde ahí lo usan `snapshots list`, `run` y la interfaz.
4. `sinsim serve` levanta la API y la interfaz en `127.0.0.1` y abre el navegador.

### HU-6. Quien clona el repositorio no nota ningún cambio (prioridad P1)

Como colaborador, quiero que `uv sync`, `make demo`, `make dev` y `make test` sigan funcionando
igual, con los datos del repositorio.

**Aceptación**

1. Dentro del repositorio, sinsim usa `config/`, `data/` y `cases/` del repositorio, como hasta
   ahora.
2. Las pruebas existentes pasan sin cambios de comportamiento.

## Requisitos funcionales

- **FR-040** Modos: si `config/defaults.toml` existe en la carpeta actual o en una superior, o junto
  al paquete instalado en modo editable, sinsim trabaja en **modo repositorio** (sin cambios). Si
  no, trabaja en **modo instalado**.
- **FR-041** Carpeta de datos del usuario (modo instalado): `$SINSIM_HOME` si está definida; si no,
  la convención del sistema operativo: `~/Library/Application Support/sinsim` (macOS),
  `$XDG_DATA_HOME/sinsim` o `~/.local/share/sinsim` (Linux) y `%LOCALAPPDATA%\sinsim` (Windows).
  Dentro: `paratec/` (snapshots) y `cases/` (casos).
- **FR-042** El paquete incluye, como recursos de solo lectura: `config/defaults.toml`, las tablas
  `data/equivalencias/*.csv`, el mapa base `data/geo/`, el snapshot de demostración
  `data/paratec/2026-10-20/` y, si está construida, la interfaz `frontend/dist/`.
- **FR-043** Snapshots en modo instalado: se leen de la carpeta del usuario y del snapshot incluido;
  si una fecha está en las dos, gana la del usuario. Solo se escribe en la carpeta del usuario. Una
  fecha disponible en cualquiera de las dos no se vuelve a descargar (`SNAPSHOT_EXISTS`). El
  snapshot incluido se verifica contra su manifiesto como cualquier otro (III.4).
- **FR-044** `sinsim serve [--puerto N] [--abrir/--no-abrir]` sirve la API en `127.0.0.1` (NG-08) y,
  si la interfaz está disponible, la interfaz en la raíz. Por defecto usa el puerto 8000 y abre el
  navegador. Sin interfaz construida, sirve solo la API y lo dice.
- **FR-045** La API sirve la interfaz construida desde `/`, sin afectar las rutas `/api/…`. En modo
  repositorio usa `frontend/dist/` si existe.
- **FR-046** Al publicar un release en GitHub, una acción construye la interfaz y el paquete y adjunta
  el wheel y el sdist al release. Con eso se instala con
  `uv tool install <url del wheel del release>`.

- **FR-047** La API rechaza las peticiones de páginas ajenas. Toda petición debe ir dirigida a
  `127.0.0.1` o `localhost`; si no, responde 400 `HOST_NOT_ALLOWED` (contra DNS rebinding). En
  los métodos que modifican, si el navegador declara un origen (`Origin` o `Referer`), debe ser
  local; si no, responde 403 `ORIGIN_NOT_ALLOWED` (contra CSRF). Las peticiones sin esas
  cabeceras (CLI, scripts) se aceptan. Origen: hallazgo de la revisión de seguridad, validado
  contra la API local y aprobado por el usuario el 2026-10-23.

## Fuera de alcance

- Publicar en PyPI (paso 4 de la propuesta): requiere decidir el nombre y la cuenta.
- Tablas de equivalencias editables en modo instalado: quien cura equivalencias trabaja en el
  repositorio y aporta por pull request.
- Escuchar en otra interfaz distinta de `127.0.0.1`.

## Criterios de éxito

- **SC-010** Un wheel construido con `make package` se instala con `uv tool install` en un entorno
  limpio y, fuera del repositorio, ejecuta `snapshots list`, `run` y `serve` sin internet.
- **SC-011** El resultado de `sinsim run --fecha 2026-10-20 --periodo 19` instalado coincide con el del
  repositorio: mismo `case_id`.
- **SC-012** Todas las pruebas existentes pasan; las nuevas cubren la resolución de rutas, la lectura
  de snapshots en dos carpetas, el servicio de la interfaz, el comando `serve` y la protección de
  FR-047.
- **SC-013** Un POST con un origen ajeno y una petición con un host ajeno no llegan a la lógica de
  la API; la interfaz local, por Vite o por `sinsim serve`, sigue funcionando.
