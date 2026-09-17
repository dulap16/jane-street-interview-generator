import json
from pathlib import Path
import tempfile
import unittest

from interview_lab import config
from interview_lab.narration import comments
from interview_lab.storage import LabError, identifier, read_json, safe_child


class ConfigTests(unittest.TestCase):
    def test_symlink_escape_is_rejected_when_host_supports_it(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as external:
            root = Path(directory)
            try:
                (root / "link").symlink_to(Path(external), target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"Host cannot create directory symlinks: {exc}")
            with self.assertRaises(LabError):
                safe_child(root, "link", "state.json")

    def test_defaults_and_preset_override(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(config.resolve(root)["duration_minutes"], 45)
            self.assertEqual(config.resolve(root, {"preset": "short"})["duration_minutes"], 25)
            self.assertEqual(config.resolve(root, {"preset": "short"})["session_format"], "focused")
            self.assertEqual(config.resolve(root, {"preset": "extended", "session_format": "focused"})["session_format"], "focused")
            self.assertEqual(config.resolve(root, {"preset": "short", "duration_minutes": 11})["duration_minutes"], 11)

    def test_unknown_invalid_nonfinite_and_bool_values(self):
        bad = [{"unknown": True}, {"duration_minutes": True}, {"duration_minutes": float("nan")},
               {"checkpoints": [1, 1]}, {"checkpoints": [False]}, {"style": "hostile"},
               {"compiler": "C:\\absolute\\g++.exe"}, {"python_executable": "python && bad"},
               {"docs_allowed": "yes"}, {"output_limit": True}, {"test_timeout": 0}]
        with tempfile.TemporaryDirectory() as directory:
            for override in bad:
                with self.subTest(override=override), self.assertRaises(LabError):
                    config.resolve(Path(directory), override)

    def test_persist_and_parse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = config.parse_overrides(["language=cpp", "docs_allowed=false", "checkpoints=[5,1]"])
            config.save(root, value)
            self.assertFalse(config.resolve(root)["docs_allowed"])
            with self.assertRaises(LabError):
                config.parse_overrides(["mode=study", "mode=interview"])

    def test_strict_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for text in ('{"a":1,"a":2}', '{"n":NaN}', '{bad', "[" * 2000 + "0" + "]" * 2000):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(LabError):
                    read_json(path)

    def test_safe_child_rejects_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(LabError):
                safe_child(Path(directory), "..", "outside")


class NarrationTests(unittest.TestCase):
    def test_python_only_standalone_real_comments(self):
        source = '''text = "# THINK: not a comment"
text2 = """
# THINK: inside a string
"""
# ordinary comment
# THINK: real reasoning
answer = 4 # THINK: inline not narration-only
'''
        self.assertEqual(comments(source, "python"), [
            {"line": 6, "text": "real reasoning", "original": "# THINK: real reasoning"}])
        self.assertIn("# THINK: inside a string", source)

    def test_incomplete_python_conservatively_returns_no_metadata(self):
        self.assertEqual(comments('"""\n# THINK: uncertain\n', "python"), [])

    def test_cpp_raw_normal_and_block_strings(self):
        source = '''const char* a = "// THINK: not a comment";
auto b = R"tag(
// THINK: raw
)tag";
/* // THINK: blocked */
// THINK: real reasoning
int answer = 4; // THINK: inline
'''
        self.assertEqual(comments(source, "cpp"), [
            {"line": 6, "text": "real reasoning", "original": "// THINK: real reasoning"}])

    def test_cpp_continued_comment_is_not_rewritten(self):
        source = "// THINK: continued \\\n// THINK: still same comment\n// THINK: separate\n"
        self.assertEqual(comments(source, "cpp"), [
            {"line": 3, "text": "separate", "original": "// THINK: separate"}])
