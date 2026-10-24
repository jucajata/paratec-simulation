# Contrato del comando `sinsim n1` (HU-8, FR-059)

Se suma a [specs/001/contracts/cli.md](../../001-flujo-potencia-despacho/contracts/cli.md); los
códigos de salida son los de ese contrato (constitución V).

## `sinsim n1 --fecha YYYY-MM-DD --periodo N [--fecha-despacho F] [--salida CARPETA] [--json]`

| Opción | Por defecto | Descripción |
|---|---|---|
| `--fecha` | obligatoria | Fecha del snapshot de PARATEC. |
| `--periodo` | obligatoria | Periodo horario 1–24. |
| `--fecha-despacho` | `--fecha` | Snapshot del despacho y la demanda, como en `sinsim run`. |
| `--salida` | `./n1-<fecha>-p<NN>/` | Carpeta donde escribir los archivos. Se crea si no existe. |
| `--json` | no | Imprime el `N1Analysis` completo en JSON por stdout. |

**Comportamiento**

1. Construye o reutiliza el caso con las mismas reglas de `sinsim run` y corre el flujo AC base.
2. Si el flujo base no converge: no corre el análisis, imprime el diagnóstico y sale con código 4
   (`N1_BASE_INVALID`).
3. Corre el análisis y muestra el avance en stderr: `N-1: 640/1261 contingencias`.
4. Escribe en `--salida` los archivos de [export-n1.md](./export-n1.md). Si la carpeta ya tiene
   esos archivos, los reemplaza.
5. Sin `--json`, imprime el resumen (FR-057) y las 10 primeras filas de cada listado.

**Códigos de salida**

| Código | Cuándo |
|---|---|
| 0 | Análisis terminado; incluye contingencias sin solución, que son un resultado. |
| 1 | Error general: snapshot alterado, falta el punto de operación. |
| 2 | Uso incorrecto: fecha mal formada, periodo fuera de 1–24. |
| 4 | El flujo base no converge (`N1_BASE_INVALID`). |
