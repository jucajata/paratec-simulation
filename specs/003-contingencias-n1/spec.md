# Spec: análisis de contingencias N-1

**Feature**: 003-contingencias-n1 | **Fecha**: 2026-10-24 | **Estado**: borrador para revisión
**Release objetivo**: 0.6.0
**Origen**: conversación con el usuario del 2026-10-24. El usuario quiere identificar el impacto
que tiene la salida de activos eléctricos para estudiar restricciones eléctricas y, más adelante,
la generación de seguridad. Decidió acotar este release a N-1 (el N-2 completo son ~567.000 pares
en la red actual) y dejar fuera el cálculo de generación de seguridad.

## Problema

Hoy sinsim corre un flujo de carga sobre el despacho programado con todos los activos en
servicio. No dice qué pasa si sale uno de ellos. Para estudiar restricciones eléctricas, el
analista necesita saber qué salida de un activo deja la red en peor estado: qué elemento se
sobrecarga más y qué barra se sale más de su banda de tensión. Hacerlo a mano, activo por activo,
son más de mil flujos.

Esta spec levanta, para este análisis, la exclusión NG-01 de la spec 001 («Análisis de
contingencias N-1 o N-k»). La constitución ya incluye el N-1 en el alcance (I, «Capacidades en
alcance»).

## Historias de usuario

### HU-7. Ver qué contingencias N-1 son más críticas (prioridad P1)

Como analista del SIN, después de correr el flujo de una fecha y un periodo quiero lanzar el
análisis N-1 y ver, de mayor a menor, qué salidas de un activo provocan las peores sobrecargas y
las peores tensiones, para identificar las restricciones eléctricas de ese escenario.

**Aceptación**

1. Con un flujo AC convergido en pantalla, el botón «Analizar N-1» lanza el análisis sobre ese
   mismo caso y muestra el avance mientras corre.
2. Al terminar se ven dos listados lado a lado, cada uno ordenado de mayor a menor:
   cargabilidad y tensiones.
3. Una contingencia que lleva una línea al 200 % aparece en el listado de cargabilidad por encima
   de una que la lleva al 130 %.
4. Una línea que en el caso base ya estaba al 105 % y sigue al 105 % con la contingencia no hace
   que esa contingencia aparezca en el listado.
5. Las contingencias cuyo flujo no converge aparecen en el bloque «Sin solución», con su
   diagnóstico.

### HU-8. Correr el análisis N-1 desde la terminal (prioridad P2)

Como analista, quiero correr el mismo análisis con un comando y obtener los listados en CSV, para
guardarlos, compararlos entre fechas o procesarlos en otra herramienta.

**Aceptación**

1. `sinsim n1 --fecha 2026-10-20 --periodo 19` construye el caso si hace falta, corre el flujo
   base y el análisis N-1, y escribe los CSV y los metadatos en una carpeta de salida.
2. Los CSV contienen las mismas contingencias, en el mismo orden, que los listados de la
   interfaz para ese caso.

## Requisitos funcionales

- **FR-049** Contingencias analizadas. Para un caso con un flujo base AC convergido, el análisis
  saca de servicio, una a la vez, cada línea, cada transformador y cada generador en servicio en
  ese caso. Un generador es lo que el modelo ya representa como tal: un recurso del despacho en una
  barra (`RECURSO@BARRA`), es decir, la planta completa en esa barra, no una unidad (decisión del
  usuario del 2026-10-24). Los compensadores (SVC/STATCOM), que el modelo representa como generadores, también
  se analizan, identificados como compensadores. En el caso del 2026-10-20 son 1.261
  contingencias (857 líneas, 209 transformadores, 192 generadores y 3 compensadores).
- **FR-050** Flujo de cada contingencia. Es un flujo AC con la misma configuración de solver que el
  caso base, la misma referencia distribuida (FR-015) y los mismos límites. La potencia de un
  generador que sale la absorben los generadores despachados en proporción a su peso en la
  referencia distribuida. Cada flujo parte de la solución del caso base; si no converge, se
  reintenta una vez partiendo de un flujo DC antes de declararlo sin solución (FR-056).
- **FR-051** Generador de referencia de ángulo. Si la contingencia saca el generador de la barra de
  referencia de ángulo, la referencia pasa a la siguiente barra según el criterio de reserva que ya
  usa la construcción del caso (FR-015). Con la referencia distribuida, esa elección no altera los
  flujos. El cambio de referencia se registra en esa contingencia.
- **FR-052** Criterio de empeoramiento. Solo cuenta lo que la contingencia empeora frente al caso
  base:
  - una línea o un transformador cuenta en cargabilidad si con la contingencia supera el límite
    configurado (`limits.loading.max_percent`, hoy 100 % según CREG 025/1995) **y** su cargabilidad
    es mayor que en el caso base;
  - una barra cuenta en tensión si con la contingencia queda fuera de la banda de su nivel de
    tensión (`limits.voltage`) **y** su distancia a la banda, en valor absoluto, es mayor que en el
    caso base. Si la barra cambia de lado (de subtensión a sobretensión o al revés), se aplica la
    misma comparación de valores absolutos.
  No hay umbral mínimo: cualquier aumento frente al caso base cuenta, por pequeño que sea. El
  usuario lo decidió el 2026-10-24, sabiendo que el caso base del 2026-10-20 ya tiene 5 líneas
  sobrecargadas y unas 31 barras fuera de banda, y que por eso muchas contingencias entran a los
  listados con aumentos pequeños. El activo que sale no cuenta como elemento afectado. Las barras que quedan aisladas no cuentan
  en tensión (no tienen solución); se informan como en FR-055.
- **FR-053** Listado de cargabilidad. Una fila por contingencia con al menos un elemento que cuente
  según FR-052. Columnas: posición, activo fuera, elemento más cargado (entre los que cuentan según
  FR-052), cargabilidad con la contingencia (%). Orden: de mayor a menor por esa cargabilidad. En
  empate, por nombre del activo fuera.
- **FR-054** Listado de tensiones. Una fila por contingencia con al menos una barra que cuente según
  FR-052. Columnas: posición, activo fuera, barra más afectada (entre las que cuentan según FR-052),
  tensión con la contingencia (pu),
  distancia fuera de banda (pu, negativa para subtensión y positiva para sobretensión). Orden: de
  mayor a menor por el valor absoluto de esa distancia. En empate, por nombre del activo fuera.
- **FR-055** Barras aisladas. Si una contingencia deja barras aisladas y el resto de la red
  converge, se evalúa con FR-052 sobre la parte conectada, y su fila lleva la marca «aísla N barras,
  X MW sin servicio», donde X es la demanda asignada a esas barras.
  Además, toda contingencia que converge y deja demanda sin servicio aparece en un bloque compacto
  «Aíslan demanda», junto a «Sin solución», aunque no empeore ninguna cargabilidad ni tensión.
  Columnas: posición, activo fuera, barras aisladas, demanda sin servicio (MW). Orden: de mayor a
  menor por demanda sin servicio; en empate, por nombre del activo fuera (decisión del usuario del
  2026-10-24).
- **FR-056** Sin solución. Las contingencias cuyo flujo no converge van en un bloque compacto
  «Sin solución», debajo de los dos listados, con el diagnóstico que ya produce el proyecto para un
  flujo que no converge (iteraciones, desbalance máximo, barras problemáticas). Nunca se descartan
  ni se presentan como resultado válido (constitución III.8).
- **FR-057** Resumen. Encima de los listados se muestra: contingencias analizadas, cuántas entran en
  cada listado, cuántas aíslan demanda, cuántas no tienen solución, cuántas no tienen impacto y la
  duración del análisis.
- **FR-058** Lanzamiento desde la interfaz. Con un flujo AC convergido en pantalla, el botón
  «Analizar N-1» lanza el análisis en segundo plano. Mientras corre se ve el avance
  (contingencias hechas sobre el total) y la interfaz sigue respondiendo. Hay un solo análisis a
  la vez en toda la aplicación: ocupa casi todos los núcleos del equipo. Los listados solo muestran; no tienen acciones por fila.
- **FR-059** Comando `sinsim n1 --fecha YYYY-MM-DD --periodo N [--fecha-despacho F] [--salida CARPETA]
  [--json]`. Construye o reutiliza el caso con las mismas reglas de `sinsim run` (`--fecha-despacho`
  y `--json` significan lo mismo que allí), corre el flujo base AC y el análisis, y
  escribe `n1_cargabilidad.csv`, `n1_tensiones.csv`, `n1_aislan_demanda.csv`,
  `n1_sin_solucion.csv` y `metadatos.json`.
  Si el flujo base no converge, no corre el análisis y sale con el código de error de validación.
  Muestra el avance en la terminal.
- **FR-060** Trazabilidad (constitución III.7). Cada análisis registra la fecha del snapshot, el
  periodo, la versión de pandapower, la configuración del solver, el hash del caso, los límites
  aplicados con su fuente y la fecha y hora del análisis. Esos datos van en `metadatos.json` y se
  ven en la interfaz junto al resumen.
- **FR-061** Solo flujo AC. Si el flujo en pantalla es DC, el botón «Analizar N-1» no está
  disponible y la interfaz explica que el análisis se hace sobre el flujo AC.

## Casos límite

- El flujo base no converge: no hay análisis; la interfaz no ofrece el botón y el CLI sale con
  error de validación.
- Una contingencia saca el único vínculo de una zona con generación: la zona queda aislada; se
  trata con FR-055.
- Una contingencia saca el generador de referencia de ángulo: FR-051.
- Dos circuitos en paralelo: cada uno es una contingencia distinta.
- Recursos sin despacho: la construcción del caso (spec 001) no los incluye en la red, así que no
  son contingencias. Los únicos generadores con 0 MW en la red son los compensadores (S25). Esta
  spec no cambia la construcción del caso.
- El análisis se lanza de nuevo sobre el mismo caso: reemplaza al anterior en pantalla.
- Se pulsa «Analizar N-1» mientras otro análisis sigue corriendo (por ejemplo, tras cambiar de
  periodo): la interfaz muestra el mensaje «ya hay un análisis en curso, espera a que termine» y
  el botón se puede volver a pulsar después.

## Entidades clave

- **Contingencia**: el activo que sale (tipo: línea, transformador, generador o compensador;
  identificador; nombre; subárea), el estado del flujo (convergió o no), las barras aisladas y la
  demanda sin servicio, y el cambio de referencia si lo hubo.
- **Peor cargabilidad de una contingencia**: elemento, cargabilidad base y con contingencia,
  número de elementos que cuentan según FR-052.
- **Peor tensión de una contingencia**: barra, tensión base y con contingencia, distancia fuera de
  banda, número de barras que cuentan según FR-052.
- **Análisis N-1**: el conjunto de contingencias de un caso y un flujo base, con su resumen y su
  trazabilidad (FR-060).

## Fuera de alcance

- N-2 o N-k.
- Generación de seguridad, redespacho u optimización (excluidos por la constitución, I).
- Acciones correctivas o remediales.
- Análisis N-1 sobre flujo DC.
- Acciones por fila: centrar en el mapa, abrir la contingencia como un flujo, filtrar.
- Límites de emergencia distintos al límite normal: se usa el límite configurado.

## Criterios de éxito

- **SC-014** Sobre el caso del 2026-10-20, periodo 19, el análisis completo de unas 1.260
  contingencias termina en menos de 3 minutos en el portátil del usuario (12 núcleos; 76 s medidos
  en research R2), y la interfaz muestra el avance durante todo ese tiempo. Para lograrlo, las contingencias pueden repartirse entre los
  núcleos del equipo, sin dependencias nuevas.
- **SC-015** Para una contingencia elegida en las pruebas, la cargabilidad y la tensión que muestra
  el listado coinciden con las de un flujo corrido a mano con ese activo fuera de servicio.
- **SC-016** Ninguna violación que ya existe en el caso base, y que la contingencia no empeora, hace
  que la contingencia entre en un listado.
- **SC-017** Toda contingencia analizada que no converge está solo en «Sin solución». Toda
  contingencia que converge está en cero, uno o varios de: listado de cargabilidad, listado de
  tensiones, «Aíslan demanda»; si no está en ninguno, se cuenta como sin impacto. El resumen cuadra
  con el número de contingencias analizadas.
- **SC-018** Los CSV de `sinsim n1` tienen las mismas filas y el mismo orden que los listados y
  bloques de la interfaz para el mismo caso.
- **SC-019** Todas las pruebas existentes pasan. Las nuevas cubren FR-052 con valores conocidos, el
  orden de los dos listados, una contingencia que no converge, una que aísla barras, la salida del
  generador de referencia y el comando `sinsim n1`.

## Supuestos

- **S23 (propuesto)** Reparto de la potencia de un generador que sale: lo absorbe la referencia
  distribuida existente (FR-015), en proporción al peso de cada generador despachado. Es decisión
  del agente, aceptada en la conversación; el usuario puede corregirla si en el sector se reparte de
  otra forma.
- **S24 (propuesto)** El análisis N-1 no se guarda en disco en este release: vive con la corrida en
  la sesión de la interfaz, y el CLI lo escribe en la carpeta de salida. Volver a abrir la interfaz
  exige lanzarlo de nuevo.
- **S25 (propuesto)** Los compensadores (SVC/STATCOM) se analizan como contingencias porque su
  salida afecta tensiones; el usuario pidió «cada generador» y el modelo los representa como
  generadores.
