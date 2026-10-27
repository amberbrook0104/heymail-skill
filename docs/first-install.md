# 首次安装 heymail v1.3

适用于尚未安装或尚未配置heymail的用户。已有账号、简历或台账时，请走[已有用户更新](update.md)，不要重复创建一份同名技能。

## 下载与安装

1. 下载[heymail v1.3安装包](https://github.com/amberbrook0104/heymail-skill/releases/download/v1.3/heymail-v1.3.zip)，完整解压。
   包内`heymail/assets/templates/application-ledger.xlsx`为不含记录的空白台账模板，也可[单独下载](https://github.com/amberbrook0104/heymail-skill/releases/download/v1.3/application-ledger.xlsx)。自动登记的实时台账在配置共享目录后生成。
2. 进入包含`install.ps1`和`heymail/`的目录，按实际客户端选择一条命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Agent codex
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Agent doubao
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Agent claude
```

安装器会显示实际目标目录。Codex新用户默认使用`%USERPROFILE%\.agents\skills\heymail`，发现单一旧安装时沿用旧位置。豆包默认使用：

```text
%USERPROFILE%\AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills\heymail
```

自定义配置、不同豆包Profile或其他目录，请加`-Destination "实际技能目录\heymail"`。如果提示目标已存在，先核对是否应走更新入口。

## 可直接复制给Agent的提示词

```text
请安装并使用 https://github.com/amberbrook0104/heymail-skill 的 v1.3 版 heymail，使用完整安装包，不要只复制 SKILL.md。

先检查本客户端是否已经安装heymail及已有邮箱配置，避免重复安装。技能路径以本机实际目录为准，保留安装器显示的结果。

我是首次使用。请读SKILL.md，按以下顺序推进：先启动本机安全授权码输入；保存成功后再让我提供PDF/DOCX简历；最后再提供发件邮箱。不要让我把授权码发到聊天，也不要一次索取全部资料。配置后只验证SMTP登录，不发送测试邮件。

请检查共享Excel台账所需的Node与Artifact Tool运行时。依赖可用时，再让我选择台账保存目录；如果我同时用Codex和豆包，两边指向同一个目录，保留各自邮箱和简历设置。生成9列、时间倒序、社科大风格的台账，表内不显示姓名；文件作者元数据使用发件配置中的真实姓名。然后运行tracker-shortcut，在桌面创建指向实时台账的快捷方式。如果依赖不可用，请明确说明台账尚未启用，不要虚称成功。

以后我提供JD后，请基于真实简历准备主题、正文和附件，逐一展示预览；只有我之后单独回复“发送”时再投递，并自动登记实际投递Agent。个人资料与台账只保存在本机，不上传GitHub。
```

## 配置完成后

Codex调用`$heymail`，或在`/skills`中选择；豆包要求使用已安装的heymail技能。技能变更未显示时刷新技能列表或重新打开聊天。

台账开启后，`tracker-sync`只刷新Excel；`tracker-shortcut`只创建桌面入口。邮件预览中收件人、主题、正文和全部附件都需核对，再独立回复「发送」。

常用运行命令和配置字段见[执行说明](../heymail/references/usage.md)。
