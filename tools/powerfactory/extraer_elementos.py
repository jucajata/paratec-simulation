"""Inventario de los elementos de cálculo de un proyecto de PowerFactory a CSV.

Requiere PowerFactory 2021 SP2 con licencia válida y Python 3.9 de 64 bits.
Uso: python extraer_elementos.py "Nombre del proyecto"
Salida: Escritorio\\Elementos_PowerFactory\\inventario_elementos.csv (separador ";").
"""

import csv
import os
import sys

# 1. Rutas de PowerFactory 2021 SP2. `digapi.dll` vive en la carpeta raíz, no en Python\3.9,
#    así que las dos deben estar en la búsqueda de DLL.
PF_ROOT = r"C:\Program Files\DIgSILENT\PowerFactory 2021 SP2"
PF_API = os.path.join(PF_ROOT, "Python", f"{sys.version_info.major}.{sys.version_info.minor}")

if not os.path.isdir(PF_API):
    print(f"Error: no existe la API para Python {sys.version_info.major}.{sys.version_info.minor}: {PF_API}")
    sys.exit(1)
if hasattr(os, "add_dll_directory"):
    os.add_dll_directory(PF_ROOT)
    os.add_dll_directory(PF_API)
os.environ["PATH"] = PF_ROOT + os.pathsep + os.environ.get("PATH", "")
if PF_API not in sys.path:
    sys.path.append(PF_API)

try:
    import powerfactory as pf  # type: ignore[import-not-found]
except ImportError as err:
    print(f"Error al importar el módulo powerfactory: {err}")
    sys.exit(1)

# 2. Proyecto y salida.
project_name = sys.argv[1] if len(sys.argv) > 1 else "Mi_Proyecto"
desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop", "Elementos_PowerFactory")
os.makedirs(desktop_dir, exist_ok=True)
csv_output = os.path.join(desktop_dir, "inventario_elementos.csv")

# 3. Conexión. GetApplicationExt lanza una excepción con el código de error en vez de
#    devolver None, lo que ayuda a diagnosticar problemas de licencia o de instancia.
try:
    app = pf.GetApplicationExt()
except Exception as exc:  # noqa: BLE001 - se informa el error exacto
    print(f"Error: no se pudo conectar a PowerFactory: {type(exc).__name__}: {exc}")
    sys.exit(1)

app.SetGuiUpdateEnabled(0)

# 4. Activar proyecto y caso de estudio (solo lectura: no se modifica nada).
if app.ActivateProject(project_name) != 0:
    print(f"Error: no se encontró o no se pudo activar el proyecto '{project_name}'.")
    sys.exit(1)

try:
    study_case = app.GetActiveStudyCase()
    if not study_case:
        print("Error: no hay ningún caso de estudio activo en el proyecto.")
        sys.exit(1)
    print(f"Caso de estudio activo: {study_case.loc_name}")

    # 5. Elementos relevantes para el cálculo.
    headers = ["Nombre", "Tipo_Clase", "En_Servicio", "Carpeta_Padre", "Ruta_Completa"]
    rows = []
    for elem in app.GetCalcRelevantObjects("*"):
        outserv = getattr(elem, "outserv", None)
        estado = {0: "En servicio", 1: "Fuera de servicio"}.get(outserv, "N/A")
        parent = elem.GetParent()
        rows.append(
            [
                elem.loc_name,
                elem.GetClassName(),
                estado,
                parent.loc_name if parent else "N/A",
                elem.GetFullName(),
            ]
        )

    # 6. CSV.
    with open(csv_output, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)
        writer.writerows(rows)
    print(f"Listo: {len(rows)} elementos guardados en {csv_output}")
finally:
    prj = app.GetActiveProject()
    if prj:
        prj.Deactivate()
