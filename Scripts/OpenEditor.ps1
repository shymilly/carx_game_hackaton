param([string]$EngineRoot = 'D:\UE_5.8')
$ErrorActionPreference = 'Stop'
$projectPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'Dostoevsky.uproject'
$editorPath = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
if (!(Test-Path -LiteralPath $editorPath)) { throw "Unreal Editor not found: $editorPath" }
if (!(Test-Path -LiteralPath $projectPath)) { throw "Project not found: $projectPath" }
Start-Process -FilePath $editorPath -ArgumentList ('"' + $projectPath + '"'), '-LiveCoding=false' -WindowStyle Normal
