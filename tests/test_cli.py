import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from tests.helpers import SessionCase

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_cold_start_context_is_an_explicit_empty_state(self):
        result = self.call("context")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["phase"], "none")
        self.assertIn("No active session", result.stdout)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="interview cli root with spaces ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(ROOT)

    def call(self, *args, payload=None):
        return subprocess.run([sys.executable, "-m", "interview_lab", "--root", str(self.root), *args],
                              input=json.dumps(payload) if payload is not None else None,
                              capture_output=True, text=True, encoding="utf-8",
                              env=self.env, cwd=self.root, timeout=20)

    def test_installed_style_module_from_space_path(self):
        result = self.call("config")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["language"], "python")
        self.assertFalse((self.root / ".git").exists())

    def test_invalid_cli_setting_reports_error(self):
        result = self.call("config", "--set", "invented=true")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown", json.loads(result.stderr)["error"])
        self.assertNotIn("Traceback", result.stderr)

    def test_malformed_hook_is_not_narration_success(self):
        result = self.call("hook", payload={"hook_event_name": "UserPromptSubmit", "prompt": 42})
        self.assertEqual(result.returncode, 2)
        self.assertIn("hook error", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_unknown_command_and_invalid_id(self):
        self.assertEqual(self.call("invented").returncode, 2)
        result = self.call("status", "../escape")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        missing = self.call("status", "missing-session")
        self.assertEqual(missing.returncode, 2)
        self.assertFalse((self.root / ".interview-lab").exists())

    def test_setup_is_explicit_and_preserves_unrelated_settings(self):
        result = self.call("setup-claude")
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.root / ".claude").exists())
        settings = self.root / ".claude" / "settings.json"
        settings.parent.mkdir()
        settings.write_text('{"permissions":{"allow":["Read"]}}', encoding="utf-8")
        result = self.call("setup-claude", "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(settings.read_text(encoding="utf-8"))
        self.assertEqual(value["permissions"], {"allow": ["Read"]})
        self.assertIn("UserPromptSubmit", value["hooks"])

    def test_statusline_no_active_session(self):
        result = self.call("statusline", payload={"workspace": {"project_dir": str(self.root)}})
        self.assertEqual(result.returncode, 0)
        self.assertIn("no active interview", result.stdout)


class SmokeTests(unittest.TestCase):
    def test_cpp_full_documented_smoke_or_explicit_skip(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "smoke.py"), "--language", "cpp"],
                                capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=180)
        if result.returncode == 77:
            self.assertIn("NOT passed", result.stdout)
            self.skipTest(result.stdout.strip())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: cpp full", result.stdout)

    def test_python_full_documented_smoke(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "smoke.py"), "--language", "python"],
                                capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: python full", result.stdout)


class WatchLiveTests(SessionCase):
    def test_real_watch_updates_without_model_turns_and_expires(self):
        self.now = time.time()
        self.start(duration_minutes=0.05, checkpoints=[])
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        result = subprocess.run(
            [sys.executable, "-m", "interview_lab", "--root", str(self.root),
             "watch", "practice", "--interval", "0.1"],
            capture_output=True, text=True, encoding="utf-8", cwd=self.root, env=env, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(result.stdout.count("practice |"), 2)
        self.assertIn("Session ended: expired", result.stdout)
        self.assertEqual(self.lab.store.load("practice")["phase"], "ended")
