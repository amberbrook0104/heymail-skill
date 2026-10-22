param(
    [ValidateSet('codex','claude')][string]$Agent = 'codex',
    [string]$Destination = '',
    [switch]$Replace
)
$ErrorActionPreference = 'Stop'
$heymailSource = Join-Path $PSScriptRoot 'heymail'
if (-not (Test-Path -LiteralPath (Join-Path $heymailSource 'SKILL.md'))) {
    throw '请保留完整仓库结构后运行安装器。'
}
if (-not $Destination) {
    $heymailRelative = if ($Agent -eq 'claude') { '.claude\skills\heymail' } else { '.codex\skills\heymail' }
    $Destination = Join-Path ([Environment]::GetFolderPath('UserProfile')) $heymailRelative
}
$Destination = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $Destination) {
    if (-not $Replace) { throw '目标已存在；如要升级，请加 -Replace。' }
    if ((Get-Item -LiteralPath $Destination).LinkType) { throw '目标是链接，请先核对实际目标，避免意外覆盖。' }
    $heymailBackup = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) ('HeyMail\skill-backups\' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path (Split-Path -Parent $heymailBackup) -Force | Out-Null
    Copy-Item -LiteralPath $Destination -Destination $heymailBackup -Recurse
}
Get-ChildItem -LiteralPath $heymailSource -Recurse -File | ForEach-Object {
    $heymailRelativeFile = $_.FullName.Substring($heymailSource.Length).TrimStart('\','/')
    $heymailTargetFile = Join-Path $Destination $heymailRelativeFile
    New-Item -ItemType Directory -Path (Split-Path -Parent $heymailTargetFile) -Force | Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $heymailTargetFile -Force
    if ((Get-FileHash -LiteralPath $_.FullName).Hash -ne (Get-FileHash -LiteralPath $heymailTargetFile).Hash) {
        throw '复制校验失败。'
    }
}
Write-Output ('已安装：' + $Destination)
Write-Output '重新打开聊天或刷新技能列表。Codex 用 $heymail，Claude Code 用 /heymail。'
