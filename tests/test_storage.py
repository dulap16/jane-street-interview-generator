import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from interview_lab.storage import atomic_json, read_json


class AtomicStorageTests(unittest.TestCase):
    def test_interrupted_replace_leaves_old_complete_file(self):
        with tempfile.TemporaryDirectory(prefix="interview atomic ") as directory:
            path = Path(directory) / "state.json"
            atomic_json(path, {"old": [1, 2, 3]})
            with patch("interview_lab.storage.os.replace", side_effect=OSError("injected interruption")):
                with self.assertRaises(OSError):
                    atomic_json(path, {"new": [4, 5, 6]})
            self.assertEqual(read_json(path), {"old": [1, 2, 3]})
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["state.json"])

    def test_atomic_json_preserves_unicode_and_rejects_nonfinite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            atomic_json(path, {"unicode": "\u03bb\U0001f680", "nul": "\0"})
            self.assertEqual(read_json(path), {"unicode": "\u03bb\U0001f680", "nul": "\0"})
            with self.assertRaises(ValueError):
                atomic_json(path, {"number": float("inf")})
            self.assertIn("unicode", read_json(path))
