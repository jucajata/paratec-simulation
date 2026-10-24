# Investigación: análisis de contingencias N-1

**Feature**: 003-contingencias-n1 | **Fecha**: 2026-10-24

Mediciones sobre `cases/demo/net.json` (2026-10-20, periodo 19), en el portátil del usuario
(12 núcleos), con la configuración de solver del proyecto (Newton-Raphson, referencia distribuida,
límites de reactiva). pandapower 3.5.6 sin numba. Script desechable en el scratchpad de la sesión.

## R1. Costo de una contingencia

- **Decisión**: cada contingencia restaura el estado base (columnas `in_service` de barras,
  líneas, transformadores, generadores y cargas, y `res_bus` del flujo base), saca el activo,
  detecta islas y corre `runpp(init="results")`.
- **Medición**: 207 ms por contingencia en promedio (7 ms de islas, 200 ms de flujo). En
  secuencial, las 1.261 contingencias tardan unos 4,4 minutos.
- **Alternativas**: `copy.deepcopy(net)` por contingencia. Se descarta porque copia toda la red
  para cambiar una columna. `init="dc"` en todas: más lento y no aprovecha la solución base.

## R2. Paralelismo

- **Decisión**: `concurrent.futures.ProcessPoolExecutor` con `os.cpu_count() - 1` procesos (mínimo
  1). Cada proceso carga la red una vez (inicializador), corre el flujo base y luego atiende lotes
  de contingencias. Biblioteca estándar: no hay dependencias nuevas (constitución II).
- **Medición**: 11 procesos, 1.260 contingencias, **76 s** de principio a fin, incluido el
  arranque de los procesos. Cumple SC-014 (menos de 3 minutos).
- **Alternativas**: hilos. Se descartan por el GIL: el flujo es Python y numpy mezclados. Numba:
  acelera el solver, pero es una dependencia pesada que también cambia el paquete de PyPI; no hace
  falta para cumplir SC-014. Dask o Ray: dependencias nuevas sin necesidad.

## R3. Determinismo

- **Decisión**: cada contingencia parte del mismo estado base, sin importar qué proceso la corre
  ni en qué orden. Los resultados se reúnen y se ordenan al final. Con eso la interfaz y el CLI
  producen las mismas filas en el mismo orden (SC-018).
- **Riesgo descartado**: con `init="results"` sin restaurar `res_bus`, cada flujo partiría de la
  contingencia anterior y el resultado dependería del reparto entre procesos.

## R4. No convergencia y reintento

- **Decisión**: si `runpp(init="results")` lanza `LoadflowNotConverged`, se reintenta una vez con
  `init="dc"`. Si tampoco converge, la contingencia va a «Sin solución» con el diagnóstico de
  `services/diagnostics.diagnose`.
- **Medición**: 8 de 1.260 contingencias no convergen en el caso de ejemplo (sin el reintento).

## R5. Islas

- **Decisión**: reutilizar `services/islands.detect_and_isolate` (FR-016) en cada contingencia de
  línea o transformador: energiza la componente con la referencia de ángulo, saca de servicio las
  demás y reporta la demanda perdida. La salida de un generador no cambia la topología, así que no
  se recalculan islas.
- **Medición**: 123 de 1.260 contingencias aíslan barras en el caso de ejemplo; es el volumen
  esperado del bloque «Aíslan demanda».
- **Por qué no `check_connectivity` solo**: research R5 de la spec 001 verificó que una isla sin
  referencia queda con NaN y `converged=True`.

## R6. Salida del generador de referencia de ángulo

- **Decisión**: si la contingencia saca el generador con `slack=True`, la referencia pasa al
  generador elegido por el criterio de reserva de `services/build_case._angle_ref`: la barra STN
  (≥ 220 kV) con mayor P programada entre los generadores que quedan. Esa función se vuelve
  pública (`choose_angle_ref`) para reutilizarla sin duplicar el criterio. El cambio se registra en
  la fila de la contingencia.
- **Por qué no afecta los resultados**: con `distributed_slack=True` el desbalance se reparte por
  `slack_weight`; la barra de referencia solo fija el ángulo cero.

## R7. Tensión en pu

- **Decisión**: la tensión de cada barra se expresa en pu del nominal declarado por PARATEC
  (`nominal_kv`), igual que `run_flow._result`. Esa conversión se extrae a una función
  `bus_vm_nominal(net)` que usan los dos, para que el N-1 y el flujo base comparen lo mismo.

## R8. Compensadores

- **Decisión**: un generador cuyo nombre empieza por `svc:` o `statcom:` es un compensador (así lo
  nombra `build_case`). En el caso de ejemplo son 3. Su contingencia se etiqueta «compensador»
  (S25).

## R9. Base de la comparación

- **Decisión**: los valores base (cargabilidad por rama y tensión por barra) se toman de la
  ejecución guardada (`Run.result`) que el usuario tiene en pantalla, no de un flujo recalculado.
  Así el análisis compara contra exactamente lo que el usuario vio.
- **Comprobación**: el flujo base que corre cada proceso debe coincidir con la ejecución guardada;
  una prueba de integración lo verifica (tolerancia 1e-6 pu y 1e-4 %).
