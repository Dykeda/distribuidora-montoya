# Copia la base de datos a una carpeta de respaldo con fecha y hora en el nombre.
# Si el computador tiene OneDrive, el respaldo queda ahi (se sube solo a la nube).
# Si no, se guarda en una carpeta local "respaldos" junto al programa.
$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
$origen = Join-Path $aqui "instance\distribuidora.db"

if (-not (Test-Path $origen)) {
    Write-Host "No se encontro instance\distribuidora.db en esta carpeta."
    Write-Host "Asegurate de que este archivo este junto a DistribuidoraMontoya.exe."
    exit 1
}

if ($env:OneDrive -and (Test-Path $env:OneDrive)) {
    $destinoDir = Join-Path $env:OneDrive "Respaldos Distribuidora Montoya"
} else {
    $destinoDir = Join-Path $aqui "respaldos"
}

New-Item -ItemType Directory -Force -Path $destinoDir | Out-Null
$marca = Get-Date -Format "yyyy-MM-dd_HHmm"
$destino = Join-Path $destinoDir "distribuidora_$marca.db"
Copy-Item $origen $destino

Write-Host "Respaldo guardado en:"
Write-Host $destino
