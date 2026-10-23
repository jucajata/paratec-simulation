# Cambios

Todas las versiones de sinsim, de la más reciente a la más antigua. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y la numeración sigue
[versionado semántico](https://semver.org/lang/es/). Mientras la versión empiece por 0, el
proyecto está en desarrollo y el contenido de un caso puede cambiar entre versiones menores.

Cada caso registra en su traza la versión de sinsim con que se calculó: para reproducir un
resultado, usa el código de esa versión.

## [0.5.0] - 2026-10-23

sinsim se instala con un comando y funciona desde cualquier carpeta.

### Añadido

- **Paquete instalable** con todo lo necesario para trabajar sin internet: configuración, tablas
  de equivalencias, mapa base, la interfaz construida y el snapshot del 2026-10-20.
- **Comando `sinsim serve`**: levanta la API y la interfaz en `127.0.0.1` y abre el navegador.
- **Carpeta de datos del usuario** para los snapshots descargados y los casos, configurable con
  `SINSIM_HOME`.
- **`make package`** construye el wheel y el sdist, y una acción de GitHub los adjunta a cada
  release publicado.

### Sin cambios para quien clona el repositorio

- Dentro del repositorio, sinsim sigue usando `config/`, `data/` y `cases/`. Un mismo escenario
  produce el mismo `case_id` en los dos modos.

### Gobernanza

- Constitución 1.2.0: se añade el modo instalado (III.4 y IV).

## [0.4.0] - 2026-10-23

Primera versión publicada. Reúne el modelo del SIN construido desde PARATEC, el despacho
programado y el pronóstico de demanda de XM, y la interfaz web para ejecutarlo.

### Añadido

- **Coordenadas curadas** para subestaciones que PARATEC publica sin coordenadas, en la tabla
  `data/equivalencias/coordenadas_subestaciones.csv` con su fuente. La primera fila ubica
  Pimampiro (Ecuador), extremo de los circuitos Jamondino–Pimampiro 230 kV (#3, supuesto S21).
- **Descarga desde la interfaz**: una fecha sin snapshot se descarga de PARATEC y XM desde el
  campo de fecha, hasta el día siguiente.
- **Aviso «Cómo colaborar»** en el reporte de calidad, con los recursos y nodos sin ubicar.
- **Subáreas, mapa geográfico, flujos por barra y reporte de violaciones** (#1, FR-034 a
  FR-037).

### Cambiado

- **Topología sin saturación** con muchas barras cercanas (#2): tamaños acotados en pantalla,
  flechas de flujo de tamaño fijo a mitad de rama, etiquetas sin solapes en cuatro posiciones,
  dobles circuitos separados y barras de una misma subestación repartidas según el zoom.
- **Rediseño de la interfaz** sobre el sistema de diseño sinsim: tema oscuro, foco visible,
  franja de indicadores, pestañas segmentadas, tablas con cifras alineadas y estado por fila.
  El mapa de topología va primero.
- El contenido del caso cambia respecto a 0.3.0: las coordenadas curadas entran en los
  supuestos y en el hash del caso.

### Datos

- Snapshots de PARATEC del 2026-10-09, 2026-10-19, 2026-10-20 y 2026-10-21.

[0.5.0]: https://github.com/jucajata/paratec-simulation/releases/tag/v0.5.0
[0.4.0]: https://github.com/jucajata/paratec-simulation/releases/tag/v0.4.0
