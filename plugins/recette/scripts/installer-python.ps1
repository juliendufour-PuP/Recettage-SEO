# Python pour la recette SEO, sans rien installer à la main (Windows).
# 1. Un Python 3.10+ déjà présent sur le poste est utilisé tel quel.
# 2. Sinon, un Python privé (python-build-standalone, version figée, empreinte vérifiée) est
#    téléchargé une fois dans %USERPROFILE%\.claude\recettage-seo\python : sans droits
#    administrateur, sans toucher au PATH ni au reste du poste.
# Dernière ligne affichée : PY=<commande à utiliser>.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Tester($commande, $arguments) {
    try {
        $sortie = & $commande @arguments -c "import sys; print('ok' if sys.version_info >= (3, 10) else 'vieux')" 2>$null
        return ($LASTEXITCODE -eq 0 -and "$sortie".Trim() -eq 'ok')
    } catch { return $false }
}

$dest = Join-Path $env:USERPROFILE '.claude\recettage-seo\python'
$prive = Join-Path $dest 'python.exe'
if (Test-Path $prive) { if (Tester $prive @()) { Write-Output "PY=$prive"; exit 0 } }

# « python » peut être le raccourci du Microsoft Store, qui ne lance rien : on teste vraiment.
foreach ($c in @(@{n = 'python'; a = @()}, @{n = 'py'; a = @('-3')}, @{n = 'python3'; a = @()})) {
    $cmd = Get-Command $c.n -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd -and (Tester $cmd.Source $c.a)) {
        Write-Output ("PY=" + ((@("`"$($cmd.Source)`"") + $c.a) -join ' ')); exit 0
    }
}

$version = '20261021'
if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
    $nom = "cpython-3.12.15+$version-aarch64-pc-windows-msvc-install_only.tar.gz"
    $empreinte = 'c0660992e1907a8dc31e9069676b1415d585b53f17d0aa7e9075f4b06f38fd65'
} else {
    $nom = "cpython-3.12.15+$version-x86_64-pc-windows-msvc-install_only.tar.gz"
    $empreinte = 'be7f14464d1d66f84429ad27e01f6d1482963afff64a2fb5256b2a51c7b5d398'
}
$url = "https://github.com/astral-sh/python-build-standalone/releases/download/$version/" + $nom.Replace('+', '%2B')

Write-Output "Python absent : téléchargement d'un Python privé pour la recette (45 Mo environ, une seule fois)..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$tmp = Join-Path $env:TEMP ("recette-python-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $tmp | Out-Null
try {
    $archive = Join-Path $tmp 'python.tar.gz'
    try {
        Invoke-WebRequest -Uri $url -OutFile $archive -UseBasicParsing
    } catch {
        Write-Output "ECHEC: téléchargement impossible ($($_.Exception.Message)). Un pare-feu ou un antivirus bloque peut-être github.com : installe Python depuis https://www.python.org/downloads/ en cochant « Add python.exe to PATH », puis relance."
        exit 1
    }
    $calcul = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLower()
    if ($calcul -ne $empreinte) {
        Write-Output "ECHEC: le fichier téléchargé n'a pas l'empreinte attendue : rien n'a été installé."
        exit 1
    }
    & tar.exe -xzf $archive -C $tmp
    if ($LASTEXITCODE -ne 0) { Write-Output "ECHEC: décompression impossible (tar.exe)."; exit 1 }
    New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    Move-Item (Join-Path $tmp 'python') $dest
} finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
if (-not (Tester $prive @())) { Write-Output "ECHEC: le Python privé ne démarre pas."; exit 1 }
Write-Output "Python privé installé."
Write-Output "PY=$prive"
