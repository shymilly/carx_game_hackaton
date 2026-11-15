param(
    [string]$EngineRoot = 'D:\UE_5.8',
    [switch]$GenerateVSCode
)
$ErrorActionPreference = 'Stop'
$projectPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'Dostoevsky.uproject'
$buildPath = Join-Path $EngineRoot 'Engine\Build\BatchFiles\Build.bat'
if (!(Test-Path -LiteralPath $buildPath)) { throw "Unreal Build.bat not found: $buildPath" }
if ($GenerateVSCode) {
    & $buildPath -projectfiles "-project=$projectPath" -game -engine -VSCode
} else {
    & $buildPath DostoevskyEditor Win64 Development "-Project=$projectPath" -WaitMutex -NoUBA
}
if ($LASTEXITCODE -ne 0) { throw "Unreal build failed with exit code $LASTEXITCODE" }
