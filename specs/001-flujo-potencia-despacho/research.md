# Investigación (Fase 0): Flujo de potencia del SIN con PARATEC, despacho y demanda por barra

**Feature**: [spec.md](./spec.md) · **Fecha**: 2026-10-19

Hallazgos verificados en vivo el 2026-10-19 contra las fuentes (APIs, archivos y normas). Lo
marcado **NO VERIFICADO** se trata como supuesto y queda como riesgo en [plan.md](./plan.md).

---

## R1. Acceso a PARATEC

- **Decisión**: leer la API JSON pública del backend de PARATEC
  (`https://paratecbackend.xm.com.co/<servicio>/api/...`) con httpx. No se usa Playwright.
- **Justificación**: todos los GET probados respondieron 200 sin autenticación, con la forma
  `{"header": {...}, "data": [...]}` y sin paginación. La UI es una SPA Angular que consume
  esos mismos endpoints. Los `getExcelFile` no son descargas directas: piden un POST con las
  filas ya filtradas.
- **Endpoints usados** (los conteos son de la fecha de verificación):

  | Entidad | Endpoint | Registros |
  |---|---|---|
  | Líneas | `reportetransmision/api/Line/getAll` | 929 |
  | Subestaciones | `reportetransmision/api/Substation/SubstationInfo` | 509 |
  | Reactores | `reportetransmision/api/Reactor/getAll` | 81 |
  | SVC/STATCOM | `reportetransmision/api/StatcomSvc/getAll` | 26 |
  | Transformadores | `reportetransformacion/api/PowerTransformer/PowerTransformerInfo` | 1075 |
  | Unidades hidráulicas | `reportegeneracion/api/HydraulicUnit/HydraulicUnitInfo` | 284 |
  | Unidades térmicas | `reportegeneracion/api/ThermalUnit/ThermalUnitInfo` | 130 |
  | Unidades solares equivalentes | `reportegeneracion/api/SolarEquivalentUnit/getAll` | 375 |
  | Plantas eólicas | `reportegeneracion/api/WindPlant/WindPlantInfo` | — |
  | Condensadores | `reportegeneracion/api/Capacitor/getAll` | 63 |
  | Extremos de líneas (respaldo) | `mapas/api/TransmissionMap/getLines` (`sub1`/`sub2`) | 807 |

- **Alternativas descartadas**:
  - *Playwright sobre la UI*: innecesario, porque la API es directa.
  - *Exportes Excel*: requieren POST con los datos ya en mano.
  - *`BarSections/getAll`*: devolvió exactamente 1000 registros, posible tope del servidor
    (NO VERIFICADO). No se depende de él (ver R6).

## R2. Despacho programado

- **Decisión**: usar el archivo diario `dDEC<MMDD>.txt` de XM (programa de generación del
  despacho coordinado), descargado por HTTPS desde la API de archivos del portal de XM:
  - **Listado**:
    `GET https://api-portalxm.xm.com.co/administracion-archivos/ficheros?ruta=/M:/InformacionAgentes/Usuarios/Publico/DESPACHO/<AAAA-MM>&contenedor=storageportalxm&...`
  - **Descarga**:
    `GET https://api-portalxm.xm.com.co/administracion-archivos/ficheros/descarga-archivo?ruta=M:/InformacionAgentes/Usuarios/Publico/DESPACHO/<AAAA-MM>/dDEC<MMDD>.txt&nombreBlobContainer=storageportalxm`
- **Formato verificado**:
  - Cada fila es `"<NOMBRE RECURSO>",v1,...,v24`, con 24 valores horarios en **MWh por
    periodo**. Como el periodo dura 1 h, el valor equivale numéricamente a MW medios.
  - Unas 626 filas, nombradas por recurso o planta (no por código SIC). Algunas son de nivel
    unidad (p. ej. `"ZIPAEMG 5"`) y otras son enlaces internacionales (`"ECUADOR138_1"`,
    `"ECUADOR230_1"`).
  - La última fila es `"Total"` y se usa como suma de control.
- **Norma de formato**: *Estándar de Información del Despacho Económico*, XM-CND-2014-045,
  edición 2025, publicada como XM-CND-2025-055. Esa versión se registra en el manifiesto (R-04).
  Separador "," o ";".
- **Versiones del mismo día** (decisión del usuario D-3, 2026-10-20): cuando existen
  `dDEC<MMDD>.txt` (equivale a V0) y `dDEC<MMDD>_V<n>.txt`, prevalece la `_V<n>` de mayor `n`.
  El scraper guarda todas las versiones en `raw/` y el manifiesto registra cuál se usó
  (`dispatch_version`). Si se usó una versión distinta de V0, el caso muestra la advertencia
  `DISPATCH_REVISED`.
- **Alternativas descartadas**:
  - *FTPS (`xmftps.xm.com.co:210`)*: requiere credenciales; el login anónimo da `530 Access
    denied`. El supuesto A-02 vale solo para la vía HTTPS.
  - *API SINERGOX `GeneProgDesp`*: está por recurso pero en kWh y es otra fuente distinta del
    archivo oficial; no aporta nada que el `dDEC` no tenga.
  - *`rDEC` (redespacho)*: fuera de alcance por NG-06.
- **Riesgo**: la API de archivos del portal no está documentada y puede cambiar. Si eso pasa,
  el scraper sale con código 4 (`PARATEC_SCHEMA_CHANGED` o equivalente); no hay respaldo
  silencioso.

## R3. Pronóstico oficial de demanda por barra

- **Decisión**: usar `PRON_BARRA<MMDD>` (carpeta
  `/M:/InformacionAgentes/Usuarios/Publico/DEMANDAS/Pronostico Oficial/<AAAA-MM>`), descargado
  por la misma API HTTPS de R2.
- **Formato**:
  - Columnas: `UCP, NODO, NIVEL TENSIÓN (kV), CONCEPTO, HORA 01..HORA 24`.
  - El archivo real tiene 1656 filas: 552 nodos × 3 conceptos, en 44 UCP.
  - Etiquetas observadas: `Ener.Act.`, `Ener.Reac` y `Perd.PSTR` (el estándar las escribe con
    punto final). El parser acepta ambas variantes.
- **Unidades según el estándar XM-CND-2025-055**:
  - `Ener.Act.`: MWh por periodo → MW medios.
  - `Ener.Reac.`: el estándar dice "MVAr" → Mvar.
  - `Perd.PSTR.`: "pérdidas de potencia por referir la carga a un nivel de tensión", en MWh →
    MW. En el archivo es una fracción constante de `Ener.Act.` por nodo (0 %, 1,52 %, 3,09 %,
    5,26 % o 17,65 %). Esto respalda la decisión de la clarificación 4: sumarla a la demanda
    activa.
- **Revisiones**: el archivo de la semana se crea el viernes anterior y se modifica en D-1
  hacia las 08:00. El manifiesto guarda `fechaModificacion` de la fuente (FR-003).
- **Brecha observada** (hora 1, 20-oct): ΣEner.Act. + ΣPerd.PSTR = 9089,8 MW frente a
  `dDEM` Total = 9307,9 MW. La diferencia, de unos 218 MW, no tiene explicación (NO
  VERIFICADO). La absorbe la referencia distribuida y se ve en el balance (FR-024); queda como
  riesgo de SC-004.

## R4. Términos de uso de XM y redistribución (resuelto por el usuario)

- **Hallazgo**: PARATEC no publica una licencia propia. Rigen los *Términos legales del sitio
  web* de XM (https://www.xm.com.co/legales/terminos-legales-del-sitio-web):
  - **Art. 6**: el usuario se abstiene de "Reproducir o copiar, distribuir, permitir el acceso
    del público… a menos que se cuente con la autorización del titular… o ello resulte
    legalmente permitido".
  - **Art. 19**: XM no concede licencia sobre su propiedad intelectual.
- **Consecuencia**: FR-001 (snapshot incluido en el repo) y el principio I de reproducibilidad
  chocan con III.10 ("respetar los términos de uso de XM") mientras no haya autorización de XM
  o una base legal confirmada (p. ej. la Ley 1712 de 2014, cuya aplicabilidad está NO
  VERIFICADA).
- **Decisión del usuario (D-1, 2026-10-20)**: se publican los datos de XM en el repositorio,
  porque son información pública que se usa y difunde ampliamente. Toda redistribución lleva
  la atribución "Información proporcionada por XM S.A. E.S.P. – PARATEC y archivos públicos
  de despacho". La atribución va en:
  - el manifiesto de cada snapshot,
  - `metadatos.json` de cada exportación,
  - el pie de la interfaz,
  - el README (R-12).

  El usuario asume el riesgo frente a los términos del art. 6. La regla quedó en la
  constitución 1.1.0 (III.10).

## R5. Motor de cálculo: pandapower

- **Decisión**: fijar **pandapower 3.5.6** (2026-10-07; `requires_python >=3.10`; probado en
  Python 3.12).
- **Referencia distribuida (FR-015)**:
  - Se activa con `runpp(net, distributed_slack=True)`. El reparto es
    `P_i = P_set,i − desbalance·w_i`, con pesos normalizados.
  - `slack_weight` solo vale en `gen`, `ext_grid` y `xward`. En sgen o load se ignora con un
    aviso, así que todo generador despachado se modela como `gen`.
  - La referencia de ángulo es un `gen` con `slack=True`; no se usa `ext_grid`.
  - Solo funciona con Newton-Raphson (o HELM). El solver queda fijo en `nr`.
- **Islas (FR-016)**:
  - `topology.create_nxgraph` + `networkx.connected_components` dan las islas.
  - El SIN real es un sistema interconectado sin islas (D-5, usuario). Por eso, una isla en
    el modelo solo puede venir de los datos: elementos excluidos por parámetros faltantes,
    extremos de línea sin resolver o el corte de alcance en 57,5 kV. Se trata como **problema
    de calidad de datos**.
  - Solo se resuelve la componente que contiene la barra de referencia de ángulo. Las demás
    se sacan de servicio, y el reporte las muestra como hallazgo, con los MW de generación y
    demanda que quedaron fuera.
  - **Riesgo comprobado**: con `check_connectivity=True`, una isla sin referencia queda con
    NaN, P=0 en sus gen y `converged=True`. Por eso la detección y la salida de servicio se
    hacen **antes** de correr el flujo.
- **No convergencia (FR-022)**: se captura `LoadflowNotConverged`. Del estado interno se
  toman las iteraciones (`net._ppc["iterations"]`) y se calcula el desbalance
  `mis = V·conj(Ybus·V) − Sbus`. Las peores barras salen de `argsort(|mis|)`, mapeadas con
  `net._pd2ppc_lookups["bus"]`. Como usa estado privado, la versión de pandapower queda fija
  y hay una prueba de contrato del diagnóstico.
- **Flujo DC (FR-021)**: `rundcpp`, con pérdidas = 0, Q = 0 y |V| = 1 pu. La UI y la
  exportación lo etiquetan como "aproximación DC". `rundcpp` usa
  `check_connectivity=False` por defecto, así que el manejo de islas previo es obligatorio.
- **Hash del caso (FR-023)**: `pp.to_json` es determinista, pero incluye `res_*`,
  `converged` y `version`. El hash es SHA-256 de un **JSON canónico de las entradas del
  caso**, no del JSON de pandapower.
- **Red de referencia (SC-005)**: `pandapower.networks.case9`, `case14` y `case30` se
  desvían menos de 1e-11 pu de PYPOWER `runpf` (PF_TOL=1e-10). Se usan como regresión con
  tolerancia 1e-6 pu. `case118` de `pn` está corregido en dos barras y no sirve tal cual.
- **p3s** (`parallel-pandapower-solver` 1.2.1): existe, pero no se usa (NG-14).

## R6. Construcción de la topología desde PARATEC

- **Barras**: una barra por par (subestación, tensión nominal kV), tomando `voltageLevel[]`
  de `SubstationInfo`. No se modelan secciones de barra ni configuración de interruptores.
  - **Justificación**: el nivel de detalle de PARATEC (y el tope de 1000 en `BarSections`)
    no permite una topología de interruptores confiable. Un nodo por (subestación, kV) es la
    práctica estándar en estudios de planeamiento.
- **Líneas**:
  - Extremos: se parsea `subStation` ("A - B"); si no se puede, se usa `sub1`/`sub2` del mapa.
    Si no se resuelven, la línea se excluye y se reporta (FR-013).
  - Parámetros por tramo (`typeLines[]`): R1 y X1 en Ω/km, B1 en µS/km, longitud en km. Se
    agregan en serie:
    - `R = Σ rᵢ·lᵢ`
    - `r_ohm_per_km = R / Σlᵢ` (igual para X)
    - `c_nf_per_km = (Σ bᵢ·lᵢ / Σlᵢ) · 1e3 / (2π·60)`
  - Límite (D-4, usuario): la corriente nominal es el 100 %, así que
    `max_i_ka = ratedCurrent [A] / 1000`. `thermalLimit` y `emergencyLimit` se conservan en
    `normalized/` pero no se usan en esta feature.
- **Transformadores**:
  - Bidevanado → `trafo`; tridevanado → `trafo3w`. `nomVoltage` [kV] y `nomCapacity` [MVA]
    por devanado.
  - **Impedancias** (usuario, 2026-10-20): las impedancias % de PARATEC se toman tal como
    vienen, en la convención de pandapower, sin convertir:
    - `vk_percent = impedanceHighLow`;
    - en `trafo3w`: `vk_hv_percent = impedanceHighMedium`, `vk_mv_percent = impedanceMediumLow`,
      `vk_lv_percent = impedanceHighLow`.

    En `trafo` la base es `sn_mva`; en `trafo3w`, la menor capacidad de los dos devanados del
    par, según `pandapower/build_branch.py`.
  - **Pérdidas de cobre → `vkr`**: es la única conversión inevitable, porque PARATEC da kW y
    pandapower pide %. Se usa la misma base que pandapower:
    - `vkr_percent = P_cu[kW] / (sn_mva·1000) · 100`;
    - en `trafo3w`, la base es `min(S_a, S_b)` del par.

    Fórmula en el docstring y prueba de valor conocido (III.1).
  - `pfe_kw = ironLosses`.
  - `i0_percent` no existe en PARATEC → 0 % (D-2, ver R8).
  - **Taps**: PARATEC trae la geometría completa del cambiador:
    - `lowStep`/`highStep`: rango de posiciones.
    - `lowStepU`/`highStepU`: tensión en cada extremo, en kV.
    - `step`: paso en %.
    - `normalStep`: posición neutra.
    - `ltcFlag`: bajo carga (755 transformadores) o en vacío (292).

    Que `normalStep` es la posición neutra (relación nominal) se verificó con los datos del
    2026-10-19. Por ejemplo, en ALFEREZ (EEB) 230 kV: paso 1 = 264,5 kV, paso 1,25 % = 2,875 kV,
    y 230 kV cae en 1 + (264,5 − 230)/2,875 = 13 = `normalStep`. Lo mismo vale para AGUACHICA,
    AGUACLARA y AGUAZUL.
    - **Orientación**: un paso mayor da una tensión menor. El adaptador fija el sentido de
      `tap_step_percent` según eso y lo prueba con valores conocidos (III.1).
    - **Mapeo a pandapower**: `tap_min = lowStep`, `tap_max = highStep`,
      `tap_neutral = tap_pos = normalStep`, `tap_step_percent = step`.
    - **Lo que PARATEC no trae** es la posición *operativa* de cada momento. El tap queda en
      `normalStep` (relación nominal) como supuesto visible del caso (D-2). No hace falta otra
      fuente para construir el modelo.
    - Los transformadores con `step` o `lowStep` en "-" (unos 15) se modelan sin cambiador y se
      reportan.
  - Muchos campos llegan como "-" o "N/A" y se tratan como faltantes.
- **Generadores**:
  - `connectionPoint` es texto libre (p. ej. "GUATAPE 220"); se parsea a (subestación, kV).
  - `minQ` y `maxQ` (en MVAr, magnitudes positivas, "a Pmáx") se usan como límites:
    `min_q_mvar = −minQ`, `max_q_mvar = maxQ`.
  - `ratedNetMaxP` es la capacidad.
- **Compensación fija**: reactores y condensadores como `shunt` (MVAr nominal, en servicio).
- **SVC y STATCOM** (D-6, usuario: "generadores o cargas de reactiva"): se modelan como `gen`
  con `p_mw = 0`, `slack_weight = 0`, `vm_pu` = consigna por defecto (D-2),
  `min_q_mvar = −inductiveRating` y `max_q_mvar = +capacitiveRating`, con `enforce_q_lims`.
  Así regulan la tensión de su barra dentro de su capacidad en MVAr. Verificado en pandapower
  3.5.6 (case14): converge con `distributed_slack=True` y `enforce_q_lims=True`.
  - *Descartado `create_svc`*: pide `x_l_ohm`, `x_cvar_ohm` y el ángulo de tiristores, que
    PARATEC no publica; con parámetros de prueba no convergió con la referencia distribuida.
  - *Descartado `create_ssc`*: convergió, pero con una tensión interna sin sentido físico
    (≈ 2000 pu) y también pide reactancias internas que no están en PARATEC.
  - Si en una barra ya hay un generador PV, el compensador usa la misma consigna, para evitar
    dos consignas distintas en la misma barra (`MultipleVoltageControllingElementsPerBus`).
- **Recurso con varias unidades**: se crea un `gen` por recurso y barra de conexión, con la
  suma de las capacidades. Si las unidades de un recurso están en barras distintas, la P
  programada se reparte en proporción a `ratedNetMaxP`, y ese reparto se registra como
  supuesto del caso.
- **Alcance (FR-017)**: barras ≥ 57,5 kV. Lo que queda por debajo se excluye, y su generación
  y demanda se trasladan a la barra del STR de la frontera STR/SDL (FR-014, FR-019).

## R7. Tablas de equivalencias (FR-011)

- **Hallazgo**: no existe una tabla oficial pública que relacione:
  - nombres de recurso del `dDEC` con unidades o plantas de PARATEC, ni
  - nodos de `PRON_BARRA` (p. ej. `DONCELL1`, `ANCONSU1`, `GUADALU4`) con subestaciones de
    PARATEC (`DONCELLO`, `ANCON SUR (EPM)`, `GUADALUPE IV`).

  Con un cruce heurístico por nombre normalizado coinciden 157 de 164 plantas hidráulicas.
- **Decisión**: dos tablas CSV versionadas en `data/equivalencias/`, con columnas de vigencia:
  - `recursos_despacho.csv`: recurso → unidades o planta PARATEC, o enlace internacional.
  - `nodos_demanda.csv`: nodo → (subestación, kV) PARATEC.

  En tiempo de ejecución solo se usa la tabla; **nunca** hay coincidencia aproximada
  automática (FR-011, FR-012). La construcción inicial es una tarea de curación de datos: el
  heurístico solo propone y una persona revisa. Ese heurístico no forma parte del producto.
- **Alternativa descartada**: coincidencia aproximada en tiempo de ejecución. Viola "nunca en
  silencio" (constitución III.5) y haría el resultado no reproducible.

## R8. Datos faltantes e imputación (FR-013)

- **Decisión**: la regla por defecto es **excluir** el elemento. La imputación solo aplica a
  los parámetros listados en la configuración, con el método "mediana de elementos del mismo
  tipo y nivel de tensión en el mismo snapshot". Cada imputación lleva `imputado=true`,
  `metodo_imputacion` y el parámetro afectado, y aparece en el reporte de calidad.
- **`i0_percent` de transformadores**: PARATEC no lo trae en ningún elemento. Se fija en 0
  (se desprecia la corriente de magnetización) por decisión del usuario (D-2, 2026-10-20). Se
  declara como supuesto del caso, no como imputación por elemento.

## R9. Límites operativos por defecto (FR-031, constitución III.9)

| Límite | Valor por defecto | Fuente |
|---|---|---|
| Tensión 500 kV | 0,90–1,05 pu | CREG 025/1995, Código de Operación, num. 5.1 |
| Tensión 110/115/220/230 kV | 0,90–1,10 pu | CREG 025/1995, Código de Operación, num. 5.1 |
| Tensión STR (57,5–<220 kV) | 0,90–1,10 pu | CREG 153/2019, art. 1 (Reglamento de Distribución, num. 6.2.1.1) |
| Cargabilidad de líneas y transformadores | 100 % | CREG 025/1995, Código de Planeamiento, num. 5.2 ("No se permiten sobrecargas") |

Para 57,5 y 66 kV, aplicar 0,90–1,10 pu es una inferencia del art. 1 de la CREG 153/2019 y se
anota así en la configuración.

## R10. Consigna de tensión de los generadores (A-04, FR-018)

- **Hallazgo**: no existe un valor por defecto regulatorio. La CREG 135/2013 (num. 5.7) dice
  que los voltajes objetivo "se determinarán según los resultados de las metodologías del
  Planeamiento Operativo Eléctrico", es decir, salen de un OPF del CND que no es público.
- **Decisión del usuario (D-2, 2026-10-20)**: la consigna por defecto es 1,0 pu para todos
  los generadores y compensadores. En `config/defaults.toml` y en el caso aparece con la
  fuente "supuesto del proyecto aprobado por el usuario el 2026-10-20 (sin norma aplicable,
  CREG 135/2013 num. 5.7)". Se puede cambiar por generador.

## R11. Periodos y hora

- 24 periodos horarios en todos los archivos. Que el periodo 1 sea 00:00–01:00 se infiere del
  dataset SiMEM ff027b (NO VERIFICADO como norma).
- Colombia usa UTC−5 fijo, sin horario de verano, así que no existen días de 23 o 25
  periodos.

## R12. Dependencias (constitución II: cada una justificada)

| Dependencia | Para qué | ¿Está en la tabla de stack? |
|---|---|---|
| pandapower==3.5.6 | Motor de cálculo | Sí |
| networkx | Detección de islas | Ya viene con pandapower |
| pandas / numpy | Tablas de pandapower | Ya vienen con pandapower |
| pyarrow | Escritura y lectura de Parquet | Implícita en "Parquet" |
| duckdb | Consultas sobre snapshots | Sí |
| httpx | Scraper (PARATEC y portal XM) | Sí |
| typer | CLI `sinsim` | Sí |
| fastapi, pydantic v2, uvicorn | API local | Sí |
| pytest, pytest-cov | Pruebas y medición de la cobertura del 85 % | pytest sí; pytest-cov se justifica por IV |
| ruff, mypy, pre-commit | Calidad | Sí |
| react, typescript, vite, @tanstack/react-query | Frontend (HU-4) | Sí |
| cytoscape | Vista de topología (FR-033) | Sí |
| vitest, @playwright/test | Pruebas del frontend y e2e | Sí |

- **No se agregan**: Playwright en el scraper (innecesario), Plotly (ninguna historia de esta
  feature pide gráficas), una librería de tablas en el frontend (los filtros son simples),
  respx (se usa `httpx.MockTransport`, que ya viene en httpx) ni p3s.
