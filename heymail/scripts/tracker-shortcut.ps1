param(
    [Parameter(Mandatory=$true)][string]$Workbook,
    [string]$DesktopDirectory = ''
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
if (-not (Test-Path -LiteralPath $Workbook -PathType Leaf)) { throw '台账文件不存在，请先运行 tracker-sync。' }
$Workbook = [IO.Path]::GetFullPath($Workbook)
if (-not $DesktopDirectory) { $DesktopDirectory = [Environment]::GetFolderPath('Desktop') }
if (-not (Test-Path -LiteralPath $DesktopDirectory -PathType Container)) { throw '桌面目录不存在。' }
$DesktopDirectory = [IO.Path]::GetFullPath($DesktopDirectory)
$shortcutShell = New-Object -ComObject WScript.Shell
$shortcutPath = Join-Path $DesktopDirectory '实习投递台账.lnk'
$index = 1
while (Test-Path -LiteralPath $shortcutPath) {
    $existing = $shortcutShell.CreateShortcut($shortcutPath)
    if ($existing.TargetPath -ieq $Workbook) { break }
    $label = if ($index -eq 1) { '实习投递台账（实时）.lnk' } else { '实习投递台账（实时' + $index + '）.lnk' }
    $shortcutPath = Join-Path $DesktopDirectory $label
    $index++
}
$shortcut = $shortcutShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $Workbook
$shortcut.WorkingDirectory = Split-Path -Parent $Workbook
$shortcut.Description = '打开持续自动更新的实习投递台账'
$shortcut.Save()
$verified = $shortcutShell.CreateShortcut($shortcutPath)
if (-not (Test-Path -LiteralPath $shortcutPath) -or $verified.TargetPath -ine $Workbook) { throw '快捷方式校验失败。' }
[pscustomobject]@{shortcut=$shortcutPath; target=$Workbook} | ConvertTo-Json -Compress
