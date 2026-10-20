# Contrato del formato de snapshot y de las equivalencias

## 1. Estructura de directorios (constitución III.3 y III.4)

```text
data/paratec/<YYYY-MM-DD>/
├── manifest.json
├── raw/                                  # bytes tal como se descargaron; NUNCA se modifican
│   ├── paratec/<servicio>__<recurso>.json   # p. ej. reportetransmision__Line_getAll.json
│   └── xm/
│       ├── dDEC<MMDD>.txt                # V0
│       ├── dDEC<MMDD>_V<n>.txt           # si existen; prevalece la n más alta (D-3)
│       └── PRON_BARRA<MMDD>.txt
└── normalized/                           # derivados de raw/ por el scraper
    ├── buses.parquet
    ├── lines.parquet
    ├── trafos2w.parquet
    ├── trafos3w.parquet
    ├── generators.parquet
    ├── shunts.parquet
    ├── svc_statcom.parquet
    ├── dispatch.parquet
    └── demand.parquet
```

Las columnas de cada Parquet están en [data-model.md §2](../data-model.md).

## 2. `manifest.json`

```json
{
  "schema_version": 1,
  "snapshot_date": "2026-10-20",
  "extracted_at": "2026-10-19T09:15:02-05:00",
  "scraper_version": "0.1.0",
  "attribution": "Información proporcionada por XM S.A. E.S.P. – PARATEC y archivos públicos de despacho",
  "dispatch_version": {"used": "V1", "available": ["V0", "V1"]},
  "sources": [
    {"entity": "paratec.lines",
     "url": "https://paratecbackend.xm.com.co/reportetransmision/api/Line/getAll",
     "source_modified_at": null, "standard_version": null},
    {"entity": "xm.dispatch",
     "url": "https://api-portalxm.xm.com.co/administracion-archivos/ficheros/descarga-archivo?ruta=M:/InformacionAgentes/Usuarios/Publico/DESPACHO/2026-10/dDEC1020.txt&nombreBlobContainer=storageportalxm",
     "source_modified_at": "2026-10-19T14:05:11-05:00",
     "standard_version": "XM-CND-2014-045 ed. 2025"}
  ],
  "record_counts": {"paratec.lines": 929, "xm.dispatch.resources": 625, "xm.demand.nodes": 552},
  "files": [
    {"path": "raw/xm/dDEC1020.txt", "sha256": "…", "bytes": 61234}
  ]
}
```

Reglas:
- `files` cubre todos los archivos de `raw/` y `normalized/`. No incluye `manifest.json`.
- Las rutas son relativas al directorio del snapshot.
- Al cargar un snapshot, cualquier diferencia de checksum da `SNAPSHOT_CORRUPTED` (FR-006).

## 3. Equivalencias (`data/equivalencias/*.csv`)

Ambas tablas usan UTF-8, separador `,`, fechas ISO-8601 y `valid_to` vacío = vigente.

**`recursos_despacho.csv`**

```csv
resource,kind,paratec_ids,connection_bus,valid_from,valid_to,note
GUATAPE,plant,HydraulicPlant:GUATAPE,,2020-01-01,,
ECUADOR230_1,intl_link,,JAMONDINO|230,2020-01-01,,inyección fija (NG-11)
```

**`nodos_demanda.csv`**

```csv
node,ucp,vn_kv,substation,paratec_vn_kv,valid_from,valid_to,note
DONCELL1,Uandaki,115,DONCELLO,115,2020-01-01,,
```

Reglas:
- Una vigencia que se solapa para la misma clave es un error de validación (lo verifica
  `make test`).
- El contenido real lo curan personas (research R7). Los valores de los ejemplos son
  ilustrativos.
