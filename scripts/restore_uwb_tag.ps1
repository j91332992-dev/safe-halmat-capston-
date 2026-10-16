param(
    [Parameter(Mandatory = $true)][string]$Manifest,
    [string]$Port = 'COM6'
)
$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repository '.venv\Scripts\python.exe'
$esptool = Join-Path $repository '.pio-core\packages\tool-esptoolpy\esptool.py'
$record = Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
if ($record.device_verified -ne $true) { throw 'Backup has not passed on-device verification' }
$backup = $record.backup_file
if ((Get-Item -LiteralPath $backup).Length -ne 16777216) { throw 'Backup size differs from 16 MiB' }
$hash = (Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne $record.sha256) { throw 'Backup SHA-256 mismatch' }
$identity = & $python $esptool --chip esp32 --port $Port flash_id 2>&1
$identity | Write-Output
if ($LASTEXITCODE -ne 0) { throw 'Cannot identify the connected tag' }
if (($identity -join "`n") -notmatch [regex]::Escape($record.mac)) { throw 'Connected MAC differs from the backed-up tag' }
& $python $esptool --chip esp32 --port $Port --baud 921600 write_flash --flash_size keep 0x0 $backup
if ($LASTEXITCODE -ne 0) { throw 'Flash restore failed' }
Write-Output 'Full flash restored. The prior firmware uses 115200 baud.'
