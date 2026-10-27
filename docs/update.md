# 已有用户原地更新到 heymail v1.3

适用于已安装、已配置过邮箱或已有投递记录的用户。首次使用请走[首次安装](first-install.md)。

## 更新步骤

1. 保存并关闭正在编辑的台账。
2. 下载[v1.3完整安装包](https://github.com/amberbrook0104/heymail-skill/releases/download/v1.3/heymail-v1.3.zip)，解压到新的临时目录。
3. 先定位当前正在使用的技能目录，再在新版包中运行对应命令：

```powershell
# 自动查找单一Codex旧安装并原地替换
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Agent codex -Replace

# 豆包Default Profile
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Agent doubao -Replace

# 已知自定义目录时明确指定，避免装出第二份
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Destination "现有技能目录\heymail" -Replace
```

安装器先备份旧技能，然后只复制技能源文件；不会改邮箱配置、凭据、简历或共享台账。Codex同时存在`.agents/skills/heymail`和`.codex/skills/heymail`时会停止，需用`-Destination`明确本次目标。不要为了升级迁移已有目录或重新提交授权码。

## 可直接复制给Agent的提示词

```text
请把现有 heymail 原地更新到 https://github.com/amberbrook0104/heymail-skill 的 v1.3 完整版。

先定位本客户端实际使用的heymail目录并比较版本，备份后替换技能文件，不要重复安装第二份。若我同时使用Codex和豆包，只同步我已经安装的这两份，不创建其他客户端安装。

保留发件邮箱、Windows凭据、默认简历、历史manifest/receipt、共享台账目录，以及我在Excel中修改的公司、岗位、地点、进展、跟进日期和备注。不要索取新的授权码，不发送测试邮件，也不要为补台账而重发旧邮件。

更新后重新读取SKILL.md和台账定稿规范。检查台账运行时；已有tracker配置沿用原目录，缺失时再让我选择共享目录和核实依赖。Codex和豆包共用同一份台账，但各自的邮箱、凭据和简历设置保持原样。

请运行tracker-sync和tracker-shortcut，确认台账为8列、投递时间倒序、社科大风格、表内不显示姓名，桌面入口指向自动更新的原文件。文件作者元数据取发件配置姓名。

如果需要回填旧投递，先让我提供旧回执目录；以实际回执为准，测试邮件和未发送草稿不算正式投递。公司、岗位、地点无法核实时标为待确认，不能凭邮箱域名猜填。旧稿的邮件、附件和确认摘要不擅自修改。

只更新本机技能和台账，不把个人资料上传GitHub。最后报告更新的路径、版本、台账路径和验证结果。
```

## 核对结果

- 技能`metadata.version`为`1.3`，完整包中有`tracker.py`、`tracker_export.mjs`、`tracker-shortcut.ps1`及`references/tracker.md`。
- 已有账户可继续使用，原授权码仍在凭据管理器。
- 台账目录和人工字段保留；新投递会自动登记实际Agent。
- Excel打开造成刷新失败时，保留回执与事件，关闭Excel后再运行`tracker-sync`。不能因台账失败重发邮件。

更新操作本身不授权发送任何求职邮件。发送仍需完整预览之后新的独立「发送」。
