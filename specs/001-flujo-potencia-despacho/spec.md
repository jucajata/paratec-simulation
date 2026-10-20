# Especificación de feature: Flujo de potencia del SIN con parámetros PARATEC y despacho programado

**Rama de feature**: `001-flujo-potencia-despacho`

**Creada**: 2026-10-19

**Estado**: Borrador (pendiente `/speckit-clarify`)

**Entrada**: Descripción del usuario: "Correr flujo de potencia sobre el SIN usando los parámetros
técnicos de PARATEC y el despacho programado publicado por XM, con datos incluidos en el
repositorio y un comando para actualizarlos."

> Esta spec describe **qué** y **por qué**. El **cómo** (librerías, endpoints, estructura de
> código) va en `plan.md` y debe cumplir `.specify/memory/constitution.md` v1.1.0.

## Intención

### Problema

Un ingeniero que quiere estudiar el comportamiento en estado estacionario del SIN colombiano
para una hora concreta no tiene una herramienta abierta y reproducible que combine los
parámetros técnicos oficiales de los equipos con la generación programada. Hoy tiene que armar
el modelo a mano, conciliar nombres de plantas entre fuentes y adivinar supuestos que nadie
documenta.

### Propósito de la feature

Permitir que cualquier persona que clone el repositorio ejecute un **flujo de potencia para una
fecha y un periodo horario**. Ese flujo usa:

- los parámetros técnicos de PARATEC del snapshot elegido, y
- la generación por recurso del **despacho programado** de XM para ese día y periodo.

Los resultados son trazables y no esconden supuestos.

### Propósito de cada funcionalidad

| Funcionalidad | Para qué existe |
|---|---|
| Snapshot de datos incluido en el repositorio | Que el proyecto funcione sin internet y que los resultados sean reproducibles |
| Comando de actualización de datos | Que el usuario pueda generar snapshots de otras fechas sin depender del mantenedor |
| Conciliación despacho ↔ PARATEC | Que cada MW programado llegue a un generador del modelo, o quede reportado como no ubicado |
| Ejecución del flujo de potencia | Obtener tensiones, flujos, cargabilidad y pérdidas para el punto de operación elegido |
| Reporte de calidad del caso | Que el usuario sepa qué tan confiable es el resultado antes de interpretarlo |
| Visualización y exportación | Que el resultado pueda leerse y reutilizarse fuera de la herramienta |

## Clarifications

### Session 2026-10-19

- Q: ¿Qué niveles de tensión del SIN debe incluir la red que se construye a partir de PARATEC?
  → A: STN + STR (≥ 57,5 kV). Primero se había respondido "solo STN"; el usuario lo cambió
  durante la misma sesión.
- Q: ¿Qué pasa con los generadores del despacho que, según PARATEC, se conectan por debajo del
  nivel modelado? → A: Su potencia se traslada como inyección a la barra modelada de la
  frontera a la que pertenecen, y cada traslado queda en el reporte de calidad. Al cambiar el
  alcance a STN + STR, la frontera pasa a ser STR/SDL (< 57,5 kV).
- Q: ¿De dónde sale la demanda del periodo y cómo se reparte entre las barras? → A: De la
  demanda por barra del *Pronóstico oficial de demanda definitivo* publicado por XM
  (https://www.xm.com.co/generaci%C3%B3n/informes-despacho/pronostico-oficial-de-demanda-definitivo),
  archivo diario `PRON_BARRA<MMDD>`, que trae por barra la energía activa y reactiva de los 24
  periodos.
- Q: ¿Qué se hace con la fila `Perd.PSTR` (pérdidas del STR asignadas a cada barra) del
  pronóstico de demanda? → A: Se suma a la demanda activa de la barra (Ener.Act. + Perd.PSTR).
  Son pérdidas asignadas a la demanda, distintas de las pérdidas de los activos (líneas y
  transformadores) que calcula el flujo, así que no se cuentan dos veces.
- Q: ¿Cómo se elige el generador o los generadores que absorben la diferencia entre generación
  y demanda (referencia o slack)? → A: Referencia distribuida entre los generadores despachados,
  en proporción a su potencia programada; una barra fija configurada sirve como referencia de
  ángulo.

## Escenarios de usuario y pruebas *(obligatorio)*

### Historia de usuario 1 - Correr un flujo de potencia con datos incluidos (Prioridad: P1, MVP)

Como ingeniero que acaba de clonar el repositorio, quiero elegir una fecha disponible y un
periodo horario y correr el flujo de potencia, para obtener el estado del sistema sobre el
despacho programado sin descargar nada.

**Por qué esta prioridad**: es la razón de ser del proyecto. Sin esto, nada más tiene valor.

**Prueba independiente**: con el repositorio recién clonado y sin red, ejecutar el comando de
demo produce un resultado convergido con trazabilidad completa.

**Escenarios de aceptación**:

1. **Given** un repositorio clonado con al menos un snapshot de PARATEC y el despacho programado
   de esa fecha, **When** el usuario selecciona la fecha y el periodo 19 y ejecuta el flujo AC,
   **Then** el sistema muestra la tensión de cada barra, el flujo y la cargabilidad de cada
   línea y transformador, las pérdidas totales y el estado `convergio`.
2. **Given** un resultado convergido, **When** el usuario abre su detalle, **Then** ve la fecha
   del snapshot de PARATEC, la fecha del despacho, el periodo, el tipo de flujo, la versión del
   motor de cálculo y el identificador del caso.
3. **Given** un caso en el que el flujo AC no converge, **When** termina la ejecución, **Then**
   el sistema muestra el estado `no_convergio` con el número de iteraciones, el mayor
   desbalance y las barras donde ocurre, y no muestra tensiones ni flujos como si fueran
   válidos.
4. **Given** una fecha seleccionada sin despacho o sin pronóstico de demanda disponible,
   **When** el usuario intenta ejecutar, **Then** el sistema bloquea la ejecución e indica qué
   dato falta y cómo obtenerlo.

---

### Historia de usuario 2 - Revisar la calidad del caso antes de interpretar (Prioridad: P1)

Como ingeniero, quiero ver qué parte del despacho y de la red quedó correctamente representada,
para saber si puedo confiar en el resultado.

**Por qué esta prioridad**: un flujo con 20 % de la generación sin ubicar es engañoso. La
calidad del caso es parte del resultado, no un extra.

**Prueba independiente**: con un despacho que contiene una planta inexistente en PARATEC, el
reporte la lista como no ubicada y el balance lo refleja.

**Escenarios de aceptación**:

1. **Given** un despacho con recursos cuyo nombre no coincide con ningún generador de PARATEC,
   **When** se construye el caso, **Then** el reporte lista cada recurso no ubicado con su
   generación programada en MW, y el total de MW no ubicados aparece en el resumen.
2. **Given** un elemento de red al que le falta un parámetro obligatorio, **When** se construye
   el caso, **Then** el elemento queda excluido o marcado como `imputado` según la regla
   configurada, y aparece en el reporte con el parámetro faltante y, si se imputó, el método
   usado.
3. **Given** que la red construida tiene islas eléctricas, **When** se construye el caso,
   **Then** el reporte indica cuántas islas hay, cuántas barras tiene cada una y cuáles quedan
   sin referencia.
4. **Given** un caso construido, **When** el usuario ve el resumen, **Then** encuentra el
   balance: generación ubicada, demanda asignada, diferencia y porcentaje de cobertura del
   despacho.

---

### Historia de usuario 3 - Actualizar datos para otra fecha (Prioridad: P2)

Como usuario avanzado, quiero ejecutar un comando que descargue los parámetros de PARATEC y el
despacho programado de una fecha, para estudiar días que no vienen en el repositorio.

**Por qué esta prioridad**: el snapshot incluido cubre el MVP. Esto amplía el alcance sin
bloquear el uso básico.

**Prueba independiente**: con fixtures grabados (sin red real), el comando genera un snapshot
completo y válido en un directorio temporal.

**Escenarios de aceptación**:

1. **Given** acceso a internet, **When** el usuario ejecuta el comando de actualización para una
   fecha, **Then** se crea un snapshot nuevo con su manifiesto (fecha, fuentes, conteo de
   registros y checksums), y la fecha aparece como disponible.
2. **Given** que ya existe un snapshot para esa fecha, **When** el usuario ejecuta el comando,
   **Then** el comando termina sin modificar nada e informa el conflicto.
3. **Given** que la fuente cambió su estructura o devuelve datos que no pasan la validación,
   **When** se ejecuta el comando, **Then** no queda ningún snapshot parcial, el comando sale
   con código de error de validación y el mensaje indica qué entidad falló.
4. **Given** que no hay conexión, **When** se ejecuta el comando, **Then** sale con código de
   error de red y los snapshots existentes quedan intactos.

---

### Historia de usuario 4 - Visualizar y exportar resultados (Prioridad: P3)

Como ingeniero, quiero ver los resultados en una interfaz y exportarlos, para identificar
violaciones y llevar los datos a mis propios análisis.

**Por qué esta prioridad**: el MVP ya entrega los valores calculados; la interfaz y la
exportación mejoran su lectura y reutilización, pero no cambian el resultado.

**Prueba independiente**: con un resultado ya calculado, la interfaz muestra las tablas y la
vista de red, y la exportación produce archivos que coinciden valor a valor con el resultado.

**Escenarios de aceptación**:

1. **Given** un resultado convergido, **When** el usuario abre la vista de resultados, **Then**
   ve tablas filtrables de barras, líneas, transformadores y generadores, y una vista de
   topología coloreada por tensión o cargabilidad.
2. **Given** límites de tensión y cargabilidad configurados, **When** se muestran los
   resultados, **Then** los elementos fuera de límite aparecen resaltados y contados en el
   resumen.
3. **Given** un resultado, **When** el usuario lo exporta, **Then** obtiene un archivo por tipo
   de elemento más un archivo de metadatos de trazabilidad.

---

### Casos borde

- Periodo horario fuera de 1–24 → rechazo con mensaje explícito.
- Recurso del despacho con generación 0 MW en el periodo → se representa como fuera de
  servicio, no como error.
- Planta que cambió de nombre entre la fecha del despacho y la del snapshot de PARATEC → se
  resuelve solo mediante la tabla de equivalencias versionada; si no está, queda como no
  ubicada.
- Generador conectado por debajo de 57,5 kV sin frontera STR/SDL identificable → queda como no
  ubicado, con su potencia programada en el reporte.
- Fechas de snapshot de PARATEC y de despacho distintas → se permite, pero el resultado lo
  advierte de forma visible.
- Snapshot cuyo checksum no coincide con su manifiesto → no se usa y se informa la corrupción.
- Isla en el modelo → el SIN real no tiene islas, así que una isla solo puede venir de datos
  faltantes o del corte de alcance. Solo se energiza la componente que contiene la barra de
  referencia de ángulo; las demás se reportan como hallazgo de calidad de datos, con los MW
  que quedaron fuera, y no bloquean el resto del cálculo.
- Existen varias versiones del despacho del día (`dDEC<MMDD>.txt` y `dDEC<MMDD>_V<n>.txt`) →
  prevalece la de mayor versión; el caso lo advierte y el manifiesto registra cuál se usó.
- Generación ubicada muy distinta de la demanda asignada → se ejecuta, pero la diferencia queda
  explícita en el balance (la absorbe la referencia distribuida entre los generadores
  despachados).

## Requisitos *(obligatorio)*

Tipos de patrón EARS: **[U]** Ubicuo · **[E]** Por evento (Cuando) · **[S]** Por estado
(Mientras) · **[N]** No deseado (Si…, entonces) · **[O]** Opcional (Donde).

### Requisitos funcionales

**Datos y snapshots**

- **FR-001 [U]**: El sistema DEBE incluir en el repositorio al menos un snapshot de parámetros
  PARATEC, el despacho programado y el pronóstico oficial de demanda de la misma fecha.
- **FR-002 [U]**: El sistema DEBE listar las fechas disponibles e indicar, para cada una, si
  tiene parámetros PARATEC, despacho programado y pronóstico de demanda.
- **FR-003 [E]**: Cuando el usuario ejecute el comando de actualización con una fecha, el
  sistema DEBE descargar los parámetros técnicos de PARATEC, el despacho programado y el
  pronóstico oficial de demanda definitivo por barra de esa fecha, y guardarlos como un
  snapshot nuevo con manifiesto. El manifiesto registra, para cada archivo de XM, su fecha de
  última modificación en la fuente, porque XM puede republicar un archivo después de creado.
- **FR-004 [N]**: Si ya existe un snapshot para la fecha solicitada, entonces el sistema DEBE
  abortar sin modificar archivos e informar el conflicto. (Ver "Decisiones pendientes": el
  borrador incluía una opción de forzar que contradice la inmutabilidad de snapshots.)
- **FR-005 [N]**: Si alguna entidad descargada no pasa la validación de esquema, entonces el
  sistema DEBE descartar toda la descarga, no dejar archivos parciales y salir con código de
  error de validación.
- **FR-006 [N]**: Si el checksum de un archivo no coincide con su manifiesto, entonces el
  sistema DEBE negarse a usar ese snapshot e informar cuál archivo está alterado.
- **FR-007 [S]**: Mientras el comando de actualización esté descargando, el sistema DEBE limitar
  la tasa de peticiones a la fuente según el valor configurado.

**Construcción del caso**

- **FR-010 [E]**: Cuando el usuario solicite construir un caso para una fecha y periodo, el
  sistema DEBE crear el modelo de red a partir del snapshot PARATEC y asignar a cada generador
  la potencia activa del despacho programado para ese periodo.
- **FR-011 [U]**: El sistema DEBE conciliar los nombres de recursos del despacho con los
  generadores de PARATEC mediante una tabla de equivalencias versionada en el repositorio.
- **FR-012 [N]**: Si un recurso del despacho no tiene equivalencia, entonces el sistema DEBE
  excluirlo del modelo y registrarlo en el reporte de calidad con su potencia programada.
- **FR-013 [N]**: Si a un elemento de red le falta un parámetro obligatorio, entonces el sistema
  DEBE excluirlo o imputarlo según la regla configurada, marcándolo como `imputado` con el
  método de imputación y registrándolo en el reporte de calidad.
- **FR-014 [U]**: El sistema DEBE asignar a cada barra, para el periodo, una demanda activa
  igual a `Ener.Act.` + `Perd.PSTR` y una demanda reactiva igual a `Ener.Reac`, tomadas del
  pronóstico oficial de demanda definitivo de XM para esa fecha. El caso conserva por separado
  los dos componentes de la demanda activa de cada barra. Las barras del pronóstico se asocian a barras del modelo mediante la
  tabla de equivalencias versionada (FR-011). La demanda de barras por debajo de 57,5 kV (por
  ejemplo, 44 kV o 13,2 kV) se agrega a la barra del STR de la frontera STR/SDL a la que
  pertenecen, igual que los generadores (FR-019).
- **FR-014a [N]**: Si una barra del pronóstico de demanda no se puede asociar a una barra STN
  del modelo, entonces el sistema DEBE excluir esa demanda y registrar en el reporte de calidad
  la barra y sus MW, que también aparecen como demanda no ubicada en el balance.
- **FR-015 [U]**: El sistema DEBE usar una referencia (slack) distribuida: la diferencia entre
  generación y demanda más pérdidas se reparte entre los generadores conciliados con potencia
  programada mayor a 0 MW en el periodo, en proporción a esa potencia programada. Una barra
  fija, configurada en el repositorio con su criterio de elección documentado, sirve como
  referencia de ángulo. El caso muestra la barra de ángulo y los factores de participación
  como supuestos.
- **FR-016 [U]**: El sistema DEBE detectar islas eléctricas y reportarlas antes de ejecutar el
  cálculo.
- **FR-017 [U]**: El sistema DEBE construir la red con los elementos del STN (tensión nominal
  ≥ 220 kV) y del STR (≥ 57,5 kV y < 220 kV). Los elementos de PARATEC por debajo de 57,5 kV
  (SDL) se excluyen del modelo, y su demanda y generación se ubican en la barra del STR de la
  frontera STR/SDL a la que pertenecen.
- **FR-018 [U]**: El sistema DEBE mostrar en el caso, como supuestos explícitos, la potencia
  reactiva y la consigna de tensión asignadas a cada generador, con la fuente de cada valor
  por defecto.
- **FR-019 [N]**: Si un generador conciliado se conecta por debajo de 57,5 kV, entonces el
  sistema DEBE trasladar su potencia programada como inyección a la barra del STR de la
  frontera STR/SDL a la que pertenece, y registrar en el reporte de calidad el generador, su
  barra original, la barra de destino y los MW trasladados. Si no se puede identificar esa
  frontera, el generador se trata como no ubicado (FR-012).

**Ejecución**

- **FR-020 [E]**: Cuando el usuario ejecute un caso, el sistema DEBE correr un flujo de potencia
  AC.
- **FR-021 [O]**: Donde el usuario seleccione flujo DC, el sistema DEBE correr un flujo DC y
  etiquetar los resultados como aproximación DC.
- **FR-022 [N]**: Si el flujo AC no converge, entonces el sistema DEBE devolver el estado
  `no_convergio` con iteraciones, mayor desbalance y barras problemáticas, y NO DEBE presentar
  tensiones ni flujos como resultado válido.
- **FR-023 [U]**: El sistema DEBE asociar a cada resultado: fecha del snapshot PARATEC, fecha y
  periodo del despacho, tipo de flujo, versión del motor de cálculo, parámetros del solver e
  identificador (hash) del caso.
- **FR-024 [U]**: El sistema DEBE calcular un balance con generación ubicada, demanda asignada,
  pérdidas y ajuste total absorbido por la referencia distribuida, además del ajuste de cada
  generador participante.
- **FR-025 [N]**: Si las fechas del snapshot PARATEC y del despacho difieren, entonces el
  sistema DEBE mostrar una advertencia en el resultado.
- **FR-026 [U]**: El sistema DEBE describir todo resultado como "flujo sobre despacho
  programado" y nunca como "estado real del SIN".

**Resultados**

- **FR-030 [U]**: El sistema DEBE presentar por barra: tensión en pu y kV y ángulo; por línea y
  transformador: P, Q, corriente, cargabilidad en % y pérdidas; por generador: P y Q.
- **FR-031 [S]**: Mientras haya límites de tensión o cargabilidad configurados, el sistema DEBE
  resaltar y contar los elementos que los violen.
- **FR-032 [E]**: Cuando el usuario exporte un resultado, el sistema DEBE generar un archivo
  tabular por tipo de elemento y un archivo de metadatos con la trazabilidad de FR-023.
- **FR-033 [U]**: El sistema DEBE ofrecer una vista de topología lógica de la red coloreable por
  tensión o por cargabilidad.

### Restricciones

**Técnicas**

- **R-01**: La ejecución del MVP (HU-1, HU-2) DEBE funcionar sin conexión a internet, usando
  solo los datos incluidos en el repositorio.
- **R-02**: Los snapshots son inmutables. Una actualización produce un snapshot nuevo, nunca
  modifica uno existente.
- **R-03**: Las pruebas automatizadas NO DEBEN acceder a PARATEC ni a los servidores de XM.
  Usan fixtures grabados.
- **R-04**: El formato de los archivos de despacho DEBE validarse contra el *Estándar de
  información del despacho* publicado por XM, y la versión de ese estándar DEBE quedar
  registrada en el manifiesto.
- **R-05**: Toda conversión de unidades entre fuentes y modelo sigue la regla III.1 de la
  constitución.

**De negocio y dominio**

- **R-10**: El despacho programado de XM es un **programa**, no la generación real (ver
  FR-026).
- **R-11**: El despacho reporta potencia activa. La potencia reactiva y la consigna de tensión
  de los generadores son supuestos del modelo y DEBEN quedar visibles en el caso (ver FR-018).
- **R-12**: Los datos redistribuidos DEBEN citar a XM como fuente y respetar sus términos de
  uso.
- **R-13**: Ningún parámetro técnico ni valor por defecto de límites puede inventarse; todo
  valor por defecto cita su fuente (constitución III.5 y III.9).

### Entidades clave

- **Snapshot PARATEC**: parámetros técnicos de equipos en una fecha; inmutable; con manifiesto
  (fecha de extracción, fuentes, conteo de registros por entidad, checksums).
- **Despacho programado**: generación activa programada por recurso y periodo para un día;
  incluye la versión del estándar de información con que se validó.
- **Pronóstico oficial de demanda por barra**: archivo diario de XM con, por cada barra, su
  UCP, su tensión nominal (kV) y tres series de 24 valores horarios: energía activa, energía
  reactiva y pérdidas del STR asignadas a la demanda (que forman parte de la demanda activa,
  FR-014). Incluye barras de distintos niveles de tensión. Se
  guarda en el mismo snapshot que el despacho de esa fecha.
- **Tabla de equivalencias**: relación entre el nombre del recurso en el despacho y el generador
  en PARATEC; versionada; con vigencia.
- **Caso de estudio**: red construida para una fecha y un periodo, más los supuestos aplicados
  (demanda, referencia, alcance, imputaciones, consignas de generadores).
- **Reporte de calidad**: recursos no ubicados, generadores trasladados a la frontera STR/SDL,
  elementos excluidos o imputados, islas y balance.
- **Ejecución**: corrida del flujo sobre un caso, con su estado (`convergio` / `no_convergio`),
  sus parámetros del solver y su trazabilidad.
- **Resultado**: valores por elemento de una ejecución convergida.

## Criterios de éxito *(obligatorio)*

### Resultados medibles

- **SC-001**: Una persona que clona el repositorio obtiene su primer resultado convergido en
  menos de 10 minutos, siguiendo solo el README y sin conexión después de instalar
  dependencias.
- **SC-002**: El 100 % de los recursos del despacho con generación mayor a 0 MW en el periodo
  aparecen como ubicados o como no ubicados; ninguno se descarta en silencio.
- **SC-003**: Para el snapshot incluido, la generación ubicada cubre al menos el 95 % de la
  generación programada del periodo (valor provisional; ver Supuestos A-05).
- **SC-004**: El flujo AC sobre el caso incluido converge para todos los periodos 1–24 de la
  fecha incluida, cada uno ejecutado por separado.
- **SC-005**: El proceso de construcción y cálculo, aplicado a una red de referencia con
  solución conocida, reproduce las tensiones con un error máximo de 1e-6 pu.
- **SC-006**: Una ejecución del comando de actualización interrumpida en cualquier punto deja el
  directorio de datos idéntico al estado previo.
- **SC-007**: Todo resultado exportado contiene completos los metadatos de trazabilidad de
  FR-023.

## Supuestos

Supuestos a validar en `/speckit-clarify`:

- **A-01**: El despacho programado tiene 24 periodos horarios por día, y el periodo 1
  corresponde a 00:00–01:00.
- **A-02**: Los archivos públicos de despacho son accesibles sin credenciales, por web o por la
  ruta pública de FTPS de XM.
- **A-03**: PARATEC permite identificar la subestación o barra de conexión de cada generador y
  los extremos de cada línea.
- **A-04**: Por defecto, los generadores se modelan como nodos PV con consigna de tensión
  configurable. El valor por defecto se muestra en el caso como supuesto y cita su fuente
  (R-13).
- **A-05**: El umbral de cobertura de SC-003 (95 %) es provisional; el borrador lo dejaba sin
  definir y debe confirmarse en clarify.
- **A-06**: Los datos de XM (PARATEC, despacho programado y pronóstico de demanda) se
  redistribuyen en el repositorio con la atribución exigida por la constitución III.10
  (v1.1.0).
- **A-07**: La aplicación es local y monousuario; no hay requisitos de autenticación (ver
  NG-08).
- **A-08**: El pronóstico por barra se publica como archivo de texto diario `PRON_BARRA<MMDD>`
  en la biblioteca de XM y en la ruta pública FTPS
  `/INFORMACION_XM/Publico/DEMANDAS/Pronostico Oficial/` (verificado el 2026-10-19). Cada fila
  tiene: UCP, barra, tensión (kV), tipo (`Ener.Act.`, `Ener.Reac` o `Perd.PSTR`) y 24 valores
  horarios. Junto a él se publica `PRON_SIN<MMDD>` (total del SIN), que esta feature no usa.
  Unidades a confirmar: se asume que los valores horarios están en MWh y Mvarh, equivalentes a
  MW y Mvar medios del periodo.

## No objetivos

Esta feature **NO** construye lo siguiente. El agente no debe implementarlo ni dejar "preparado"
código para ello.

- **NG-01**: Análisis de contingencias N-1 o N-k.
- **NG-02**: Cálculo de cortocircuito.
- **NG-03**: Series de tiempo: correr las 24 horas, varios días o animaciones temporales. Cada
  ejecución es una fecha y un periodo.
- **NG-04**: Flujo óptimo de potencia (OPF), redespacho o despacho económico propio.
- **NG-05**: Estabilidad dinámica, transitorios o respuesta de frecuencia.
- **NG-06**: Uso de redespacho, generación real o disponibilidad real como fuente del punto de
  operación.
- **NG-07**: Edición manual de la red desde la interfaz (agregar, quitar o modificar elementos).
- **NG-08**: Autenticación, usuarios, roles o despliegue multiusuario en la nube.
- **NG-09**: Descargas programadas o automáticas de datos (cron, schedulers). La actualización
  es solo manual por comando.
- **NG-10**: Comparación o validación contra resultados operativos publicados por XM.
- **NG-11**: Representación de interconexiones internacionales como algo distinto de
  inyecciones fijas.
- **NG-12**: Mapas georreferenciados. La vista de topología es lógica, no geográfica.
- **NG-13**: Soporte para fuentes de datos distintas de PARATEC, del despacho programado y del
  pronóstico oficial de demanda definitivo de XM.
- **NG-14**: Aceleración por GPU. Si se evalúa, será una feature aparte.

## Decisiones pendientes

1. **Opción de forzar en la actualización (FR-004).** El borrador decía "sin la opción de
   forzar", lo que implica que existe una opción que sobrescribe un snapshot existente. Eso
   contradice la constitución III.4 ("no se edita tras su commit") y R-02 de esta spec. Mientras
   no se decida, FR-004 se redactó sin esa opción, porque la constitución prevalece.
