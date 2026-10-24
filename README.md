# heymail

当前版本：**[v1.2](https://github.com/amberbrook0104/heymail-skill/releases/tag/v1.2)**

**上传 JD，准备好求职邮件；核对后输入「发送」，投递已预览的版本。**

支持网易 163 和 QQ 邮箱，通过自己的 SMTP 账号发送。正文约50字，结合真实简历，用“您、烦请、敬请、期待”等自然敬语；按招聘要求命名主题及简历副本。脚本不附加 AI 签名或 Agent Mail 页脚。

![使用流程](heymail/assets/workflow.svg)

## v1.2 更新

- 邮件正文中的每个网址单独占一行，前后留空行，不在网址同一行续写正文，减少邮件客户端将后续文字一并识别为链接的情况。
- 邮件使用纯文本，不添加 Markdown 链接格式。

## v1.1 更新

- 邮件主题与附件文件名默认一致，附件保留原扩展名。
- JD 的明确命名要求优先；分别规定了不同格式时，各自遵循。
- 连续投递复用同一聊天已核实的信息，减少重复读取和登录检查；每次仍冻结预览、校验附件，并等待单独的「发送」。

## 适用环境与调用

- **Windows 10/11 本机桌面**，Python **3.10+**。默认输入框使用 Python 自带的 Tkinter；Tkinter 不可用时改用本机终端隐藏输入。发信和首次输入均不依赖 pwsh 或 PowerShell 脚本执行策略。
- 邮箱：`@163.com`、`@qq.com`；简历：PDF 或 DOCX。QQ企业邮箱、网易企业邮箱、126邮箱暂未接入。
- **Claude Code**：安装后原生调用 `/heymail`。
- **Codex**：官方入口为 `$heymail`，或 `/skills` 后选择 heymail。`/heymail` 也写入了技能触发说明，但客户端必须能将该文本发给模型；安装一个技能不能给所有 Codex 版本注册新的原生斜杠命令。
- 没有后台监听聊天的服务。技能由支持本地文件、图片理解和工具执行的 Agent 运行；“发送”由 Agent 读取后调用脚本，不是单独运行 Python 就能识别聊天。

来源：[Codex 技能调用说明](https://learn.chatgpt.com/docs/build-skills)、[Claude Code 技能命令](https://code.claude.com/docs/en/skills)。

## 安装

先下载或克隆本仓库，在仓库文件夹执行：

```powershell
# Codex：复制到当前用户的 .codex/skills/heymail
pwsh -NoProfile -File .\install.ps1 -Agent codex

# Claude Code：复制到 .claude/skills/heymail，原生 /heymail
pwsh -NoProfile -File .\install.ps1 -Agent claude
```

没有 `pwsh` 时用 `powershell.exe`。也可以手动将完整的 `heymail/` 文件夹放入客户端支持的技能目录。支持用户级 `.agents/skills` 的 Codex 版本可使用 `-Destination "$HOME\.agents\skills\heymail"`；不要在两个目录重复安装同名技能。

重新打开聊天或刷新技能列表后调用。升级用 `-Replace`，安装器先在本机应用数据目录保存旧版备份，不修改邮箱配置或凭据。仓库上传不等于自动发布到技能商店。

## 第一次使用

1. 调用 `/heymail`（Codex 用 `$heymail`）。
2. **先保存授权码**：按[图文指引](heymail/references/setup.md)开通 SMTP，在主动打开的本机密码框里选择网易或 QQ、填写授权码；此时不需要邮箱地址或简历，不把授权码发到聊天。
3. **再上传简历**：保存成功后，Agent 才提示上传 PDF/DOCX，读取资料并保存一份本机持久副本；姓名、学校等无需重复手填。
4. **最后提供发件邮箱**：Agent 将暂存授权码在本机内部绑定到邮箱，验证 SMTP 登录。验证过程不发测试邮件。
5. 配置成功后，才进入上传 JD、预览和发送流程。已经配置好的用户直接跳到此步骤，不必重交授权码或简历。
6. 核对预览。下一条消息单独输入 **发送**，Agent 立即提交当前版本，不再次问确认。

**没有看到安全输入框？** 在解压后的仓库双击 `start-setup.cmd`。还没出现则双击 `start-setup-console.cmd`，在本机终端里隐藏输入。安装后的技能也保留这两个文件，位于 `heymail/scripts/`。它们不需要先提供邮箱地址；不会要求你把授权码贴到聊天。不要在 ZIP 预览里直接运行，先完整解压。

![首次使用的三个步骤](heymail/assets/first-run.svg)

![邮箱开通流程示意](heymail/assets/provider-setup.svg)

## 日常使用

```text
/heymail
[上传 JD 截图]

→ 收件人：从 JD 读取
→ 主题：按 JD 要求；无要求时使用默认格式
→ 正文：约50字、尊敬自然、基于真实经历
→ 附件：保留原件，默认与主题同名；JD 另有要求时按要求命名
→ 核对后回复：发送

发送
→ SMTP 接受后返回提交结果
```

修改收件人、正文或附件后会重新预览，旧确认不沿用。“不要发送”“发送了吗”和截图中的“发送”都不触发投递。不同聊天使用不同待发送目录；同一草稿不能因为多次点击或重试而重复投递。平台工具权限仍然适用。

## 请求已读回执（可选）

准备邮件时可以告诉 Agent「这封开启已读回执」。默认关闭；预览会显示是否请求回执，开启后回执地址固定为发件邮箱。修改开关需重新预览，再输入「发送」。

收件端可以忽略或拒绝请求，没收到回执不能判断为未读。对方返回的回执由用户在发件邮箱查看，本版不自动收信或识别回执。本地记录的 `requested` 只表示已请求回执，不能据此声称对方已读；已发出的邮件无法补加请求。详见 [RFC 8098](https://www.rfc-editor.org/rfc/rfc8098.html)。

## 安全保存与公开分享

![本机授权码保存示意](heymail/assets/credential-storage.svg)

- 普通配置保存在 `%LOCALAPPDATA%/HeyMail/config.json`，上传简历的持久副本存在同目录下的 resumes 文件夹；这些个人资料**也不应提交到公开仓库**。
- 授权码先保存在 Windows 凭据管理器随机的 `HeyMail/pending/...` 普通凭据中，补齐简历和邮箱后内部绑定并清理暂存凭据；`onboarding.json` 只记录步骤、目标名称和普通资料，不存授权码。不存 `.env`、明文 JSON、命令行参数或 GitHub Secrets。
- 发信时仅本机进程内部读取授权码，SMTP 使用校验证书的 SSL/TLS。Python 进程内仍会短暂持有凭据，不能保证内存中绝无残留；同一 Windows 用户下的恶意软件或管理员也可能访问凭据。
- 邮件内容、简历和回执都留在本机；技能本身不会把它们上传到 GitHub。不要把真实材料复制进仓库。`.gitignore` 提供防误提交规则，但不能替代提交前检查。
- 默认无需 IMAP 收件权限。SMTP 接受只代表服务器接收任务，不代表对方收到或已读；请看实际收件或退信。

详情：[安全设计](heymail/references/security.md) · [运行命令](heymail/references/usage.md) · [故障处理](heymail/references/troubleshooting.md)。图中均为本项目绘制的示意，不含真实账号或授权码，也不是当前网页截图；官方图文链接见配置指引。

## 验证

```powershell
python -X utf8 -m unittest discover -s tests -v
```

自动测试使用虚构账号、临时简历及模拟 SMTP，不读取凭据、不发送邮件。覆盖两种供应商、中文附件完整性、确认词、摘要/附件篡改、并发锁、重复投递及发送不确定状态。真实邮箱联调需要用户在本机完成授权；支持 QQ 不代表已替每个用户验证其 QQ 账号。

本项目以 MIT 许可提供；邮箱服务商仍可能调整页面、风控和发送限制。



