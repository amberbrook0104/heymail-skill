# 故障处理

脚本只输出错误类别、受控错误码与 SMTP 数字状态码，不打印服务器认证原文或协议调试日志。

| 情况 | 处理 |
| --- | --- |
| setup_required | 先确认是否在隔离沙箱中运行。沙箱的应用数据目录可能不同，先用宿主授权机制在实际 Windows 用户上下文重查；确认本机确实无配置后再首次设置。 |
| 第一次使用没有输入框 | 不再要求先填写邮箱。先用 credential_input.py --probe；在实际 Windows 用户桌面运行 Python 输入框并核对 gui_ready。不要只在管道里运行命令并声称已弹出。 |
| Tkinter 未安装或 GUI 不出现 | 让用户在资源管理器双击完整解压后的 start-setup.cmd；仍无窗口时双击 start-setup-console.cmd，通过本机终端隐藏输入。不要用聊天收授权码替代。 |
| PowerShell 脚本被阻止 / 没有 pwsh | 新的默认输入入口使用 Python，不依赖 PowerShell 执行策略；不要为弹框改全局执行策略。旧 PS 脚本只保留兼容用途。 |
| authorization_already_saved_upload_resume_or_provide_email_next | 暂存已经成功，读取 onboarding-status，继续收简历或发件邮箱，不重新开框、覆盖暂存记录。 |
| save_authorization_code_first / upload_resume_before_sender_email_setup | 严格执行授权码 → 简历 → 发件邮箱的首次顺序；未验证完整配置前不进入邮件投递。 |
| open_local_console_launcher_for_hidden_input | 当前终端是工具管道，不接受秘密。让用户运行可见的本机终端入口，输入不会明文回显。 |
| provider_email_domain_mismatch | 163 只接受 @163.com，QQ 只接受 @qq.com；企业邮/其他域名本版不支持。 |
| credential_not_found_or_not_accessible / credential_saved:false | 用同一 Windows 用户打开本机密码框保存；工具沙箱也可能限制凭据访问，申请所需本机权限。 |
| SMTPAuthenticationError / 535 | 确认已开通 SMTP、使用授权码而非登录密码；检查是否更改过密码使旧码过期，在本机重新填写。不要把授权码贴进聊天排查。 |
| timeout / network error / TLS error | 检查联网、DNS和证书；禁止关闭证书校验。发送前失败与已提交后不确定要分开看回执。 |
| confirmation_is_for_a_different_preview | 当前待发稿已改变，重新展示最新稿并等新“发送”。 |
| attachment_changed_prepare_and_review_again | 附件字节变化，重新准备并核对；不要跳过哈希。 |
| already_submitted_or_uncertain_do_not_resend | 查看已有回执和实际收件；不能删除回执后重发。 |
| workflow_locked_check_previous_process | 同一状态目录仍在被使用，先检查进程；异常遗留时也先检查回执再恢复。 |
| subject / recipient / filename 校验失败 | 按错误字段修正；不猜模糊邮箱或改简历扩展名。 |
| 收件端没有邮件 | SMTP accepted 不等于投递成功，检查垃圾箱、退信和服务商自助查询，不自动再发。 |
| 没有已发送箱记录 | SMTP 提交不保证客户端“已发送”文件夹同步；以本机回执、退信和实际收件为准。 |

默认不使用 IMAP。未开通 IMAP 或 IMAP 登录失败不影响 SMTP 发信；不要为了投递简历扩大为读取全部邮箱或反复登录。

没有配置或没有待确认稿时，“发送”不会产生新邮件；先完成设置或上传 JD。有效确认后仍可能出现系统工具权限请求，技能无法绕过客户端或操作系统的权限控制。
