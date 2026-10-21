# Mapa base vectorial (FR-035)

`colombia_departamentos.geojson` es el fondo de la disposición geográfica de la topología. Se
sirve por `GET /api/geo/basemap` y funciona sin internet (R-01).

## Fuente y licencia

- **Natural Earth**, capa *Admin 1 – States, Provinces*, escala 1:10m, versión 5.1.2.
- Archivo de origen: `ne_10m_admin_1_states_provinces.geojson` del repositorio
  `nvkelso/natural-earth-vector`, etiqueta `v5.1.2`.
- SHA-256 del archivo de origen: `22d0e3ad85eb3e27f17cabf8ba2d50e554fbc27a87796ff891d958185da62fb5`.
- Descargado el 2026-10-20.
- Licencia: **dominio público**. Atribución sugerida, que se conserva en el archivo:
  "Made with Natural Earth. Free vector and raster map data @ naturalearthdata.com".

No se usan teselas raster de OpenStreetMap: su política de uso prohíbe la descarga masiva.

## Procesamiento

1. Se conservan los 33 departamentos de Colombia (`adm0_a3 = COL`), incluida Bogotá D.C. y
   San Andrés y Providencia. Se descarta un elemento sin nombre (`CO-X01~`).
2. Se añaden, como contexto, los contornos de Venezuela, Ecuador, Panamá, Perú y Brasil,
   recortados al rectángulo de longitud −80,5 a −65,5 y latitud −5,0 a 14,0.
3. Geometrías simplificadas con tolerancia de 0,01° (unos 1 km) y coordenadas redondeadas a
   4 decimales. Es un fondo de referencia visual, no un dato para cálculos.

Cada elemento lleva `properties.kind` (`departamento` o `pais_vecino`) y `properties.name`.
Coordenadas en WGS84 (longitud, latitud).

## Uso

El mapa no se usa en el flujo de potencia ni entra en el hash del caso. La ubicación de las
barras sale de PARATEC (`SubstationInfo.latitude`/`longitude`), no de este archivo.
