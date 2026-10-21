# Fase 1: reconocimiento de la VM Windows con PowerFactory. Solo lectura.
# Uso: scp recon.ps1 jcjt9-windows10:C:/Users/jcjt9/pf_tests/ ; ssh jcjt9-windows10 "powershell -File C:/Users/jcjt9/pf_tests/recon.ps1"

$ErrorActionPreference = "Continue"

Write-Output "== Sistema =="
Write-Output ("Windows: " + (Get-CimInstance Win32_OperatingSystem).Caption + " " + (Get-CimInstance Win32_OperatingSystem).Version + " (" + (Get-CimInstance Win32_OperatingSystem).OSArchitecture + ")")
Write-Output ("Usuario: " + [System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Output ("Administrador (token actual): " + $isAdmin)
Write-Output ("Miembro del grupo Administradores: " + ((net localgroup Administradores 2>$null) + (net localgroup Administrators 2>$null) | Select-String -Pattern "jcjt9" -Quiet))
Write-Output ("CPU/RAM: " + (Get-CimInstance Win32_Processor).Name + " / " + [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1) + " GB")

Write-Output "`n== PowerFactory: instalaciones en C:\Program Files\DIgSILENT =="
$pfRoot = "C:\Program Files\DIgSILENT"
if (Test-Path $pfRoot) {
    Get-ChildItem $pfRoot -Directory | ForEach-Object {
        Write-Output ("- " + $_.FullName)
        $exe = Get-ChildItem $_.FullName -Filter "PowerFactory*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($exe) {
            $v = (Get-Item $exe.FullName).VersionInfo
            Write-Output ("    exe: " + $exe.Name + "  versión de archivo: " + $v.FileVersion + "  producto: " + $v.ProductVersion)
        }
        $py = Join-Path $_.FullName "Python"
        if (Test-Path $py) {
            Write-Output ("    API Python (subcarpetas): " + ((Get-ChildItem $py -Directory | ForEach-Object { $_.Name }) -join ", "))
            Get-ChildItem $py -Recurse -Filter "powerfactory*.pyd" -ErrorAction SilentlyContinue | ForEach-Object { Write-Output ("      " + $_.FullName.Replace($pfRoot, "")) }
        }
    }
} else {
    Write-Output "No existe $pfRoot"
}
Write-Output "Otras rutas con DIgSILENT (x86 / ProgramData / AppData):"
foreach ($p in @("C:\Program Files (x86)\DIgSILENT", "C:\ProgramData\DIgSILENT", "$env:APPDATA\DIgSILENT", "$env:LOCALAPPDATA\DIgSILENT")) {
    if (Test-Path $p) { Write-Output ("- " + $p + ": " + ((Get-ChildItem $p -ErrorAction SilentlyContinue | ForEach-Object { $_.Name }) -join ", ")) }
}

Write-Output "`n== Python instalado =="
$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pyLauncher) { Write-Output "py -0p:"; & py -0p 2>&1 | ForEach-Object { Write-Output ("  " + $_) } } else { Write-Output "No hay lanzador py" }
foreach ($cmd in @("python", "python3")) {
    $c = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($c) { Write-Output ($cmd + ": " + $c.Source + " -> " + (& $c.Source --version 2>&1)) } else { Write-Output ($cmd + ": no está en PATH") }
}
Write-Output "Carpetas típicas:"
foreach ($p in @("C:\Python*", "$env:LOCALAPPDATA\Programs\Python\Python*", "C:\Program Files\Python*", "C:\ProgramData\Anaconda*", "$env:USERPROFILE\anaconda*", "$env:USERPROFILE\miniconda*")) {
    Get-Item $p -ErrorAction SilentlyContinue | ForEach-Object { Write-Output ("- " + $_.FullName) }
}
Write-Output "Registro (PythonCore):"
foreach ($hive in @("HKLM:\SOFTWARE\Python\PythonCore", "HKCU:\SOFTWARE\Python\PythonCore")) {
    if (Test-Path $hive) { Get-ChildItem $hive | ForEach-Object { $ip = (Get-ItemProperty ($_.PSPath + "\InstallPath") -ErrorAction SilentlyContinue).'(default)'; Write-Output ("- " + $hive + " " + $_.PSChildName + " -> " + $ip) } }
}

Write-Output "`n== Licencia (indicios) =="
Write-Output "Servicios relacionados (CodeMeter / Sentinel / WIBU / DIgSILENT / FlexLM):"
Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match "CodeMeter|Sentinel|WIBU|DIgSILENT|FlexNet|lmgrd|HASP" } | ForEach-Object { Write-Output ("- " + $_.DisplayName + " [" + $_.Status + "]") }
Write-Output "Dispositivos USB con pinta de llave (WIBU/Sentinel/HASP/Aladdin):"
Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.FriendlyName -match "WIBU|CodeMeter|Sentinel|HASP|Aladdin|SafeNet" } | ForEach-Object { Write-Output ("- " + $_.FriendlyName + " [" + $_.Status + "]") }
Write-Output "Variables de entorno DIgSILENT/licencia:"
Get-ChildItem Env: | Where-Object { $_.Name -match "DIGSILENT|PF_|LM_LICENSE|CODEMETER|WIBU" } | ForEach-Object { Write-Output ("- " + $_.Name + "=" + $_.Value) }
Write-Output "Archivos de configuración/licencia de PowerFactory (solo nombres):"
foreach ($p in @("C:\ProgramData\DIgSILENT", "$env:APPDATA\DIgSILENT", "$env:LOCALAPPDATA\DIgSILENT")) {
    if (Test-Path $p) { Get-ChildItem $p -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "lic|\.ini$|\.cfg$|settings" } | Select-Object -First 30 | ForEach-Object { Write-Output ("- " + $_.FullName) } }
}
Write-Output "Procesos de PowerFactory en ejecución:"
Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match "PowerFactory" } | ForEach-Object { Write-Output ("- " + $_.ProcessName + " pid " + $_.Id) }
Write-Output "`n== Fin del reconocimiento =="
