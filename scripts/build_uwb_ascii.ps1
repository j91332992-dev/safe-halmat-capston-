param([string[]]$Environments = @('tag', 'anchor-01'), [string]$OutputDirectory = '', [switch]$CompileTestWifi)
$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repository $(if ($CompileTestWifi) { '.pio-artifacts/compile-test-only' } else { '.pio-artifacts' })
}
$stage = Join-Path 'C:\Windows\Temp' ('u-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
$previousCore = $env:PLATFORMIO_CORE_DIR
try {
    Write-Host "Staging UWB build in $stage"
    New-Item -ItemType Directory -Path "$stage\p" -Force | Out-Null
    foreach ($entry in @('src', 'include', 'platformio.ini')) {
        Copy-Item -LiteralPath "$repository\firmware\uwb_multi_test\$entry" -Destination "$stage\p\$entry" -Recurse
    }
    if ($CompileTestWifi) {
        # Never changes the real ignored configuration. Forces linker inclusion
        # of the HTTP task using dummy credentials, in a separate artifact tree.
        @'
#define HANMIR_WIFI_SSID "UWB-COMPILE-TEST-ONLY"
#define HANMIR_WIFI_PASSWORD "dummy-not-a-real-password"
#define HANMIR_SERVER_URL "http://192.0.2.1:8000/api/uwb/distances"
'@ | Set-Content -LiteralPath "$stage\p\include\wifi_secrets.h" -Encoding ascii
        New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
        'COMPILE TEST ONLY. Dummy Wi-Fi configuration. DO NOT FLASH.' |
            Set-Content -LiteralPath (Join-Path $OutputDirectory 'DO-NOT-FLASH.txt')
    }
    Copy-Item -LiteralPath "$repository\firmware\lib" -Destination "$stage\lib" -Recurse
    New-Item -ItemType Directory -Path "$stage\c" -Force | Out-Null
    foreach ($folder in @('platforms', 'packages')) {
        & robocopy "$repository\.pio-core\$folder" "$stage\c\$folder" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
        if ($LASTEXITCODE -ge 8) { throw "Copying PlatformIO $folder failed" }
    }
    $env:PLATFORMIO_CORE_DIR = "$stage\c"
    $arguments = @('-m', 'platformio', 'run', '-d', "$stage\p")
    foreach ($environment in $Environments) { $arguments += @('-e', $environment) }
    & "$repository\.venv\Scripts\python.exe" @arguments
    if ($LASTEXITCODE -ne 0) { throw 'UWB firmware build failed' }
    foreach ($environment in $Environments) {
        $output = Join-Path $OutputDirectory $environment
        New-Item -ItemType Directory -Path $output -Force | Out-Null
        foreach ($file in @('firmware.bin', 'firmware.elf', 'bootloader.bin', 'partitions.bin')) {
            Copy-Item -LiteralPath "$stage\p\.pio\build\$environment\$file" -Destination (Join-Path $output $file) -Force
        }
        Write-Host "Build artifacts saved to $output"
    }
} finally {
    $env:PLATFORMIO_CORE_DIR = $previousCore
    # Only remove this script's unique staging folder, never an input/workspace.
    $resolved = [IO.Path]::GetFullPath($stage)
    if ($resolved -match '^C:\\Windows\\Temp\\u-[0-9a-f]{8}$' -and (Test-Path -LiteralPath $resolved)) {
        try { Remove-Item -LiteralPath $resolved -Recurse -Force }
        catch { Write-Warning "Could not remove staging directory $resolved : $_" }
    }
}
