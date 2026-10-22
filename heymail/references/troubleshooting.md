# 故障处理

脚本只输出错误类别、受控错误码与 SMTP 数字状态码，不打印服务器认证原文或协议调试日志。

| 情况 | 处理 |
| --- | --- |
| setup_required | 先确认是否在隔离沙箱中运行。沙箱的应用数据目录可能不同，先用宿主授权机制在实际 Windows 用户上下文重查；确认本机确实无配置后再首次设置。 |
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
