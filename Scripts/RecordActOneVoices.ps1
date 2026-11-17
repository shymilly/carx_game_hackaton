$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$spec = Get-Content -Raw -LiteralPath (Join-Path $project 'Docs/Scenario/ActOne.json') | ConvertFrom-Json -AsHashtable
$apartment = Get-Content -Raw -LiteralPath (Join-Path $project 'Docs/Scenario/DimaApartment.json') | ConvertFrom-Json -AsHashtable
$destination = Join-Path $project 'Resources/Audio/ActOne'
New-Item -ItemType Directory -Force -Path $destination | Out-Null
$rawVoices = Join-Path $project 'Saved/ActOne/Unfiltered'
New-Item -ItemType Directory -Force -Path $rawVoices | Out-Null

$profiles = @{
    Dima=@('Pavel',0,0); Nina=@('Irina',-1,-2); Vendor=@('Irina',1,-1)
    Veteran=@('Pavel',-3,-5); Guard=@('Pavel',1,3); Radio=@('Pavel',1,-2)
    Captain=@('Pavel',-1,-4); Ivan=@('Pavel',-1,2); Fedor=@('Pavel',-2,-5)
}
$synth = New-Object -ComObject SAPI.SpVoice
$tokens = @{}
foreach ($name in @('Irina','Pavel')) {
    $token = New-Object -ComObject SAPI.SpObjectToken
    $token.SetId("HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens\MSTTS_V110_ruRU_${name}M",'',$false)
    $tokens[$name] = $token
}

function Write-Line($Id,$Body,$Character) {
    $set = $profiles[$Character]
    $synth.Voice = $tokens[$set[0]]
    $synth.Rate = $set[1]
    $output = New-Object -ComObject SAPI.SpFileStream
    $name = Join-Path $rawVoices ("Voice_" + $Id + ".wav")
    $output.Open($name,3,$false)
    try {
        $synth.AudioOutputStream = $output
        $spoken = [Security.SecurityElement]::Escape($Body)
        [void]$synth.Speak("<pitch middle=`"$($set[2])`">$spoken</pitch>",8)
    } finally { $output.Close() }
    if ((Get-Item -LiteralPath $name).Length -lt 800) { throw "Empty speech take $name" }
    Copy-Item -LiteralPath $name -Destination (Join-Path $destination ("Voice_" + $Id + ".wav")) -Force
}

foreach ($document in $spec.documents.GetEnumerator()) {
    if ($document.Value.voice) { Write-Line $document.Key $document.Value.body $document.Value.voice }
}
foreach ($line in $apartment.documents) {
    if ($line.id -in @('Television','Fridge','Wardrobe','FloorLamp') -or
        ($line.id -like 'Phone*' -and $line.body -ne '-бросила трубку-')) {
        $speaker = if ($line.title -like '*Нина*') {'Nina'} elseif ($line.id -eq 'Television') {'Radio'} else {'Dima'}
        Write-Line ("Apartment_" + $line.id) $line.body $speaker
    }
}
Get-ChildItem -LiteralPath $destination -Filter 'Voice_*.wav' | Measure-Object Length -Sum
