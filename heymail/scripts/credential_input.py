"""First-run local secret entry. No sender email is needed before saving a code."""
from __future__ import annotations

import argparse
import getpass
import importlib.util
from pathlib import Path
import sys
import subprocess
import time
import uuid
import warnings

spec = importlib.util.spec_from_file_location("heymail_core", Path(__file__).with_name("mail.py"))
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class InputSession:
    def __init__(self, args):
        self.args = args
        self.provider = args.provider or ""
        self.mode = "console" if args.console else "gui"
        self.saved = False
        self.ready = False
        self.status_file = args.status_file or core.default_config().parent / "onboarding.json"
        if not args.email and self.status_file.exists():
            previous = core.read_json(self.status_file)
            if previous.get("phase") in ("credential_saved", "resume_saved"):
                raise core.MailError("authorization_already_saved_upload_resume_or_provide_email_next")
        self.target = (args.credential_target or f"HeyMail/{self.provider}/{args.email}") if args.email else "HeyMail/pending/" + uuid.uuid4().hex
        if not args.email and args.credential_target:
            raise core.MailError("pending_mode_cannot_overwrite_account_credential")
        if args.email and not args.provider:
            raise core.MailError("provider_required_for_existing_account")

    def state(self, phase, ready=False):
        import os
        core.atomic_json(self.status_file, {
            "phase": phase, "provider": self.provider, "credential_target": self.target,
            "mode": self.mode, "pid": os.getpid(), "time": core.now(), "gui_ready": ready})

    def save(self, provider, secret):
        if provider not in core.PROVIDERS:
            raise core.MailError("select_163_or_qq")
        if not secret:
            raise core.MailError("authorization_code_required")
        if self.args.email:
            core.email_address(self.args.email)
            if self.args.email.split("@")[1].lower() != core.PROVIDERS[provider]["domain"]:
                raise core.MailError("provider_email_domain_mismatch")
        core.vault_save({"credential_target": self.target, "email": self.args.email or "pending"}, secret)
        self.provider = provider
        self.state("credential_saved")
        self.saved = True


def console_input(session):
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise core.MailError("open_local_console_launcher_for_hidden_input")
    provider = session.provider
    if not provider:
        provider = {"1": "163", "2": "qq"}.get(input("邮箱类型：1=网易163，2=QQ：").strip())
    if provider not in core.PROVIDERS:
        raise core.MailError("select_163_or_qq")
    session.provider = provider
    session.state("waiting_for_credential")
    secret = None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            secret = getpass.getpass("SMTP授权码（隐藏输入，不是网页登录密码）：")
        session.save(provider, secret.strip())
    finally:
        secret = None
    print("授权码已在本机安全暂存。请返回聊天：下一步上传简历，然后提供发件邮箱。")


def gui_input(session):
    import tkinter as tk
    from tkinter import ttk, messagebox
    root = tk.Tk()
    root.withdraw()
    root.title("HeyMail 第一步 - 安全填写授权码")
    width, height = 620, 330
    left = max(0, (root.winfo_screenwidth() - width) // 2)
    top = max(0, (root.winfo_screenheight() - height) // 2)
    root.geometry(f"{width}x{height}+{left}+{top}")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="第一步：安全填写 SMTP 授权码", font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
    ttk.Label(frame, text="现在无需提供邮箱地址或简历。\n授权码先保存在 Windows 凭据管理器；不会发邮件。", padding=(0, 12)).pack(anchor="w")
    provider = tk.StringVar(value={"163": "网易 163", "qq": "QQ 邮箱"}.get(session.provider, "请选择邮箱类型"))
    picker = ttk.Combobox(frame, textvariable=provider, values=("网易 163", "QQ 邮箱"), state="readonly")
    picker.pack(fill="x", pady=(0, 12))
    code = ttk.Entry(frame, show="●", font=("Microsoft YaHei UI", 12))
    code.pack(fill="x")
    ttk.Label(frame, text="保存后回到聊天：第二步上传简历 → 第三步提供发件邮箱。", padding=(0, 12)).pack(anchor="w")
    buttons = ttk.Frame(frame)
    buttons.pack(fill="x", pady=(8, 0))

    def save():
        secret = code.get().strip()
        try:
            selected = {"网易 163": "163", "QQ 邮箱": "qq"}.get(provider.get())
            session.save(selected, secret)
            code.delete(0, "end")
            messagebox.showinfo("保存成功", "授权码已在本机安全暂存。\n请返回聊天上传简历，然后提供发件邮箱。", parent=root)
            root.destroy()
        except Exception:
            messagebox.showerror("暂存未完成", "请选择邮箱类型并填写授权码。若仍失败，请使用本机终端隐藏输入入口；不要把授权码发到聊天。", parent=root)
        finally:
            secret = None

    def cancel():
        code.delete(0, "end")
        session.state("cancelled")
        root.destroy()

    def mapped(event):
        if event.widget is root and not session.ready:
            session.ready = True
            session.state("waiting_for_credential", ready=True)
            code.focus_set()
            if session.args.smoke_test:
                root.after(800, root.destroy)

    ttk.Button(buttons, text="安全暂存", command=save).pack(side="right")
    ttk.Button(buttons, text="取消", command=cancel).pack(side="right", padx=10)
    root.protocol("WM_DELETE_WINDOW", cancel)
    root.bind("<Map>", mapped)
    root.bind("<Return>", lambda _: save())
    session.state("starting_input")
    root.deiconify()
    root.mainloop()


def launch_input(args):
    session = InputSession(args)
    session.state("starting_input")
    command = [sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
               "--status-file", str(session.status_file.resolve())]
    for flag, value in (("--provider", args.provider), ("--email", args.email),
                        ("--credential-target", args.credential_target)):
        if value:
            command.extend((flag, value))
    if args.console:
        command.append("--console")
    if args.smoke_test:
        command.append("--smoke-test")
    kwargs = {"creationflags": subprocess.CREATE_NEW_CONSOLE if args.console else subprocess.CREATE_NO_WINDOW}
    if not args.console:
        kwargs.update(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    process = subprocess.Popen(command, **kwargs)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        state = core.read_json(session.status_file)
        if state.get("phase") == "credential_saved" or (state.get("phase") == "waiting_for_credential" and
                (state.get("gui_ready") or args.console)):
            core.emit({"ok": True, "launched": True, "gui_ready": state.get("gui_ready", False),
                       "mode": session.mode, "status_file": str(session.status_file), "pid": process.pid})
            return 0
        if process.poll() is not None or state.get("phase") == "input_unavailable":
            break
        time.sleep(0.1)
    core.emit({"ok": False, "code": "input_not_ready_use_local_launcher_or_console",
               "pid": process.pid, "status_file": str(session.status_file)})
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=core.PROVIDERS)
    parser.add_argument("--email", default="", help="Optional: update an existing sender credential")
    parser.add_argument("--credential-target", default="")
    parser.add_argument("--status-file", type=Path)
    parser.add_argument("--console", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--launch", action="store_true", help="Start local GUI or visible console and check readiness")
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    if args.probe:
        try:
            import tkinter
            available = True
        except ImportError:
            available = False
        core.emit({"ok": True, "windows": sys.platform == "win32", "tkinter_available": available,
                   "python": sys.version.split()[0], "email_required_before_input": False,
                   "console_fallback_available": True})
        return 0
    if sys.platform != "win32":
        raise core.MailError("windows_local_desktop_required")
    if args.launch:
        if not args.console:
            try:
                import tkinter
            except ImportError:
                args.console = True
        return launch_input(args)
    session = InputSession(args)
    try:
        console_input(session) if args.console else gui_input(session)
        core.emit({"ok": True, "saved": session.saved, "gui_ready": session.ready,
                   "status_file": str(session.status_file), "smoke_test": args.smoke_test})
        return 0
    except Exception as error:
        try:
            session.state("input_unavailable")
        except Exception:
            pass
        core.emit({"ok": False, "error_type": type(error).__name__,
                   "code": error.code if isinstance(error, core.MailError) else "gui_unavailable_use_console_launcher"})
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except core.MailError as error:
        core.emit({"ok": False, "code": error.code})
        sys.exit(1)
