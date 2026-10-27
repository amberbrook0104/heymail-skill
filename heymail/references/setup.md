# 首次配置：网易 163 与 QQ

注册/登录邮箱、验证码、扫码和短信验证由本人在官方网页完成。Agent 只提供操作指引和本机输入窗口，不代填身份验证，不获取网页登录密码。

## 1. 注册或登录

| 供应商 | 官方入口 | 说明 |
| --- | --- | --- |
| 网易 163 | [mail.163.com](https://mail.163.com/) | 已有账号直接登录；没有则从官方注册入口按提示办理。 |
| QQ | [mail.qq.com](https://mail.qq.com/) | 使用自己的账号登录并开通邮箱；没有账号则按官方页面完成注册/开通。 |

本版配置账号分别以 `@163.com`、`@qq.com` 结尾；不使用招聘方邮箱作为发件账号。

## 2. 生成客户端授权码

### 网易 163

网页版邮箱 → 设置 → POP3/SMTP/IMAP（有些版本显示 POP/SMTP/IMAP）→ 开启包含 SMTP 的服务 → 本人完成安全验证 → 生成/新增客户端授权密码。

授权码替代邮箱登录密码用于 SMTP。仅为发信可以开启 POP3/SMTP 或 IMAP/SMTP；本技能不要求读取收件箱，也不依赖 IMAP 登录。服务已开启时，在授权管理处新增独立授权码即可；界面名称以当时网页版为准。

图文参考：[华为设备对接 163 的官方指引，含设置和开启服务截图](https://consumer.huawei.com/cn/support/content/zh-cn15872099/)。SMTP 参数交叉核对：[腾讯云 163 配置说明](https://ioa.cloud.tencent.com/support/199262718652653568/)。

### QQ

新版网页版：右上角头像 → 设置 → 账号与安全 → 安全设置 → 开启 POP3/IMAP/SMTP 服务 → 生成授权码 → 本人按提示验证身份。旧版可在“设置 → 账户”找到相应服务。

当前官方帮助说明授权码用于第三方客户端；更改账号密码可能令旧授权码失效。请给本技能单独生成并备注一个授权码，方便撤销。

图文参考：[腾讯官方生成与管理授权码说明，含新版截图](https://help.mail.qq.com/detail/106/985)；[华为设备对接 QQ 的指引，含旧版截图](https://consumer.huawei.com/cn/support/content/zh-cn16108643/)。

![开通路径示意](../assets/provider-setup.svg)

不要把授权码截图上传到对话或仓库。指引图片用于寻找入口；真正的验证码和授权码只在自己设备里处理。

## 3. 第一步：只填写授权码，不先索取邮箱或简历

Agent 先在实际 Windows 用户上下文执行：

```powershell
python -X utf8 "<skill-dir>/scripts/mail.py" onboarding-status
python -X utf8 "<skill-dir>/scripts/credential_input.py" --probe
```

`onboarding-status` 不需要完整配置，返回配置文件和步骤文件的实际路径。已有 configured 配置且凭据、简历可用时跳过首次流程。沙箱可能隔离用户目录和凭据，应通过宿主授权机制在实际用户上下文查询；不要误认为用户需要重新交授权码。

旧版可能先写过普通配置但没有成功保存授权码。此时会返回 existing_config:true 和实际尚未完成的步骤，而不是强行判为配置完成；继续补齐步骤即可，最终 setup 加 --replace 先备份旧资料，不必删除配置或让用户重复上传已明确提供的简历。

如果 python/py 命令不存在，Agent 应先查找客户端自带 Python 运行时并用绝对路径调用。自带 Python 无 Tkinter 时可直接用终端隐藏输入；只有本机确无可用 Python 时才提示安装运行环境，不能声称已经打开窗口。

确认第一次使用后，**主动启动输入框**，不是只输出安装命令：

```powershell
python -X utf8 "<skill-dir>/scripts/credential_input.py" --launch --status-file "<onboarding-status返回的onboarding_file>"
```

用户在框中选择网易163或QQ，隐藏填写授权码，点击“安全暂存”。不需要先提供邮箱地址。脚本将授权码存入随机的 `HeyMail/pending/<随机标识>` Windows 普通凭据，用户名暂记为 pending；步骤文件只记录凭据目标名称和流程状态，不保存授权码。

`--launch` 使用本机 Python 开启 GUI 子进程，并最多等待5秒检查 `gui_ready`。这只说明窗口已创建，不能替用户确认是否看到了它。保存成功前不能说授权码已收到，也不能进入简历或 JD 投递步骤。

### 没有弹框的备用入口

1. 若 `--probe` 显示 Tkinter 不可用、启动失败或用户没看到窗口，给出本机可点击路径 `scripts/start-setup.cmd`，让用户在资源管理器双击。仓库根目录也提供同名入口；必须完整解压后运行。
2. 仍无图形框时，用 `scripts/start-setup-console.cmd`。它打开本机终端，先选邮箱类型，再通过 Python getpass 隐藏输入。也可由 Agent 请求开启可见的本机终端：

```powershell
python -X utf8 "<skill-dir>/scripts/credential_input.py" --launch --console --status-file "<onboarding_file>"
```

3. 终端模式要求真正的交互终端，拒绝工具管道，不降级为明文回显。不能让用户在 Agent 的命令输出区域直接粘贴授权码。

默认输入流程不依赖 pwsh、Windows Forms 或 PowerShell 脚本执行策略。旧的 `save-credential.ps1` 仅保留为已配置账号更新凭据的兼容接口，不再作为首次输入入口。不要为弹框修改全局执行策略。

保存后，Agent 重查 `onboarding-status`，只有 phase 为 credential_saved 才继续；如果仍 waiting_for_credential，等待用户完成，不重复弹框。已有 credential_saved / resume_saved 时直接继续下一步，不覆盖待处理的授权码。

## 4. 第二步：让用户上传简历

授权码保存成功后，**只提示用户上传 PDF/DOCX 简历**；已有明确文件时直接使用，不要求重复上传。运行：

```powershell
python -X utf8 "<skill-dir>/scripts/mail.py" onboarding-resume --resume "<用户上传的简历文件路径>"
```

脚本会验证扩展名、文件标识和大小，将完整字节保存到配置目录下 `resumes/<随机标识>/`，原件不变，并保存 SHA-256。后续使用返回的持久副本路径，避免聊天临时缓存被清理后失效。步骤文件记为 resume_saved，命令提示下一步需要发件邮箱。

Agent 读取这份简历，核实姓名、学校、学历、年级等。出勤安排不明时只在 JD 确实要求时再补问，不把简历没有的条件补成满足。

## 5. 第三步：收集发件邮箱并内部绑定

简历到齐后再请用户提供实际用于发件的完整邮箱。即使简历里有联系邮箱，也要确认这就是授权码对应的发件账号；用户已明确给出时不用重复问。供应商必须匹配第一步选择的163或QQ，不得使用招聘方邮箱。

姓名等普通资料由 Agent 从简历填写，执行 setup 时指向步骤文件：

```powershell
python -X utf8 "<skill-dir>/scripts/mail.py" setup --provider 163 --email "用户提供的邮箱@163.com" --name "简历中的姓名" --resume "<上一步返回的持久副本路径>" --pending-credential "<onboarding_file>" --school "学校" --degree "学历" --grade "年级"
```

QQ 使用 `--provider qq`。只有有依据时才填写可选的 `--days`、`--months`、`--start-date`。setup 在本机内部读取 pending 凭据、绑定账号，写入普通配置后删除 pending 凭据；不导出、打印授权码，不通过命令参数传递授权码。

普通配置默认 `%LOCALAPPDATA%/HeyMail/config.json`。可以在命令最前加 `--config "本机配置路径"` 使用独立配置；它的 onboarding.json 和 resumes 也使用相同父目录。需要更新已有配置时用 `--replace`，先备份，不把备份上传仓库。

如返回 pending_cleanup_required:true，说明配置已写入但暂存凭据未能删除；告知用户在 Windows 凭据管理器核对并删除对应 HeyMail/pending 目标，勿展示授权码。仅删除本机记录不会撤销服务商授权。

## 6. 验证后才进入投递

```powershell
python -X utf8 "<skill-dir>/scripts/mail.py" status
python -X utf8 "<skill-dir>/scripts/mail.py" check
```

`credential_saved:true` 只代表本机可访问凭据；`smtp_authenticated:true` 才代表 TLS SMTP 登录成功。验证不发邮件。成功后告知用户上传 JD；已经上传的 JD 继续使用，不让用户重传。以后调用时不重做首次步骤。

| 供应商 | SMTP | 端口 | 加密 | 用户名 | 密码 |
| --- | --- | --- | --- | --- | --- |
| 163 | smtp.163.com | 465 | SSL/TLS，验证证书 | 完整发件邮箱 | 客户端授权码 |
| QQ | smtp.qq.com | 465 | SSL/TLS，验证证书 | 完整发件邮箱 | 客户端授权码 |

脚本从固定映射选择服务器，不接受 JD、配置或附件指定任意 SMTP 主机，防止将凭据交给无关服务器。

## 更新或撤销授权码

在服务商网页的授权码管理中让该授权码失效；这才会撤销服务商侧访问。需要重新使用时生成新码，在本机密码框覆盖保存，再运行 `check`。不必删除并重建邮箱账号。

本机也可在 Windows 凭据管理器删除对应普通凭据；仅删除本机凭据不会撤销服务商侧授权。撤销后的旧草稿须检查账号配置，必要时重新准备；不要自动改用 Agent Mail 发件。
