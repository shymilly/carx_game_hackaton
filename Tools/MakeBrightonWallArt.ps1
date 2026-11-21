param(
    [string]$OutputFolder = (Join-Path (Split-Path $PSScriptRoot -Parent) 'Resources/Brighton/Street/WallArt')
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$null = New-Item -ItemType Directory -Path $OutputFolder -Force
function RGB([int]$red,[int]$green,[int]$blue,[int]$alpha=255) {
    [Drawing.Color]::FromArgb($alpha,$red,$green,$blue)
}
function Banner($name,$base,$ink,$head,$sub,$nameFont,$subFont) {
    $image=[Drawing.Bitmap]::new(1024,512)
    $canvas=[Drawing.Graphics]::FromImage($image)
    $canvas.SmoothingMode='AntiAlias'
    $canvas.TextRenderingHint='AntiAliasGridFit'
    $canvas.Clear($base)
    $edge=[Drawing.Pen]::new($ink,4)
    $fill=[Drawing.SolidBrush]::new($ink)
    $canvas.DrawRectangle($edge,30,28,963,455)
    $canvas.DrawRectangle($edge,44,42,935,427)
    $canvas.FillRectangle($fill,101,283,822,3)
    $format=[Drawing.StringFormat]::new()
    $format.Alignment='Center'
    $header=[Drawing.Font]::new($nameFont,92,'Bold','Pixel')
    $byline=[Drawing.Font]::new($subFont,57,'Bold','Pixel')
    $canvas.DrawString($head,$header,$fill,[Drawing.RectangleF]::new(60,127,904,133),$format)
    $canvas.DrawString($sub,$byline,$fill,[Drawing.RectangleF]::new(60,319,904,88),$format)
    $rng=[Random]::new(9414)
    $scuffs=[Drawing.SolidBrush]::new((RGB 64 52 44 10))
    for($point=0;$point -lt 8000;$point++){
        $x=$rng.Next(0,1024)
        $y=$rng.Next(0,512)
        $canvas.FillRectangle($scuffs,$x,$y,$rng.Next(1,5),$rng.Next(1,4))
    }
    $scuffs.Dispose()
    $byline.Dispose()
    $header.Dispose()
    $format.Dispose()
    $fill.Dispose()
    $edge.Dispose()
    $canvas.Dispose()
    $image.Save((Join-Path $OutputFolder $name),[Drawing.Imaging.ImageFormat]::Png)
    $image.Dispose()
}
Banner 'T_BrightonTapeBanner.png' (RGB 28 57 52) (RGB 223 198 147) 'ВИДЕОПРОКАТ' 'VIDEO RENTALS' 'Arial' 'Georgia'
Banner 'T_BrightonSwapBanner.png' (RGB 210 187 143) (RGB 87 44 32) 'БАРАХОЛКА' 'WEEKEND FLEA MARKET' 'Georgia' 'Arial'
$image=[Drawing.Bitmap]::new(1024,384)
$canvas=[Drawing.Graphics]::FromImage($image)
$canvas.SmoothingMode='AntiAlias'
$canvas.Clear([Drawing.Color]::Transparent)
# Hand-drawn paths for the B4 tag. Offset edges and flats break up its outline.
$scribble=@(
    @(124,318,194,69,388,53,438,113,409,171,284,201,410,202,450,249,414,302,305,333,124,318),
    @(191,298,233,110,345,102,361,121,321,155,227,172),
    @(216,229,326,229,353,251,298,285,191,298),
    @(694,50,512,215,506,249,756,226,698,341,800,335,849,214,908,205),
    @(810,60,690,91,627,185,757,173,810,60),
    @(114,349,405,355,623,327,918,300),
    @(57,260,109,244,100,228),
    @(891,96,929,67,965,87)
)
$palette=@((RGB 47 44 47 180),(RGB 157 99 58 220),(RGB 200 166 103 250))
for($pass=0;$pass -lt $palette.Count;$pass++){
    $nib=[Drawing.Pen]::new($palette[$pass],@(29,16,5)[$pass])
    $nib.LineJoin='Round'
    $nib.StartCap='Round'
    $nib.EndCap='Round'
    foreach($path in $scribble){
        $points=for($index=0;$index -lt $path.Count;$index+=2){
            [Drawing.Point]::new(($path[$index]+$pass*3),($path[$index+1]-$pass*2))
        }
        $canvas.DrawLines($nib,[Drawing.Point[]]$points)
    }
    $nib.Dispose()
}
$canvas.Dispose()
$image.Save((Join-Path $OutputFolder 'T_BrightonB4Tag.png'),[Drawing.Imaging.ImageFormat]::Png)
$image.Dispose()
