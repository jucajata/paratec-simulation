# sinsim — flujo de potencia del SIN colombiano

Herramienta open-source (MIT) para construir y simular, con [pandapower](https://www.pandapower.org/),
modelos del Sistema Interconectado Nacional (SIN) de Colombia a partir de:

- los parámetros técnicos de los equipos publicados en **PARATEC** (XM),
- el **despacho programado** diario (`dDEC`) y
- el **pronóstico oficial de demanda por barra** (`PRON_BARRA`) publicados por XM.

> **Información proporcionada por XM S.A. E.S.P. – PARATEC y archivos públicos de despacho.**
> Todo resultado es un *flujo sobre despacho programado*: describe el programa publicado por
> XM, nunca el estado real del SIN.

## Requisitos

- Python 3.12 y [uv](https://docs.astral.sh/uv/)
- Node 20+ y [pnpm](https://pnpm.io/) (solo para la interfaz web)

## Primeros pasos (sin internet, con el snapshot incluido)

```bash
uv sync --project backend
pnpm --dir frontend install     # solo si vas a usar la interfaz
make demo                       # construye el caso del 2026-10-20, periodo 19, y corre el flujo AC
```

`make demo` escribe la exportación en `out/demo/` (cuatro CSV y `metadatos.json`).

## Instalar sin clonar el repositorio

Cada release publicado trae el paquete listo para instalar. Con [uv](https://docs.astral.sh/uv/)
basta un comando; uv descarga Python 3.12 si hace falta:

```bash
uv tool install https://github.com/jucajata/sinsim/releases/download/v0.5.0/sinsim-0.5.0-py3-none-any.whl
sinsim serve          # abre la interfaz en http://127.0.0.1:8000
```

El paquete incluye la configuración, las tablas de equivalencias, el mapa base, la interfaz y
el snapshot del 2026-10-20, así que funciona sin internet desde cualquier carpeta:

```bash
sinsim snapshots list
sinsim run --fecha 2026-10-20 --periodo 19
sinsim scrape --fecha 2026-10-22     # descarga otra fecha a tu carpeta de datos
```

Los snapshots que descargas y los casos que construyes se guardan en tu carpeta de datos:
`~/Library/Application Support/sinsim` en macOS, `~/.local/share/sinsim` en Linux y
`%LOCALAPPDATA%\sinsim` en Windows. Para usar otra, define `SINSIM_HOME`. Dentro de una copia
del repositorio, sinsim usa siempre `config/`, `data/` y `cases/` del repositorio.

Para construir el paquete tú mismo: `make package` (deja el wheel y el sdist en `backend/dist/`).

## Comandos públicos

| Comando | Qué hace |
|---|---|
| `uv run --project backend sinsim snapshots list` | Lista las fechas disponibles y qué datos tiene cada una |
| `uv run --project backend sinsim run --fecha YYYY-MM-DD --periodo N [--tipo ac\|dc] [--exportar DIR] [--json]` | Construye el caso, imprime el reporte de calidad y corre el flujo |
| `uv run --project backend sinsim scrape --fecha YYYY-MM-DD [--out data/paratec/]` | Descarga PARATEC, `dDEC` y `PRON_BARRA` de esa fecha y crea un snapshot nuevo. Se admite hasta mañana (XM publica el despacho la víspera). La interfaz hace lo mismo desde el campo de fecha |
| `make dev` | Levanta la API (`127.0.0.1:8000`) y la interfaz (`127.0.0.1:5173`) |
| `sinsim serve [--puerto N] [--no-abrir]` | Levanta la API y la interfaz construida en `127.0.0.1` y abre el navegador |
| `make package` | Construye la interfaz y el paquete instalable en `backend/dist/` |
| `make test` | Corre todas las pruebas |

Códigos de salida del CLI: `0` éxito (incluye un flujo que no convergió), `1` error general,
`2` uso incorrecto, `3` error de red, `4` validación fallida o cambio de estructura en la fuente.

## Cómo se construye el caso

1. Se carga el snapshot inmutable de `data/paratec/<fecha>/` y se verifican sus checksums.
2. Se modela el STN + STR (≥ 57,5 kV). Lo que está por debajo se traslada a la barra de la
   frontera STR/SDL y queda registrado.
3. Los recursos del despacho y los nodos del pronóstico se concilian con PARATEC mediante las
   tablas versionadas de `data/equivalencias/`. Lo que no tiene equivalencia se reporta como
   **no ubicado**; nunca se descarta en silencio.
4. La demanda activa de cada barra es `Ener.Act. + Perd.PSTR`; la reactiva, `Ener.Reac`.
5. La diferencia entre generación y demanda la absorbe una **referencia distribuida** entre los
   generadores despachados, en proporción a su potencia programada.
6. Si el flujo no converge, el resultado es `no_convergio` con diagnóstico; nunca se presentan
   tensiones o flujos como válidos.

Los supuestos del modelo (consigna de tensión 1,0 pu, taps en posición neutra, `i0 = 0`,
SVC/STATCOM como fuentes de reactiva) se muestran en cada caso y en cada exportación. Los
límites de tensión y cargabilidad están en `config/defaults.toml`, cada uno con su fuente.

## Estructura

```
backend/   API FastAPI, CLI Typer y motor (src/sinsim)
frontend/  Interfaz React + TypeScript
data/      Snapshots inmutables (paratec/<fecha>/) y tablas de equivalencias
config/    Límites y supuestos con su fuente
cases/     Casos de estudio (JSON de pandapower)
specs/     Especificaciones (Spec Kit)
```

La fuente de verdad del proyecto es `.specify/memory/constitution.md`.

## Cómo colaborar

El modelo se afina con las tablas de equivalencias de `data/equivalencias/`, que relacionan los
recursos del despacho (`dDEC`) y los nodos del pronóstico de demanda (`PRON_BARRA`) con las
plantas, subestaciones y niveles de tensión de PARATEC. Lo que no tiene fila queda "sin ubicar"
en el reporte de calidad; nunca se completa en silencio. Para aportar:

1. Corre un caso y revisa en el reporte de calidad los recursos y nodos sin ubicar (el aviso
   "Cómo colaborar" de la interfaz permite copiar la lista).
2. Confirma el elemento real en [PARATEC](https://paratec.xm.com.co).
3. Edita la tabla que corresponda (`recursos_despacho.csv`, `nodos_demanda.csv`,
   `subestaciones_alias.csv` o, para una subestación sin coordenadas en PARATEC,
   `coordenadas_subestaciones.csv`): fechas `AAAA-MM-DD`, una sola fila vigente por clave y fecha,
   fuente en `note` y sin la marca "NO CURADA". Deja sin fila lo que no puedas confirmar; nunca
   se inventan parámetros eléctricos.
4. Verifica con `make test` y `make demo`: la cobertura debe subir y no debe aparecer nada nuevo
   sin ubicar.
5. Abre un pull request con el motivo y la fuente de cada fila.
