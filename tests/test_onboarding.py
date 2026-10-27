"""First-run sequencing and privacy tests; no real credentials or mail traffic."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / "heymail/scripts" / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

engine = load("onboarding_engine", "mail.py")
ui = load("onboarding_ui", "credential_input.py")
FAKE_CODE = "synthetic-not-a-real-authorization-code"


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / "work/test-temp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        Path(self.temp.name).resolve().relative_to(base.resolve())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "config.json"
        self.status = engine.onboarding_path(self.config)
        self.resume = self.root / "上传的简历.pdf"
        self.resume.write_bytes(b"%PDF-1.4\n% synthetic only\n%%EOF")

    def input_args(self, **changes):
        values = dict(provider=None, email="", credential_target="", status_file=self.status,
                      console=False, probe=False, smoke_test=False, launch=False)
        values.update(changes)
        return SimpleNamespace(**values)

    def save_code(self, provider="163"):
        session = ui.InputSession(self.input_args())
        with patch.object(ui.core, "vault_save") as save:
            session.save(provider, FAKE_CODE)
        return session, save

    def setup_args(self, provider="163", **changes):
        state = engine.read_json(self.status)
        values = dict(config=self.config, provider=provider,
                      email="applicant@" + engine.PROVIDERS[provider]["domain"], name="示例同学",
                      resume=Path(state.get("resume_path", self.resume)), credential_target="",
                      school="示例大学", degree="硕士", grade="研一", days="4", months="3个月",
                      start_date="", replace=False, pending_credential=self.status)
        values.update(changes)
        return SimpleNamespace(**values)

    def test_first_status_needs_no_email_or_config(self):
        result = engine.onboarding_state(self.config)
        self.assertEqual(result["phase"], "authorization_required")
        self.assertFalse(self.config.exists())

    def test_authorization_can_be_saved_before_email_and_resume(self):
        session, save = self.save_code("qq")
        self.assertTrue(session.saved)
        target = save.call_args.args[0]
        self.assertEqual(target["email"], "pending")
        self.assertRegex(target["credential_target"], r"^HeyMail/pending/[a-f0-9]{32}$")
        self.assertEqual(engine.onboarding_state(self.config)["phase"], "credential_saved")
        self.assertFalse(self.config.exists())
        self.assertNotIn(FAKE_CODE, self.status.read_text(encoding="utf-8"))

    def test_reopening_does_not_overwrite_saved_pending_code(self):
        self.save_code()
        before = self.status.read_bytes()
        with self.assertRaises(ui.core.MailError):
            ui.InputSession(self.input_args())
        self.assertEqual(self.status.read_bytes(), before)

    def test_resume_cannot_be_collected_before_authorization(self):
        engine.atomic_json(self.status, {"phase": "cancelled"})
        with self.assertRaises(engine.MailError) as result:
            engine.onboarding_resume(self.config, self.resume)
        self.assertEqual(result.exception.code, "save_authorization_code_first")

    def test_uploaded_resume_is_persistent_and_byte_identical(self):
        self.save_code()
        data = self.resume.read_bytes()
        result = engine.onboarding_resume(self.config, self.resume)
        self.assertEqual(result["phase"], "email_required")
        persistent = Path(result["resume_path"])
        self.assertNotEqual(persistent, self.resume)
        self.resume.unlink()
        self.assertEqual(persistent.read_bytes(), data)
        self.assertEqual(engine.read_json(self.status)["resume_sha256"], engine.sha(data))

    def test_email_setup_requires_uploaded_resume_first(self):
        self.save_code()
        with patch.object(engine, "vault") as vault:
            with self.assertRaises(engine.MailError) as result:
                engine.setup(self.setup_args())
            self.assertEqual(result.exception.code, "upload_resume_before_sender_email_setup")
            vault.assert_not_called()
        self.assertFalse(self.config.exists())

    def test_binding_internally_consumes_code_without_plaintext_files(self):
        for provider in ("163", "qq"):
            with self.subTest(provider=provider):
                if self.config.exists():
                    self.config.unlink()
                self.status.unlink(missing_ok=True)
                self.save_code(provider)
                engine.onboarding_resume(self.config, self.resume)
                pending = engine.read_json(self.status)["credential_target"]
                with patch.object(engine, "vault", return_value=FAKE_CODE) as get, \
                        patch.object(engine, "vault_save") as put, \
                        patch.object(engine, "vault_delete_pending") as delete:
                    result = engine.setup(self.setup_args(provider))
                self.assertTrue(result["ok"])
                get.assert_called_once_with({"credential_target": pending, "email": "pending"})
                self.assertEqual(put.call_args.args[0]["provider"], provider)
                delete.assert_called_once_with(pending)
                self.assertEqual(engine.read_json(self.status)["phase"], "configured")
                for file in (self.config, self.status):
                    self.assertNotIn(FAKE_CODE, file.read_text(encoding="utf-8"))
                self.assertNotIn(FAKE_CODE, str(result))

    def test_provider_mismatch_rejected_before_secret_read(self):
        self.save_code("163")
        engine.onboarding_resume(self.config, self.resume)
        with patch.object(engine, "vault") as vault:
            with self.assertRaises(engine.MailError) as result:
                engine.setup(self.setup_args("qq"))
            self.assertEqual(result.exception.code, "pending_provider_mismatch")
            vault.assert_not_called()

    def test_pending_credential_preserved_when_binding_fails(self):
        self.save_code()
        engine.onboarding_resume(self.config, self.resume)
        with patch.object(engine, "vault", return_value=FAKE_CODE), \
                patch.object(engine, "vault_save", side_effect=engine.MailError("credential_save_failed")), \
                patch.object(engine, "vault_delete_pending") as delete:
            with self.assertRaises(engine.MailError):
                engine.setup(self.setup_args())
            delete.assert_not_called()
        self.assertFalse(self.config.exists())
        self.assertEqual(engine.read_json(self.status)["phase"], "resume_saved")

    def test_console_refuses_noninteractive_pipe(self):
        session = ui.InputSession(self.input_args(console=True, provider="163"))
        with patch.object(ui.sys.stdin, "isatty", return_value=False), \
                patch.object(ui.getpass, "getpass") as get, patch.object(ui.core, "vault_save") as save:
            with self.assertRaises(ui.core.MailError):
                ui.console_input(session)
            get.assert_not_called()
            save.assert_not_called()

    def test_gui_failure_produces_safe_fallback_state(self):
        output = io.StringIO()
        with patch.object(ui.sys, "argv", ["credential_input.py", "--status-file", str(self.status)]), \
                patch.object(ui, "gui_input", side_effect=RuntimeError("synthetic_gui_failure")), \
                patch.object(ui, "console_input") as console, redirect_stdout(output):
            self.assertEqual(ui.main(), 1)
            console.assert_not_called()
        self.assertEqual(engine.read_json(self.status)["phase"], "input_unavailable")
        self.assertIn("gui_unavailable_use_console_launcher", output.getvalue())
        self.assertNotIn("synthetic_gui_failure", output.getvalue())

    def test_status_rejects_accidental_secret_fields(self):
        engine.atomic_json(self.status, {"phase": "credential_saved", "authorization_code": FAKE_CODE})
        with self.assertRaises(engine.MailError):
            engine.onboarding_state(self.config)

    def partial_config(self):
        engine.atomic_json(self.config, {"version": 1, "provider": "163", "email": "applicant@163.com",
            "display_name": "示例同学", "resume_path": str(self.resume),
            "credential_target": "HeyMail/163/applicant@163.com", "applicant": {}})

    def test_legacy_profile_without_credential_resumes_authorization(self):
        self.partial_config()
        before = self.config.read_bytes()
        with patch.object(engine, "vault", return_value=False):
            result = engine.onboarding_state(self.config)
        self.assertTrue(result["existing_config"])
        self.assertEqual(result["phase"], "authorization_required")
        self.assertEqual(self.config.read_bytes(), before)

    def test_legacy_profile_does_not_hide_new_saved_authorization(self):
        self.partial_config()
        self.save_code()
        with patch.object(engine, "vault", return_value=False):
            result = engine.onboarding_state(self.config)
        self.assertTrue(result["existing_config"])
        self.assertEqual(result["phase"], "credential_saved")

    def test_working_profile_skips_first_run(self):
        self.partial_config()
        with patch.object(engine, "vault", return_value=True):
            result = engine.onboarding_state(self.config)
        self.assertEqual(result["phase"], "configured")
        self.assertTrue(result["credential_saved"])


if __name__ == "__main__":
    unittest.main()

