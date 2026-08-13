# Baja la base de datos real del servidor y genera un Excel legible a partir de ella.
# Pensado para correr solo, una vez al dia, via el Programador de tareas de Windows.
$ErrorActionPreference = "Stop"

$proyecto = "C:\Users\Kevin P\Documents\distribuidora-montoya"
$python = Join-Path $proyecto "venv\Scripts\python.exe"
$scriptExcel = Join-Path $proyecto "respaldo_local\generar_excel.py"

if ($env:OneDrive -and (Test-Path $env:OneDrive)) {
    $destinoDir = Join-Path $env:OneDrive "Respaldos Distribuidora Montoya"
} else {
    $destinoDir = Join-Path $proyecto "respaldo_local\respaldos"
}
New-Item -ItemType Directory -Force -Path $destinoDir | Out-Null

$marca = Get-Date -Format "yyyy-MM-dd_HHmm"
$dbLocal = Join-Path $destinoDir "distribuidora_$marca.db"
$excelSalida = Join-Path $destinoDir "distribuidora_$marca.xlsx"

Write-Host "Bajando la base de datos real del servidor..."
& scp -o ConnectTimeout=15 montoya@104.248.119.242:/home/montoya/distribuidora-montoya/instance/distribuidora.db "$dbLocal"
if ($LASTEXITCODE -ne 0) {
    Write-Host "No se pudo conectar al servidor. Revisa que tengas internet y que el servidor este activo."
    exit 1
}

Write-Host "Generando Excel legible..."
& $python $scriptExcel "$dbLocal" "$excelSalida"

Write-Host ""
Write-Host "Listo. Copia de la base de datos y Excel guardados en:"
Write-Host $destinoDir
