param(
    [string]$EngineRoot = 'D:\UE_5.8',
    [ValidateSet('Development', 'Shipping')]
    [string]$Configuration = 'Development'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$projectPath = Join-Path $projectRoot 'Dostoevsky.uproject'
$automationTool = Join-Path $EngineRoot 'Engine\Build\BatchFiles\RunUAT.bat'
if (!(Test-Path -LiteralPath $automationTool)) { throw "Unreal RunUAT.bat not found: $automationTool" }
if (Get-Process -Name UnrealEditor, UnrealEditor-Cmd -ErrorAction SilentlyContinue) {
    throw 'Close Unreal Editor before packaging the project.'
}
$versionLine = Get-Content -LiteralPath (Join-Path $projectRoot 'Config\DefaultGame.ini') |
    Where-Object { $_ -match '^ProjectVersion=' } | Select-Object -First 1
if (!$versionLine) { throw 'ProjectVersion is missing from Config/DefaultGame.ini.' }
$projectVersion = $versionLine.Substring('ProjectVersion='.Length).Trim()
if ($projectVersion -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid project version: $projectVersion" }
$archivePath = Join-Path $projectRoot "Builds\$projectVersion"
& $automationTool BuildCookRun "-project=$projectPath" -nop4 -unattended -installed `
    -platform=Win64 "-clientconfig=$Configuration" -build -cook -stage -pak -prereqs -nodebuginfo `
    -archive "-archivedirectory=$archivePath" '-ubtargs=-NoUBA' `
    '-additionalcookeroptions=-SkipZenStore -NoZenAutoLaunch -NoTrace -DDC=InstalledNoZenLocalFallback'
if ($LASTEXITCODE -ne 0) { throw "Unreal packaging failed with exit code $LASTEXITCODE" }
$footstepCredit = Join-Path $projectRoot 'Resources\Brighton\Audio\RECORDED-FOOTSTEPS-LICENSE.txt'
if (Test-Path -LiteralPath $footstepCredit) {
    Copy-Item -LiteralPath $footstepCredit -Destination (Join-Path $archivePath 'Windows\Footsteps-Credits.txt')
}
Write-Output "Packaged game: $archivePath\Windows\Dostoevsky.exe"
