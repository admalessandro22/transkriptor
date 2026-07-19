param(
    [Parameter(Mandatory = $true)][string]$Pythonw,
    [Parameter(Mandatory = $true)][string]$Aplicativo,
    [Parameter(Mandatory = $true)][string]$Icone,
    [string]$Destino = ""
)

$ErrorActionPreference = "Stop"

$Pythonw = (Resolve-Path -LiteralPath $Pythonw).Path
$Aplicativo = (Resolve-Path -LiteralPath $Aplicativo).Path
$Icone = (Resolve-Path -LiteralPath $Icone).Path

if (-not $Destino) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    if (-not $desktop) {
        throw "Pasta da Area de Trabalho nao encontrada."
    }
    $Destino = Join-Path $desktop "Transkriptor.lnk"
}

$Destino = [IO.Path]::GetFullPath($Destino)
$pastaDestino = Split-Path -Parent $Destino
if (-not (Test-Path -LiteralPath $pastaDestino -PathType Container)) {
    New-Item -ItemType Directory -Path $pastaDestino -Force | Out-Null
}

$shell = New-Object -ComObject WScript.Shell
$atalho = $shell.CreateShortcut($Destino)
$atalho.TargetPath = $Pythonw
$atalho.Arguments = '"' + $Aplicativo + '"'
$atalho.WorkingDirectory = Split-Path -Parent $Aplicativo
$atalho.IconLocation = $Icone
$atalho.Description = "Transkriptor - Transcricao automatica de Google Meet"
$atalho.WindowStyle = 7
# FR-3.6: não usar Hotkey do .lnk (Ctrl+Alt legado); ativação é Ctrl+Espaço no app
$atalho.Hotkey = ""
$atalho.Save()

if (-not (Test-Path -LiteralPath $Destino -PathType Leaf)) {
    throw "O atalho nao foi criado."
}

Write-Output $Destino
