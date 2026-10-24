"""Offline tests only: fake profiles, temporary files, and mocked SMTP/vault."""
from contextlib import redirect_stdout
from email import policy
from email.parser import BytesParser
import importlib.util
import io
import json
from pathlib import Path
import smtplib
import ssl
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

MODULE = Path(__file__).resolve().parents[1] / "heymail/scripts/mail.py"
spec = importlib.util.spec_from_file_location("heymail_engine", MODULE)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        temp_base = Path(__file__).resolve().parents[1] / "work/test-temp"
        temp_base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temp_base)
        # Verify the cleanup target stays inside this dedicated test directory.
        Path(self.temp.name).resolve().relative_to(temp_base.resolve())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.resume = self.root / "原始简历.pdf"
        self.resume.write_bytes(b"%PDF-1.4\n% synthetic test fixture only\n%%EOF")
        self.config = {
            "version": 1, "provider": "163", "email": "applicant@163.com",
            "display_name": "示例同学", "resume_path": str(self.resume),
            "credential_target": "HeyMail/163/applicant@163.com", "applicant": {"name": "示例同学"}}
        self.job = {"to": "hr@example.com", "subject": "示例同学-示例大学-研一-每周4天-3个月",
                    "body": "您好！希望申请贵司实习，简历随附，烦请您审阅，期待您的回复。",
                    "attachment_name": "示例同学-示例大学-研一-每周4天-3个月.pdf"}
        self.draft = self.root / "draft.json"
        self.state = self.root / "session-a"
        self.client = MagicMock()
        self.client.send_message.return_value = {}

    def prepare(self):
        self.draft.write_text(json.dumps(self.job, ensure_ascii=False), encoding="utf-8")
        return engine.prepare(self.config, SimpleNamespace(draft=self.draft, state_dir=self.state))

    def args(self, result, confirm="发送"):
        return SimpleNamespace(state_dir=self.state, expected_digest=result["digest"], confirm=confirm)

    def error_code(self, code, callable_, *args):
        with self.assertRaises(engine.MailError) as captured:
            callable_(*args)
        self.assertEqual(captured.exception.code, code)

    def test_prepare_is_offline_and_original_unchanged(self):
        original = self.resume.read_bytes()
        with patch.object(engine, "vault") as vault, patch.object(engine, "connect") as connect:
            result = self.prepare()
        vault.assert_not_called()
        connect.assert_not_called()
        self.assertEqual(Path(result["attachment"]).read_bytes(), original)
        self.assertEqual(self.resume.read_bytes(), original)
        self.assertEqual(result["body"], self.job["body"])

    def test_both_providers_select_verified_tls_hosts(self):
        for provider, domain in (("163", "163.com"), ("qq", "qq.com")):
            config = {**self.config, "provider": provider, "email": "applicant@" + domain}
            engine.validate_config(config)
            with patch.object(engine.smtplib, "SMTP_SSL", return_value=self.client) as smtp:
                engine.connect(config, "fake-offline-credential")
            args, kwargs = smtp.call_args
            self.assertEqual(args, ("smtp." + domain, 465))
            self.assertTrue(kwargs["context"].check_hostname)
            self.assertEqual(kwargs["context"].verify_mode, ssl.CERT_REQUIRED)
            self.client.login.assert_called_with(config["email"], "fake-offline-credential")

    def test_valid_send_preserves_unicode_mime_and_has_no_footer(self):
        result = self.prepare()
        with patch.object(engine, "vault", return_value="fake-offline-credential"), \
                patch.object(engine, "connect", return_value=self.client):
            receipt = engine.send(self.config, self.args(result))
        self.assertEqual(receipt["status"], "accepted")
        self.client.send_message.assert_called_once()
        msg = self.client.send_message.call_args.args[0]
        parsed = BytesParser(policy=policy.default).parsebytes(msg.as_bytes(policy=policy.SMTP))
        self.assertEqual(str(parsed["Subject"]), self.job["subject"])
        self.assertEqual(parsed.get_body(preferencelist=("plain",)).get_content().strip(), self.job["body"])
        attachment = list(parsed.iter_attachments())[0]
        self.assertEqual(attachment.get_filename(), self.job["attachment_name"])
        self.assertEqual(attachment.get_payload(decode=True), self.resume.read_bytes())
        self.assertNotIn("Agent Mail", parsed.get_body().get_content())

    def test_only_exact_confirmation_accepted(self):
        result = self.prepare()
        for text in ("", "不要发送", "发送了吗", "确认", "发送。", " 发送 "):
            with patch.object(engine, "vault") as vault:
                self.error_code("exact_user_send_confirmation_required", engine.send,
                                self.config, self.args(result, text))
                vault.assert_not_called()

    def test_stale_preview_cannot_send_new_draft(self):
        previous = self.prepare()
        self.job["to"] = "another@example.com"
        self.prepare()
        with patch.object(engine, "vault") as vault:
            self.error_code("confirmation_is_for_a_different_preview", engine.send,
                            self.config, self.args(previous))
            vault.assert_not_called()

    def test_attachment_tampering_blocks_before_credential_access(self):
        result = self.prepare()
        Path(result["attachment"]).write_bytes(b"different bytes")
        with patch.object(engine, "vault") as vault:
            self.error_code("attachment_changed_prepare_and_review_again", engine.send,
                            self.config, self.args(result))
            vault.assert_not_called()

    def test_manifest_tampering_blocks(self):
        result = self.prepare()
        _, folder, manifest, _ = engine.read_pending(self.state)
        manifest["to"] = "changed@example.com"
        engine.atomic_json(folder / "manifest.json", manifest)
        self.error_code("draft_changed_prepare_and_review_again", engine.send,
                        self.config, self.args(result))

    def test_sender_change_requires_new_preview(self):
        result = self.prepare()
        changed = {**self.config, "display_name": "另一个名字"}
        self.error_code("sender_changed_prepare_and_review_again", engine.send,
                        changed, self.args(result))

    def test_duplicate_and_uncertain_receipts_never_reconnect(self):
        result = self.prepare()
        _, folder, _, _ = engine.read_pending(self.state)
        for status in ("accepted", "submitting", "uncertain"):
            engine.atomic_json(folder / "receipt.json", {"status": status})
            with patch.object(engine, "vault") as vault, patch.object(engine, "connect") as connect:
                self.error_code("already_submitted_or_uncertain_do_not_resend", engine.send,
                                self.config, self.args(result))
                vault.assert_not_called()
                connect.assert_not_called()

    def test_lock_prevents_concurrent_send_and_prepare(self):
        result = self.prepare()
        with engine.state_lock(self.state):
            self.error_code("workflow_locked_check_previous_process", engine.send,
                            self.config, self.args(result))
            self.error_code("workflow_locked_check_previous_process", self.prepare)
            self.assertTrue((self.state / ".mail.lock").exists())
        self.assertFalse((self.state / ".mail.lock").exists())

    def test_network_failure_after_data_marks_uncertain(self):
        result = self.prepare()
        self.client.send_message.side_effect = TimeoutError()
        with patch.object(engine, "vault", return_value="fake-offline-credential"), \
                patch.object(engine, "connect", return_value=self.client):
            with self.assertRaises(TimeoutError):
                engine.send(self.config, self.args(result))
        _, folder, _, _ = engine.read_pending(self.state)
        self.assertEqual(engine.read_json(folder / "receipt.json")["status"], "uncertain")
        self.assertFalse((self.state / ".mail.lock").exists())

    def test_explicit_smtp_rejection_is_recorded(self):
        result = self.prepare()
        self.client.send_message.side_effect = smtplib.SMTPDataError(550, b"synthetic rejection")
        with patch.object(engine, "vault", return_value="fake-offline-credential"), \
                patch.object(engine, "connect", return_value=self.client):
            with self.assertRaises(smtplib.SMTPDataError):
                engine.send(self.config, self.args(result))
        _, folder, _, _ = engine.read_pending(self.state)
        self.assertEqual(engine.read_json(folder / "receipt.json")["status"], "rejected")

    def test_quit_failure_does_not_turn_accepted_into_retry(self):
        result = self.prepare()
        self.client.quit.side_effect = smtplib.SMTPServerDisconnected()
        with patch.object(engine, "vault", return_value="fake-offline-credential"), \
                patch.object(engine, "connect", return_value=self.client):
            self.assertEqual(engine.send(self.config, self.args(result))["status"], "accepted")
        self.client.close.assert_called_once()

    def test_authentication_failure_never_submits(self):
        result = self.prepare()
        with patch.object(engine, "vault", return_value="fake-offline-credential"), \
                patch.object(engine, "connect", side_effect=smtplib.SMTPAuthenticationError(535, b"fake")):
            with self.assertRaises(smtplib.SMTPAuthenticationError):
                engine.send(self.config, self.args(result))
        _, folder, _, _ = engine.read_pending(self.state)
        self.assertFalse((folder / "receipt.json").exists())
        self.client.send_message.assert_not_called()

    def test_different_sessions_do_not_share_pending(self):
        first = self.prepare()
        self.state = self.root / "session-b"
        self.job["to"] = "second@example.com"
        second = self.prepare()
        self.assertNotEqual(first["digest"], second["digest"])
        self.assertEqual(engine.read_pending(self.root / "session-a")[2]["to"], "hr@example.com")

    def test_invalid_recipients_and_header_injection_rejected(self):
        for recipient in ("a@example.com,b@example.com", "a@example.com\r\nBcc:other@example.com", "not-an-email"):
            self.job["to"] = recipient
            self.error_code("invalid_single_email_address", self.prepare)
        self.job["to"] = "hr@example.com"
        self.job["subject"] = "title\r\nBcc:other@example.com"
        self.error_code("invalid_subject", self.prepare)

    def test_secret_fields_and_arbitrary_smtp_hosts_rejected(self):
        for extra in ({"password": "fake"}, {"smtp_host": "untrusted.example"}):
            self.error_code("config_unknown_fields_no_secrets_allowed", engine.validate_config,
                            {**self.config, **extra})
        self.error_code("provider_email_domain_mismatch", engine.validate_config,
                        {**self.config, "provider": "qq"})

    def test_extension_and_filename_rules(self):
        self.job["attachment_name"] = "renamed.docx"
        self.error_code("attachment_extension_must_match_original", self.prepare)
        self.job["attachment_name"] = "公司:岗位/姓名.pdf"
        self.assertEqual(Path(self.prepare()["attachment"]).name, "公司-岗位-姓名.pdf")
        self.assertEqual(engine.safe_filename("CON.pdf"), "_CON.pdf")

    def test_docx_bytes_and_extension_preserved(self):
        self.resume = self.root / "resume.docx"
        self.resume.write_bytes(b"PK\x03\x04 synthetic fixture only")
        self.config["resume_path"] = str(self.resume)
        self.job["attachment_name"] = "示例简历.docx"
        result = self.prepare()
        self.assertEqual(Path(result["attachment"]).read_bytes(), self.resume.read_bytes())

    def test_error_output_never_echoes_authentication_payload(self):
        stream = io.StringIO()
        with patch.object(engine, "main", side_effect=smtplib.SMTPAuthenticationError(535, b"fake-sensitive-payload")), \
                redirect_stdout(stream):
            self.assertEqual(engine.run(), 1)
        self.assertNotIn("fake-sensitive-payload", stream.getvalue())
        self.assertEqual(json.loads(stream.getvalue())["smtp_code"], 535)


if __name__ == "__main__":
    unittest.main()
