"""Fase 2: prueba mínima de la API de Python de PowerFactory.

Importa `powerfactory`, obtiene la aplicación (prueba `GetApplicationExt` y, si no existe,
`GetApplication`), imprime la versión y lista los proyectos del usuario. No modifica nada.

Uso en la VM: python pf_hello.py
"""

import os
import sys
import traceback

PF_DIR = r"C:\Program Files\DIgSILENT\PowerFactory 2021 SP2"
PY_TAG = f"{sys.version_info.major}.{sys.version_info.minor}"
API_DIR = os.path.join(PF_DIR, "Python", PY_TAG)


def main() -> int:
    print(f"python: {sys.version.split()[0]} ({'64' if sys.maxsize > 2**32 else '32'} bits)")
    print(f"api dir: {API_DIR} -> {'existe' if os.path.isdir(API_DIR) else 'NO EXISTE'}")
    sys.path.insert(0, API_DIR)
    os.environ["PATH"] = PF_DIR + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(PF_DIR)

    try:
        import powerfactory  # type: ignore[import-not-found]
    except Exception:
        print("FALLO al importar powerfactory:")
        traceback.print_exc()
        return 2
    print(f"powerfactory importado desde: {powerfactory.__file__}")
    print(f"funciones disponibles: {[n for n in dir(powerfactory) if n.startswith('GetApplication')]}")

    app = None
    if hasattr(powerfactory, "GetApplicationExt"):
        print("probando GetApplicationExt()...")
        try:
            app = powerfactory.GetApplicationExt()
        except Exception as exc:  # noqa: BLE001 - queremos el mensaje exacto
            print(f"GetApplicationExt falló: {type(exc).__name__}: {exc}")
    if app is None:
        print("probando GetApplication()...")
        try:
            app = powerfactory.GetApplication()
        except Exception as exc:  # noqa: BLE001
            print(f"GetApplication falló: {type(exc).__name__}: {exc}")
            return 3
    if app is None:
        print("GetApplication devolvió None (sin licencia o sin instancia)")
        return 3

    print(f"versión de PowerFactory: {app.GetVersion()}")
    try:
        user = app.GetCurrentUser()
        print(f"usuario: {user.loc_name if user else None}")
        projects = user.GetContents("*.IntPrj", 1) if user else []
        print(f"proyectos del usuario: {len(projects)}")
        for prj in projects:
            print(f"  - {prj.GetFullName()}")
    except Exception as exc:  # noqa: BLE001
        print(f"no se pudieron listar los proyectos: {type(exc).__name__}: {exc}")
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
