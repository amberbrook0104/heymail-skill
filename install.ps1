param(
    [ValidateSet('codex','claude','doubao')][string]$Agent = 'codex',
    [string]$Destination = '',
    [string]$BackupDirectory = '',
    [switch]$Replace
)
$ErrorActionPreference = 'Stop'
function Get-HeymailSha256([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','') }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}
$heymailSource = Join-Path $PSScriptRoot 'heymail'
if (-not (Test-Path -LiteralPath (Join-Path $heymailSource 'SKILL.md'))) {
    throw '请保留完整仓库结构后运行安装器。'
}
$heymailProfile = [Environment]::GetFolderPath('UserProfile')
if (-not $Destination) {
    if ($Agent -eq 'codex') {
        $heymailCandidates = @(
            (Join-Path $heymailProfile '.agents\skills\heymail'),
            (Join-Path $heymailProfile '.codex\skills\heymail')
        )
        $heymailExisting = @($heymailCandidates | Where-Object { Test-Path -LiteralPath (Join-Path $_ 'SKILL.md') })
        if ($heymailExisting.Count -gt 1) { throw '发现两份 heymail，请用 -Destination 指定本次要更新的目录，避免重复安装。' }
        $Destination = if ($heymailExisting.Count -eq 1) { $heymailExisting[0] } else { $heymailCandidates[0] }
    } elseif ($Agent -eq 'claude') {
        $Destination = Join-Path $heymailProfile '.claude\skills\heymail'
    } else {
        $Destination = Join-Path $heymailProfile 'AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills\heymail'
    }
}
$Destination = [IO.Path]::GetFullPath($Destination)
if ($Destination -ieq [IO.Path]::GetFullPath($heymailSource)) { throw '安装源与目标不能相同，请在完整仓库中运行安装器。' }
if (Test-Path -LiteralPath $Destination) {
    if (-not $Replace) { throw '目标已存在；如要升级，请加 -Replace。' }
    if ((Get-Item -LiteralPath $Destination).LinkType) { throw '目标是链接，请先核对实际目标，避免意外覆盖。' }
    if (-not $BackupDirectory) { $BackupDirectory = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'HeyMail\skill-backups' }
    $heymailBackup = Join-Path ([IO.Path]::GetFullPath($BackupDirectory)) ([guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path (Split-Path -Parent $heymailBackup) -Force | Out-Null
    Copy-Item -LiteralPath $Destination -Destination $heymailBackup -Recurse
    Write-Output ('旧版备份：' + $heymailBackup)
}
Get-ChildItem -LiteralPath $heymailSource -Recurse -File | Where-Object {
    $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and $_.Extension -ne '.pyc'
} | ForEach-Object {
    $heymailRelativeFile = $_.FullName.Substring($heymailSource.Length).TrimStart('\','/')
    $heymailTargetFile = Join-Path $Destination $heymailRelativeFile
    New-Item -ItemType Directory -Path (Split-Path -Parent $heymailTargetFile) -Force | Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $heymailTargetFile -Force
    if ((Get-HeymailSha256 $_.FullName) -ne (Get-HeymailSha256 $heymailTargetFile)) {
        throw '复制校验失败。'
    }
}
Write-Output ('已安装：' + $Destination)
Write-Output '刷新技能列表或重新打开聊天。首次安装见 docs/first-install.md，已有用户更新见 docs/update.md。'

