param(
    [Parameter(Mandatory=$true)][ValidateSet('163','qq')][string]$Provider,
    [Parameter(Mandatory=$true)][string]$Email,
    [string]$CredentialTarget = '',
    [switch]$CheckOnly
)
$mailExpectedDomain = if ($Provider -eq '163') { '163.com' } else { 'qq.com' }
if ($Email -notmatch '^[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+$' -or $Email.Split('@')[-1].ToLowerInvariant() -ne $mailExpectedDomain) {
    throw '邮箱地址与所选供应商不匹配。'
}
if ($CredentialTarget -match '[\r\n\x00]') { throw '凭据目标名称无效。' }


$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security;

public static class HeyMailCredentialStore {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct CREDENTIAL {
        public uint Flags;
        public uint Type;
        public string TargetName;
        public string Comment;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
        public uint CredentialBlobSize;
        public IntPtr CredentialBlob;
        public uint Persist;
        public uint AttributeCount;
        public IntPtr Attributes;
        public string TargetAlias;
        public string UserName;
    }
    [DllImport("advapi32.dll", EntryPoint = "CredWriteW", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CredWrite(ref CREDENTIAL credential, uint flags);
    [DllImport("advapi32.dll", EntryPoint = "CredReadW", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CredRead(string target, uint type, uint flags, out IntPtr credential);
    [DllImport("advapi32.dll")]
    private static extern void CredFree(IntPtr credential);

    public static void Save(string target, string account, SecureString secret) {
        IntPtr blob = Marshal.SecureStringToCoTaskMemUnicode(secret);
        try {
            CREDENTIAL item = new CREDENTIAL();
            item.Type = 1;
            item.TargetName = target;
            item.Comment = "HeyMail SMTP authorization code";
            item.CredentialBlobSize = checked((uint)(secret.Length * 2));
            item.CredentialBlob = blob;
            item.Persist = 2;
            item.UserName = account;
            if (!CredWrite(ref item, 0)) throw new Win32Exception(Marshal.GetLastWin32Error());
        } finally { Marshal.ZeroFreeCoTaskMemUnicode(blob); }
    }
    public static bool Exists(string target) {
        IntPtr item;
        if (!CredRead(target, 1, 0, out item)) return false;
        CredFree(item);
        return true;
    }
}
'@

$mailCredentialTarget = if ($CredentialTarget) { $CredentialTarget } else { "HeyMail/$Provider/$Email" }
if ($CheckOnly) {
    [pscustomobject]@{
        Compiled = $true
        CredentialSaved = [HeyMailCredentialStore]::Exists($mailCredentialTarget)
    } | ConvertTo-Json
    exit
}

[System.Windows.Forms.Application]::EnableVisualStyles()
$mailCredentialForm = New-Object System.Windows.Forms.Form
$mailCredentialForm.Text = 'HeyMail 邮箱授权码 - 本机安全保存'
$mailCredentialForm.ClientSize = New-Object System.Drawing.Size(530, 240)
$mailCredentialForm.StartPosition = 'CenterScreen'
$mailCredentialForm.FormBorderStyle = 'FixedDialog'
$mailCredentialForm.MaximizeBox = $false
$mailCredentialForm.MinimizeBox = $false
$mailCredentialForm.TopMost = $true
$mailCredentialForm.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 10)

$mailCredentialLabel = New-Object System.Windows.Forms.Label
$mailCredentialLabel.Location = New-Object System.Drawing.Point(22, 18)
$mailCredentialLabel.Size = New-Object System.Drawing.Size(486, 75)
$mailCredentialLabel.Text = "账号：$Email`r`n请填写所选邮箱的 SMTP 授权码（不是登录密码）。`r`n仅保存到当前 Windows 用户的凭据管理器；此窗口不会发邮件。"
$mailCredentialForm.Controls.Add($mailCredentialLabel)

$mailCredentialBox = New-Object System.Windows.Forms.TextBox
$mailCredentialBox.Location = New-Object System.Drawing.Point(24, 105)
$mailCredentialBox.Size = New-Object System.Drawing.Size(478, 30)
$mailCredentialBox.UseSystemPasswordChar = $true
$mailCredentialBox.MaxLength = 128
$mailCredentialForm.Controls.Add($mailCredentialBox)

$mailCredentialSaveButton = New-Object System.Windows.Forms.Button
$mailCredentialSaveButton.Text = '安全保存'
$mailCredentialSaveButton.Location = New-Object System.Drawing.Point(274, 170)
$mailCredentialSaveButton.Size = New-Object System.Drawing.Size(110, 36)
$mailCredentialForm.Controls.Add($mailCredentialSaveButton)
$mailCredentialCancelButton = New-Object System.Windows.Forms.Button
$mailCredentialCancelButton.Text = '取消'
$mailCredentialCancelButton.Location = New-Object System.Drawing.Point(394, 170)
$mailCredentialCancelButton.Size = New-Object System.Drawing.Size(108, 36)
$mailCredentialCancelButton.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$mailCredentialForm.Controls.Add($mailCredentialCancelButton)
$mailCredentialForm.CancelButton = $mailCredentialCancelButton
$mailCredentialForm.AcceptButton = $mailCredentialSaveButton

$mailCredentialSaveButton.Add_Click({
    if ([string]::IsNullOrWhiteSpace($mailCredentialBox.Text)) {
        [System.Windows.Forms.MessageBox]::Show('请先填写 SMTP 授权码。', '尚未填写') | Out-Null
        return
    }
    $mailCredentialSecret = ConvertTo-SecureString -String $mailCredentialBox.Text.Trim() -AsPlainText -Force
    try {
        [HeyMailCredentialStore]::Save($mailCredentialTarget, $Email, $mailCredentialSecret)
        $mailCredentialBox.Clear()
        [System.Windows.Forms.MessageBox]::Show('已保存到 Windows 凭据管理器。可返回 Codex 告知“已保存”。', '保存成功') | Out-Null
        $mailCredentialForm.Close()
    } catch {
        [System.Windows.Forms.MessageBox]::Show('保存未完成，请关闭窗口并告知 Codex。授权码没有写入文件。', '保存失败') | Out-Null
    } finally {
        $mailCredentialSecret.Dispose()
    }
})
$mailCredentialForm.Add_Shown({ $mailCredentialBox.Focus() })
try { $mailCredentialForm.ShowDialog() | Out-Null }
finally { $mailCredentialBox.Clear(); $mailCredentialForm.Dispose() }
