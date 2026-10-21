# Instala Python 3.9.13 (64 bits) desde python.org solo para el usuario actual, sin tocar el PATH.
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File install_python39.ps1
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # sin consola, la barra de progreso falla por SSH
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$url = "https://www.python.org/ftp/python/3.9.13/python-3.9.13-amd64.exe"
$dst = "C:\Users\jcjt9\pf_tests\python-3.9.13-amd64.exe"
$target = "C:\Users\jcjt9\AppData\Local\Programs\Python\Python39\python.exe"
if (Test-Path $target) { Write-Output "Ya existe: $target"; & $target --version; exit 0 }
Write-Output "Descargando $url"
(New-Object System.Net.WebClient).DownloadFile($url, $dst)
Write-Output ("Descargado: " + [math]::Round((Get-Item $dst).Length / 1MB, 1) + " MB")
Write-Output "Instalando (silencioso, solo usuario, sin PATH)..."
$p = Start-Process -FilePath $dst -ArgumentList "/quiet InstallAllUsers=0 PrependPath=0 Include_test=0 Include_launcher=0 Include_doc=0 SimpleInstall=1" -Wait -PassThru
Write-Output ("Código de salida del instalador: " + $p.ExitCode)
if (Test-Path $target) { Write-Output ("Instalado: " + $target); & $target --version; & $target -c "import struct,sys; print('bits:', struct.calcsize('P')*8, '| exe:', sys.executable)" } else { Write-Output "No aparece python.exe en la ruta esperada"; exit 1 }
