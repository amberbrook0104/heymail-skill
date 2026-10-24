"""Windows-first JD mail workflow. Stdlib only; secrets stay in Credential Manager."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import smtplib
import ssl
import sys
import uuid

PROVIDERS = {"163": {"domain": "163.com", "smtp": "smtp.163.com"},
             "qq": {"domain": "qq.com", "smtp": "smtp.qq.com"}}
MAX_ATTACHMENT = 10 * 1024 * 1024
BLOCKED = {"accepted", "submitting", "uncertain"}


class MailError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def now():
    return datetime.now(timezone.utc).isoformat()


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_bytes(canonical(value))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def default_config():
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share")))
    return base / "HeyMail" / "config.json"


def email_address(value):
    if not isinstance(value, str) or not re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}", value):
        raise MailError("invalid_single_email_address")
    return value


def validate_config(value):
    allowed = {"version", "provider", "email", "display_name", "resume_path",
               "credential_target", "applicant"}
    if not isinstance(value, dict) or set(value) - allowed:
        raise MailError("config_unknown_fields_no_secrets_allowed")
    provider = value.get("provider")
    if provider not in PROVIDERS:
        raise MailError("provider_must_be_163_or_qq")
    email_address(value.get("email"))
    if value["email"].split("@")[1].lower() != PROVIDERS[provider]["domain"]:
        raise MailError("provider_email_domain_mismatch")
    for key in ("display_name", "resume_path", "credential_target"):
        if not isinstance(value.get(key), str) or not value[key].strip() or any(
                c in value[key] for c in "\r\n\x00"):
            raise MailError("invalid_config_field")
    applicant = value.get("applicant", {})
    fields = {"name", "school", "degree", "grade", "days_per_week", "months", "start_date"}
    if not isinstance(applicant, dict) or set(applicant) - fields:
        raise MailError("invalid_applicant_profile")
    return value


def load_config(path):
    if not path.exists():
        raise MailError("setup_required")
    return validate_config(read_json(path))


def sender(config):
    return {k: config[k] for k in ("provider", "email", "display_name", "credential_target")}


def credential_api():
    if sys.platform != "win32":
        raise MailError("windows_credential_manager_required")

    class Credential(ctypes.Structure):
        _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
                    ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
                    ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
                    ("CredentialBlob", ctypes.c_void_p), ("Persist", wintypes.DWORD),
                    ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                    ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]

    api = ctypes.WinDLL("advapi32", use_last_error=True)
    api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                             ctypes.POINTER(ctypes.POINTER(Credential))]
    api.CredReadW.restype = wintypes.BOOL
    api.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
    api.CredWriteW.restype = wintypes.BOOL
    api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    api.CredDeleteW.restype = wintypes.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    return api, Credential


def vault(config, exists_only=False):
    api, Credential = credential_api()
    item = ctypes.POINTER(Credential)()
    if not api.CredReadW(config["credential_target"], 1, 0, ctypes.byref(item)):
        if exists_only:
            return False
        raise MailError("credential_not_found_or_not_accessible")
    try:
        if item.contents.UserName != config["email"]:
            raise MailError("credential_account_mismatch")
        if exists_only:
            return True
        return ctypes.string_at(item.contents.CredentialBlob,
                                item.contents.CredentialBlobSize).decode("utf-16-le")
    finally:
        api.CredFree(item)


def vault_save(config, secret):
    api, Credential = credential_api()
    data = secret.encode("utf-16-le")
    buffer = ctypes.create_string_buffer(data)
    item = Credential()
    item.Type = 1
    item.TargetName = config["credential_target"]
    item.UserName = config["email"]
    item.Comment = "HeyMail SMTP authorization code"
    item.CredentialBlobSize = len(data)
    item.CredentialBlob = ctypes.cast(buffer, ctypes.c_void_p)
    item.Persist = 2
    try:
        if not api.CredWriteW(ctypes.byref(item), 0):
            raise MailError("credential_save_failed")
    finally:
        ctypes.memset(ctypes.addressof(buffer), 0, ctypes.sizeof(buffer))
        data = None


def vault_delete_pending(target):
    if not re.fullmatch(r"HeyMail/pending/[0-9a-f]{32}", target):
        raise MailError("invalid_pending_credential_target")
    api, _ = credential_api()
    if not api.CredDeleteW(target, 1, 0):
        raise MailError("pending_credential_cleanup_failed")


def onboarding_path(config_path):
    return config_path.resolve().parent / "onboarding.json"


def onboarding_state(config_path):
    path = onboarding_path(config_path)
    result = {"ok": True, "config": str(config_path.resolve()), "onboarding_file": str(path)}
    if config_path.exists():
        config = load_config(config_path)
        saved = vault(config, exists_only=True)
        result.update(existing_config=True, credential_saved=saved)
        if saved:
            result["phase"] = "configured"
            return result
    if path.exists():
        state = read_json(path)
        # Status is non-secret. Reject fields that might accidentally contain a code.
        allowed = {"phase", "provider", "credential_target", "mode", "pid", "time", "resume_path", "resume_sha256", "gui_ready", "error_type"}
        if set(state) - allowed:
            raise MailError("invalid_onboarding_status_fields")
        result.update(state)
        if result.get("phase") == "configured":
            result["phase"] = "authorization_required"
    else:
        result["phase"] = "authorization_required"
    return result


def validate_pending(path, provider=None):
    state = read_json(path)
    if state.get("phase") not in ("credential_saved", "resume_saved"):
        raise MailError("save_authorization_code_first")
    if state.get("provider") not in PROVIDERS or (provider and state["provider"] != provider):
        raise MailError("pending_provider_mismatch")
    if not re.fullmatch(r"HeyMail/pending/[0-9a-f]{32}", state.get("credential_target", "")):
        raise MailError("invalid_pending_credential_target")
    return state


def onboarding_resume(config_path, resume):
    path = onboarding_path(config_path)
    state = validate_pending(path)
    source = resume.resolve(strict=True)
    if source.suffix.lower() not in (".pdf", ".docx"):
        raise MailError("resume_must_be_pdf_or_docx")
    if not source.is_file() or not 0 < source.stat().st_size <= MAX_ATTACHMENT:
        raise MailError("resume_empty_or_larger_than_10mib")
    data = source.read_bytes()
    if source.suffix.lower() == ".pdf" and not data.startswith(b"%PDF-"):
        raise MailError("invalid_pdf_header")
    if source.suffix.lower() == ".docx" and not data.startswith(b"PK"):
        raise MailError("invalid_docx_header")
    # Uploaded chat attachments may live in temporary caches. Keep a private,
    # byte-identical local copy for later applications, outside the repository.
    destination = config_path.resolve().parent / "resumes" / uuid.uuid4().hex / safe_filename(source.name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    if sha(destination.read_bytes()) != sha(data):
        raise MailError("resume_copy_integrity_failed")
    state.update(phase="resume_saved", resume_path=str(destination), resume_sha256=sha(data), time=now())
    atomic_json(path, state)
    return {"ok": True, "phase": "email_required", "resume_path": str(destination),
            "onboarding_file": str(path), "next": "ask_sender_email_then_setup"}


def safe_filename(value):
    if not isinstance(value, str) or not value.strip():
        raise MailError("attachment_name_required")
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value).strip().rstrip(". ")
    if not cleaned or len(cleaned) > 180:
        raise MailError("attachment_name_empty_or_too_long")
    if re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", cleaned.split(".")[0]):
        cleaned = "_" + cleaned
    return cleaned


@contextmanager
def state_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ".mail.lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise MailError("workflow_locked_check_previous_process") from None
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        path.unlink(missing_ok=True)


def setup(args):
    path = args.config.resolve()
    config = {"version": 1, "provider": args.provider, "email": args.email,
              "display_name": args.name, "resume_path": str(args.resume.resolve(strict=True)),
              "credential_target": args.credential_target or f"HeyMail/{args.provider}/{args.email}",
              "applicant": {"name": args.name, "school": args.school, "degree": args.degree,
                            "grade": args.grade, "days_per_week": args.days,
                            "months": args.months, "start_date": args.start_date}}
    validate_config(config)
    if args.resume.suffix.lower() not in (".pdf", ".docx"):
        raise MailError("resume_must_be_pdf_or_docx")
    if path.exists():
        if not args.replace:
            raise MailError("config_exists_use_replace_for_intended_update")
        shutil.copy2(path, path.with_name(path.name + "." + uuid.uuid4().hex + ".bak"))
    pending_path = getattr(args, "pending_credential", None)
    pending = None
    if pending_path:
        pending = validate_pending(pending_path, config["provider"])
        if pending.get("phase") != "resume_saved":
            raise MailError("upload_resume_before_sender_email_setup")
        if Path(pending.get("resume_path", "")).resolve() != args.resume.resolve():
            raise MailError("resume_does_not_match_onboarding")
        # Bind internally: no secret appears in CLI args, JSON, or stdout.
        secret = vault({"credential_target": pending["credential_target"], "email": "pending"})
        try:
            vault_save(config, secret)
        finally:
            secret = None
    atomic_json(path, config)
    cleanup_required = False
    if pending:
        try:
            vault_delete_pending(pending["credential_target"])
        except MailError:
            cleanup_required = True
        pending.update(phase="configured", time=now())
        atomic_json(pending_path, pending)
    return {"ok": True, "config": str(path), "credential_target": config["credential_target"],
            "pending_cleanup_required": cleanup_required,
            "note": "profile_saved_no_secret_written_no_mail_sent"}


def read_pending(directory):
    pointer = read_json(directory / "pending.json")
    identifier = pointer.get("draft_id", "")
    if not re.fullmatch(r"[0-9a-f]{32}", identifier):
        raise MailError("invalid_pending_draft_id")
    draft_dir = directory / identifier
    manifest = read_json(draft_dir / "manifest.json")
    digest = sha(canonical(manifest))
    if digest != pointer.get("digest"):
        raise MailError("draft_changed_prepare_and_review_again")
    return pointer, draft_dir, manifest, digest


def read_receipt_enabled(data):
    enabled = data.get("request_read_receipt", False)
    if not isinstance(enabled, bool):
        raise MailError("request_read_receipt_must_be_boolean")
    return enabled


def preview(manifest, digest, draft_dir):
    enabled = read_receipt_enabled(manifest)
    return {"ok": True, "status": "prepared_waiting_for_user_send", "digest": digest,
            "from": manifest["sender"]["email"], "to": manifest["to"],
            "subject": manifest["subject"], "body": manifest["body"],
            "attachment": str(draft_dir / manifest["attachment"]["filename"]),
            "attachment_sha256": manifest["attachment"]["sha256"],
            "request_read_receipt": enabled,
            "read_receipt_to": manifest["sender"]["email"] if enabled else None,
            "next_user_message": "发送"}


def prepare(config, args):
    job = read_json(args.draft)
    if set(job) - {"to", "subject", "body", "attachment_name", "request_read_receipt"}:
        raise MailError("unexpected_draft_fields")
    enabled = read_receipt_enabled(job)
    email_address(job.get("to"))
    if not isinstance(job.get("subject"), str) or not job["subject"].strip() or any(
            c in job["subject"] for c in "\r\n\x00"):
        raise MailError("invalid_subject")
    if not isinstance(job.get("body"), str) or not job["body"].strip() or len(job["body"]) > 10000:
        raise MailError("invalid_body")
    source = Path(config["resume_path"]).resolve(strict=True)
    if source.suffix.lower() not in (".pdf", ".docx"):
        raise MailError("resume_must_be_pdf_or_docx")
    filename = safe_filename(job.get("attachment_name"))
    if Path(filename).suffix.lower() != source.suffix.lower():
        raise MailError("attachment_extension_must_match_original")
    data = source.read_bytes()
    if not data or len(data) > MAX_ATTACHMENT:
        raise MailError("resume_empty_or_larger_than_10mib")
    if source.suffix.lower() == ".pdf" and not data.startswith(b"%PDF-"):
        raise MailError("invalid_pdf_header")
    if source.suffix.lower() == ".docx" and not data.startswith(b"PK"):
        raise MailError("invalid_docx_header")
    directory = args.state_dir.resolve()
    with state_lock(directory):
        identifier = uuid.uuid4().hex
        draft_dir = directory / identifier
        draft_dir.mkdir()
        (draft_dir / filename).write_bytes(data)
        if sha((draft_dir / filename).read_bytes()) != sha(data):
            raise MailError("attachment_copy_integrity_failed")
        manifest = {"version": 1, "sender": sender(config), "to": job["to"],
                    "subject": job["subject"], "body": job["body"],
                    "request_read_receipt": enabled,
                    "attachment": {"filename": filename, "sha256": sha(data), "size": len(data)}}
        digest = sha(canonical(manifest))
        atomic_json(draft_dir / "manifest.json", manifest)
        atomic_json(directory / "pending.json", {"draft_id": identifier, "digest": digest})
        result = preview(manifest, digest, draft_dir)
        atomic_json(draft_dir / "preview.json", result)
        return result


def build_message(manifest, draft_dir):
    attachment = manifest["attachment"]
    filename = attachment["filename"]
    if safe_filename(filename) != filename or Path(filename).name != filename:
        raise MailError("unsafe_attachment_path")
    data = (draft_dir / filename).read_bytes()
    if sha(data) != attachment["sha256"] or len(data) != attachment["size"]:
        raise MailError("attachment_changed_prepare_and_review_again")
    msg = EmailMessage()
    msg["From"] = formataddr((manifest["sender"]["display_name"], manifest["sender"]["email"]))
    msg["To"] = email_address(manifest["to"])
    msg["Subject"] = manifest["subject"]
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=manifest["sender"]["email"].split("@")[1])
    if read_receipt_enabled(manifest):
        msg["Disposition-Notification-To"] = email_address(manifest["sender"]["email"])
    msg.set_content(manifest["body"], charset="utf-8")
    subtype = "pdf" if filename.lower().endswith(".pdf") else "vnd.openxmlformats-officedocument.wordprocessingml.document"
    msg.add_attachment(data, maintype="application", subtype=subtype, filename=filename)
    return msg


def connect(config, secret):
    client = smtplib.SMTP_SSL(PROVIDERS[config["provider"]]["smtp"], 465,
                              timeout=30, context=ssl.create_default_context())
    try:
        client.login(config["email"], secret)
    except Exception:
        client.close()
        raise
    return client


def close(client):
    try:
        client.quit()
    except Exception:
        # A QUIT failure does not negate an already accepted DATA transaction.
        client.close()


def send(config, args):
    # This is an execution guard, not proof of human approval. The agent must
    # receive the exact standalone message from the human after showing preview.
    if args.confirm != "发送":
        raise MailError("exact_user_send_confirmation_required")
    directory = args.state_dir.resolve()
    with state_lock(directory):
        _, draft_dir, manifest, digest = read_pending(directory)
        if digest != args.expected_digest:
            raise MailError("confirmation_is_for_a_different_preview")
        if manifest["sender"] != sender(config):
            raise MailError("sender_changed_prepare_and_review_again")
        receipt_path = draft_dir / "receipt.json"
        if receipt_path.exists() and read_json(receipt_path).get("status") in BLOCKED:
            raise MailError("already_submitted_or_uncertain_do_not_resend")
        msg = build_message(manifest, draft_dir)
        secret = vault(config)
        try:
            client = connect(config, secret)
        finally:
            secret = None
        receipt = {"status": "submitting", "time": now(), "digest": digest,
                   "from": config["email"], "to": manifest["to"],
                   "subject": manifest["subject"], "message_id": str(msg["Message-ID"]),
                   "request_read_receipt": read_receipt_enabled(manifest)}
        try:
            atomic_json(receipt_path, receipt)
            try:
                refused = client.send_message(msg)
                if refused:
                    raise smtplib.SMTPRecipientsRefused(refused)
            except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused,
                    smtplib.SMTPDataError) as error:
                receipt.update(status="rejected", error_type=type(error).__name__, time=now())
                atomic_json(receipt_path, receipt)
                raise
            except Exception:
                receipt.update(status="uncertain", time=now())
                atomic_json(receipt_path, receipt)
                raise
            receipt.update(status="accepted", time=now(),
                           read_receipt_status="requested" if receipt["request_read_receipt"]
                           else "not_requested")
            atomic_json(receipt_path, receipt)
            return {"ok": True, **receipt, "receipt": str(receipt_path),
                    "note": "smtp_accepted_delivery_not_verified"}
        finally:
            close(client)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=default_config())
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("setup", help="Save non-secret local profile only")
    init.add_argument("--provider", choices=PROVIDERS, required=True)
    init.add_argument("--email", required=True)
    init.add_argument("--name", required=True)
    init.add_argument("--resume", type=Path, required=True)
    for field in ("school", "degree", "grade", "days", "months", "start-date"):
        init.add_argument("--" + field, default="")
    init.add_argument("--credential-target", default="", help="Existing local credential target for migration")
    init.add_argument("--replace", action="store_true")
    init.add_argument("--pending-credential", type=Path, help="Non-secret local onboarding status; binds saved code internally")
    commands.add_parser("onboarding-status", help="Check first-run progress without needing a sender email")
    resume_step = commands.add_parser("onboarding-resume", help="Save the uploaded resume after authorization-code entry")
    resume_step.add_argument("--resume", type=Path, required=True)
    status = commands.add_parser("status", help="Show non-secret profile and optional pending draft")
    status.add_argument("--state-dir", type=Path)
    commands.add_parser("check", help="Authenticate SMTP; do not send a message")
    prep = commands.add_parser("prepare", help="Freeze a draft and resume copy; no network")
    prep.add_argument("--draft", type=Path, required=True)
    prep.add_argument("--state-dir", type=Path, required=True)
    submit = commands.add_parser("send", help="Send only the reviewed pending draft")
    submit.add_argument("--state-dir", type=Path, required=True)
    submit.add_argument("--expected-digest", required=True)
    submit.add_argument("--confirm", required=True)
    args = parser.parse_args()
    if args.command == "setup":
        emit(setup(args))
        return
    if args.command == "onboarding-status":
        emit(onboarding_state(args.config))
        return
    if args.command == "onboarding-resume":
        emit(onboarding_resume(args.config, args.resume))
        return
    config = load_config(args.config)
    if args.command == "status":
        result = {"ok": True, "config": str(args.config.resolve()), "profile": config,
                  "credential_saved": vault(config, exists_only=True)}
        if args.state_dir:
            _, directory, manifest, digest = read_pending(args.state_dir.resolve())
            result["pending"] = preview(manifest, digest, directory)
            if (directory / "receipt.json").exists():
                result["receipt"] = read_json(directory / "receipt.json")
        emit(result)
    elif args.command == "prepare":
        emit(prepare(config, args))
    elif args.command == "check":
        secret = vault(config)
        try:
            client = connect(config, secret)
        finally:
            secret = None
        close(client)
        emit({"ok": True, "smtp_authenticated": True, "provider": config["provider"], "account": config["email"]})
    else:
        emit(send(config, args))


def run():
    try:
        main()
        return 0
    except Exception as error:
        result = {"ok": False, "error_type": type(error).__name__}
        if isinstance(error, MailError):
            result["code"] = error.code
        elif isinstance(error, smtplib.SMTPResponseException):
            result["smtp_code"] = error.smtp_code
        # Raw exception text and protocol logs may expose authentication data.
        emit(result)
        return 1


if __name__ == "__main__":
    sys.exit(run())
