param([string]$Version)
$ErrorActionPreference = 'Stop'
$smokeRoot = Split-Path $PSScriptRoot -Parent
if (!$Version) {
    $smokeVersionLine = Get-Content -LiteralPath (Join-Path $smokeRoot 'Config\DefaultGame.ini') |
        Where-Object { $_ -match '^ProjectVersion=' } | Select-Object -First 1
    $Version = $smokeVersionLine.Substring('ProjectVersion='.Length).Trim()
}
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid project version: $Version" }
$smokeExe = Join-Path $smokeRoot "Builds\$Version\Windows\Dostoevsky\Binaries\Win64\Dostoevsky.exe"
if (!(Test-Path -LiteralPath $smokeExe)) { throw "Packaged executable not found: $smokeExe" }
$smokeFolder = Join-Path $smokeRoot "Saved\PackageChecks\$Version"
New-Item -ItemType Directory -Path $smokeFolder -Force | Out-Null
$smokeMaps = @('L_DimaApartmentInterior','L_NeptuneStreet','L_BrightonGrocery','L_LighthouseBar',
    'L_PolicePrecinct','L_FedorEntry','L_FedorApartment','L_BrightonAlley')
$smokeResults = @()
foreach ($smokeMap in $smokeMaps) {
    $smokeLog = Join-Path $smokeFolder "$smokeMap.log"
    $smokeArgs = @("/Game/Locations/$smokeMap",'-unattended','-windowed','-nosplash','-nosound',
        '-d3d11','-NoTrace','-ResX=1280','-ResY=720',('-abslog="'+$smokeLog+'"'),'-ExecCmds="quit"')
    $smokeTimer = [System.Diagnostics.Stopwatch]::StartNew()
    $smokeProcess = Start-Process -FilePath $smokeExe -ArgumentList $smokeArgs -WindowStyle Hidden -PassThru
    if (!$smokeProcess.WaitForExit(45000)) {
        Stop-Process -Id $smokeProcess.Id
        throw "Packaged map did not finish in 45 seconds: $smokeMap"
    }
    $smokeProcess.WaitForExit()
    $smokeTimer.Stop()
    if ($smokeProcess.ExitCode -ne 0) { throw "Packaged map failed: $smokeMap, exit $($smokeProcess.ExitCode)" }
    if (!(Test-Path -LiteralPath $smokeLog)) { throw "Missing packaged log: $smokeMap" }
    $smokeText = Get-Content -LiteralPath $smokeLog -Raw
    if ($smokeText -notmatch ('Bringing World.*'+[regex]::Escape($smokeMap))) {
        throw "The requested world did not start: $smokeMap"
    }
    if ($smokeText -match 'Fatal error:|Critical error:|Assertion failed:|ACT_MISSING') {
        throw "Runtime error in packaged map: $smokeMap"
    }
    if ($smokeText -match 'missing usage flag .*Default Material will be used in game') {
        throw "An object rendered with the default material in packaged map: $smokeMap"
    }
    $smokeResults += [pscustomobject]@{Map=$smokeMap;ExitCode=$smokeProcess.ExitCode;
        Seconds=[math]::Round($smokeTimer.Elapsed.TotalSeconds,2);Log=$smokeLog}
    Write-Output "PACKAGED_MAP_OK $smokeMap"
}
$smokeResults | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $smokeFolder 'Smoke.json') -Encoding utf8
Write-Output "PACKAGED_LOCATIONS_OK $Version maps=$($smokeResults.Count)"
