# Guía de validación: análisis N-1

**Feature**: 003-contingencias-n1 | **Spec**: [spec.md](./spec.md)

Requisitos: el repositorio con `uv sync --project backend` y `pnpm --dir frontend install`. Todo
corre sin internet sobre el snapshot incluido del 2026-10-20.

## 1. Pruebas

```bash
make test
```

Esperado: pasan las pruebas existentes y las nuevas de SC-019 (FR-052 con valores conocidos,
orden y empates, no convergencia, islas, salida del generador de referencia, `sinsim n1`).

## 2. Terminal (HU-8)

```bash
uv run --project backend sinsim n1 --fecha 2026-10-20 --periodo 19 --salida out/n1-demo
```

Esperado:

- avance en stderr hasta `N-1: 1261/1261 contingencias`, en menos de 3 minutos (SC-014);
- en `out/n1-demo/`: los cuatro CSV y `metadatos.json` de [export-n1.md](./contracts/export-n1.md);
- en `metadatos.json`, `resumen` cumple la invariante de SC-017;
- código de salida 0.

Caso de error: con un caso cuyo flujo base no converge, el comando sale con código 4 y
`N1_BASE_INVALID`, sin escribir archivos.

## 3. Interfaz (HU-7)

```bash
make dev
```

1. Abrir la interfaz, elegir 2026-10-20, periodo 19, flujo AC, y ejecutar.
2. Pulsar «Analizar N-1». Se ve el avance (`contingencias hechas / total`) y la interfaz sigue
   respondiendo.
3. Al terminar: resumen arriba, listados de cargabilidad y de tensiones lado a lado, y debajo
   «Aíslan demanda» y «Sin solución».
4. Comparar con `out/n1-demo/`: mismas filas y mismo orden (SC-018).
5. Con un flujo DC en pantalla, el botón no está disponible y la interfaz explica por qué (FR-061).

## 4. Comprobación manual de una fila (SC-015)

Tomar la primera fila del listado de cargabilidad, sacar ese activo de servicio en la red del caso
(`cases/<case_id>/net.json`), correr un flujo AC con la configuración del proyecto y verificar que
el elemento indicado tiene la cargabilidad del listado. La prueba de integración de SC-015 hace
esto mismo de forma automática.
