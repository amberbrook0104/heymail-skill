# heymail

当前版本：**[v1.3](https://github.com/amberbrook0104/heymail-skill/releases/tag/v1.3)** · [下载安装包](https://github.com/amberbrook0104/heymail-skill/releases/download/v1.3/heymail-v1.3.zip)

上传JD，预览求职邮件；核对后单独回复「发送」，投递并登记到本机Excel台账。

**[下载空白台账模板](https://github.com/amberbrook0104/heymail-skill/releases/download/v1.3/application-ledger.xlsx)** · [仓库内模板](heymail/assets/templates/application-ledger.xlsx)。模板包含8列、社科大标识、紧凑行高、进展下拉和跟进日期提示，不含任何个人投递记录。完整安装包也包含这份模板。自动登记时使用`tracker-sync`生成并更新实时台账；已有用户不要用空白模板覆盖自己的台账。

## 选择入口

| 你的情况 | 指引 | 内容 |
|---|---|---|
| 第一次下载、还没配置 | **[首次安装](docs/first-install.md)** | 安装命令、完整可复制提示词、首次配置顺序 |
| 已安装旧版、已有账号和记录 | **[已有用户更新](docs/update.md)** | 原地更新命令、完整可复制提示词、资料保留与刷新 |

## v1.3 更新

- 同一个 heymail 同时负责邮件投递和共享Excel台账，Codex、豆包可共用一份记录。
- 台账只显示8列：公司、岗位、工作地点、投递时间、投递 Agent、当前进展、下次跟进、备注。时间按北京时间从新到旧排列。
- 同一JD多联系人或补投合并一行；进展、跟进日期、备注及其他人工修订刷新后保留。
- 社科大校徽与校训、红白配色、紧凑行高；表内不显示用户姓名，不显示JD来源列。文件作者取当前发件配置姓名。
- 可创建桌面快捷方式，打开持续更新的原台账。
- 支持简历之外的PDF/DOCX课题或作品附件：每封最多4个，单个10 MiB以内，总计15 MiB以内，原件内容保持一致。
- 保留标题/附件命名、来源平台前缀剔除、网址独占一行、摘要和全部附件校验、预览确认及防重复发送。

## 适用环境

- 本机 Windows 10/11，Python 3.10+；发件邮箱支持 `@163.com` 和 `@qq.com`，授权码存入 Windows 凭据管理器。
- 发信使用Python标准库；首次安全输入优先使用Tkinter，无图形环境时使用本机终端隐藏输入。
- **Excel台账是可选能力**：需要本机可用的Node.js和`@oai/artifact-tool`运行时。支持提供该运行时的Agent环境；Codex可通过工作区依赖定位工具查找。安装器不会从npm下载私有包，也不要求模型API密钥。
- 如果当前环境没有Excel生成依赖，先使用邮件投递功能；Agent应说明台账尚未配置，不能把安装成功说成台账已启用。豆包可复用同机已验证可用的运行时及共享目录。
- 用Excel或兼容软件查看生成的`.xlsx`。xlwings不是本版台账的必需依赖。

## 安装与调用

下载并完整解压，进入含`install.ps1`的目录：

```powershell
# 首次安装，按实际客户端选择一条
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Agent codex
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Agent doubao
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Agent claude
```

Codex新安装默认放入`%USERPROFILE%\.agents\skills\heymail`；如果已有`.codex\skills\heymail`旧安装，会原地沿用。两处都存在时需用`-Destination`明确指定，避免重复安装。豆包默认目标为Default配置下的`.user_skills\heymail`；自定义安装位置同样用`-Destination`指定。[Codex本地技能目录说明](https://learn.chatgpt.com/docs/build-skills)

升级加`-Replace`。安装器先备份旧技能，只替换技能文件，不改邮箱配置、凭据、简历或台账。详细步骤与可复制提示词分别见上方两个入口。

Codex可调用`$heymail`或在`/skills`中选择；豆包可要求使用已安装的heymail技能。Claude Code使用`/heymail`。客户端需具备本地文件读取、图片理解和命令执行能力；安装技能不等于给所有客户端注册原生斜杠命令。

## 首次配置顺序

1. Agent检查实际Windows用户环境中的已有配置；已有配置可用时跳过首次设置。
2. 首先主动打开本机授权码输入框；不能把授权码发到聊天。此时无需先提供邮箱地址或简历。
3. 授权码保存后，再上传PDF/DOCX简历。
4. 最后提供发件邮箱；Agent从简历核实姓名等信息，绑定凭据并检查SMTP登录，不发测试邮件。
5. 台账依赖可用时，选择共享保存目录；Codex与豆包沿用同一个`tracker.root`。
6. 生成台账，再运行`tracker-shortcut`创建桌面入口。

没有看到安全输入框时，完整解压后双击`start-setup.cmd`；仍无图形框时使用`start-setup-console.cmd`。详见[首次配置](heymail/references/setup.md)。

![使用流程](heymail/assets/workflow.svg)

## 日常投递与台账

用户提供JD → Agent核实岗位与真实经历 → 冻结邮件和全部附件 → 展示预览 → 用户单独回复「发送」 → SMTP提交 → 保存本地回执并刷新共享台账。

```powershell
# 只刷新台账，不发信、不读取凭据
python -X utf8 "<skill-dir>\scripts\mail.py" tracker-sync

# 查找已有岗位编号，方便多联系人/补投合并
python -X utf8 "<skill-dir>\scripts\mail.py" tracker-list --query "公司名"

# 为已生成的台账创建或更新桌面快捷方式
python -X utf8 "<skill-dir>\scripts\mail.py" tracker-shortcut
```

Excel打开导致刷新失败时，邮件回执和投递事件仍会保留；保存并关闭Excel后再刷新，不能因此重发邮件。旧版本只保存了邮件回执时，可由Agent按用户指定目录回填；无法核实的公司、岗位或地点留待确认，不从邮箱域名猜填。详细字段和样式见[台账定稿规范](heymail/references/tracker.md)。

## 数据与发送边界

- 普通配置位于`%LOCALAPPDATA%/HeyMail/config.json`，SMTP授权码只在Windows凭据管理器中。实际路径可能受客户端沙箱重定向，需检查真实用户环境。
- 简历原件、课题附件、JD、投递回执、个人台账和人工更新均为本机私有资料，不进入此仓库或安装包；仓库中的Excel仅为空白模板。
- SMTP使用验证证书的SSL/TLS；`accepted`仅表示服务器接受，不保证送达或已读。本版不请求已读回执，也不自动读取收件箱。
- 修改正文、收件人或任一附件后需重新预览确认；已接受或状态不明的旧草稿不能盲目重发。

代码采用MIT许可。社科大校徽、校名和校训图片等标识素材的权利归其原权利人；它们作为个人台账的视觉素材提供，不代表学校背书，也不随代码MIT许可转授标识权利。可通过共享目录`.branding.json`替换自己的素材。

详情：[运行命令](heymail/references/usage.md) · [安全设计](heymail/references/security.md) · [故障处理](heymail/references/troubleshooting.md)

## 验证

```powershell
python -X utf8 -m unittest discover -s tests -v
```

测试使用合成账号、临时文件和模拟SMTP，不发送真实邮件、不读取凭据。需要Excel生成运行时的集成检查通过环境变量`HEYMAIL_TEST_NODE`和`HEYMAIL_TEST_MODULE_DIR`启用；未提供时相应检查跳过。
