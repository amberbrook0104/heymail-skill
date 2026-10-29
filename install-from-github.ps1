param(
    [ValidateSet('codex','claude','doubao','workbuddy')][string]$Agent='codex',
    [string]$Version='v1.4.2',
    [string]$Destination='',
    [switch]$Replace
)
$ErrorActionPreference='Stop'
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
if($Version -notmatch '^v[0-9]+\.[0-9]+(?:\.[0-9]+)?$'){throw 'Invalid release version'}
$release=Invoke-RestMethod -Uri ('https://api.github.com/repos/amberbrook0104/heymail-skill/releases/tags/'+$Version)
$asset=@($release.assets | Where-Object name -eq ('heymail-'+$Version+'.zip'))
if($asset.Count -ne 1 -or $asset[0].digest -notmatch '^sha256:[a-f0-9]{64}$'){throw 'Release or verified package is unavailable'}
$downloadUrl=[string]$asset[0].browser_download_url
if(-not $downloadUrl.StartsWith('https://github.com/amberbrook0104/heymail-skill/releases/download/')){throw 'Unexpected download origin'}
$downloadRoot=Join-Path ([IO.Path]::GetTempPath()) ('heymail-install-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $downloadRoot | Out-Null
$archive=Join-Path $downloadRoot 'package.zip'
Invoke-WebRequest -UseBasicParsing -Uri $downloadUrl -OutFile $archive
$stream=[IO.File]::OpenRead($archive);$algorithm=[Security.Cryptography.SHA256]::Create()
try{$actualHash=[BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant()}finally{$stream.Dispose();$algorithm.Dispose()}
if(('sha256:'+$actualHash) -ne $asset[0].digest){throw 'Download checksum mismatch'}
Expand-Archive -LiteralPath $archive -DestinationPath $downloadRoot
$installer=Join-Path $downloadRoot ('heymail-skill-'+$Version+'\install.ps1')
if(-not (Test-Path -LiteralPath $installer)){throw 'Package layout is invalid'}
$installArgs=@{Agent=$Agent}
if($Replace){$installArgs.Replace=$true}
if($Destination){$installArgs.Destination=$Destination}
& $installer @installArgs
Write-Output ('Downloaded package retained at: '+$downloadRoot)
