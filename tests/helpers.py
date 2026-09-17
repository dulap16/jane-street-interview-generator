import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from interview_lab.session import Lab


REFERENCE = """class Solution:
    def __init__(self):
        self.value = 0
    def add(self, value):
        self.value += value
        return self.value
    def reset(self):
        self.value = 0
"""


def pack_fixture():
    return {
        "schema": 1, "id": "counter", "title": "A tiny counter", "family": "stream",
        "origin": {"kind": "generated", "seed": "test-only"},
        "interface": {"constructor": [], "methods": [
            {"name": "add", "params": [{"name": "value", "type": "int"}], "returns": "int", "since": 1},
            {"name": "reset", "params": [], "returns": "void", "since": 2}]},
        "parts": [
            {"title": "Count", "prompt": "Add signed values and return their running total.",
             "public": [{"id": "public-add", "constructor": [], "commands": [
                 {"method": "add", "args": [1], "expect": 1}]}],
             "hidden": [{"id": "hidden-add", "constructor": [], "commands": [
                 {"method": "add", "args": [-7], "expect": -7}]}],
             "invariants": ["The total starts at zero and changes only by the signed input."],
             "hints": ["Track state.", "Keep one total.", "Add to the current total."],
             "failure_question": "Which signs have you tested?"},
            {"title": "Reset", "prompt": "FUTURE_SECRET Add reset() to clear the total.",
             "public": [{"id": "public-reset", "constructor": [], "commands": [
                 {"method": "add", "args": [2], "expect": 2},
                 {"method": "reset", "args": [], "expect": None},
                 {"method": "add", "args": [3], "expect": 3}]}],
             "hidden": [{"id": "hidden-reset", "constructor": [], "commands": [
                 {"method": "reset", "args": [], "expect": None}]}],
             "invariants": ["Reset is idempotent."], "hints": ["Consider state.", "Use the initial value.", "Set total to zero."],
             "failure_question": "What happens if the operation repeats?"}],
        "references": {"python": "reference.py", "cpp": "reference.cpp"},
    }


def passed_suite(language, source, interface, cases, work_dir, **kwargs):
    return {"status": "passed", "passed": len(cases), "total": len(cases),
            "cases": [{"id": c["id"], "status": "passed"} for c in cases], "diagnostics": ""}


class SessionCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="interview lab tests ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = 1000.0
        self.lab = Lab(self.root, clock=lambda: self.now)
        self.packdir = self.root / "authored"
        self.packdir.mkdir()
        self.packpath = self.packdir / "pack.json"
        self.packpath.write_text(json.dumps(pack_fixture()), encoding="utf-8")
        (self.packdir / "reference.py").write_text(REFERENCE, encoding="utf-8")
        (self.packdir / "reference.cpp").write_text("// Python-only fixture", encoding="utf-8")
        self.runner = patch("interview_lab.execution.run_suite", side_effect=passed_suite)
        self.mock_runner = self.runner.start()
        self.addCleanup(self.runner.stop)
        probe = patch("interview_lab.execution.probe_python",
                      return_value={"available": True, "version": [3, 12, 10], "error": ""}, create=True)
        probe.start()
        self.addCleanup(probe.stop)

    def prepare(self, **overrides):
        return self.lab.prepare(self.packpath, "practice", overrides)

    def start(self, **overrides):
        self.prepare(**overrides)
        self.lab.start("practice", False)
        return self.lab.store.load("practice")

    def solve(self):
        state = self.lab.store.load("practice")
        self.lab.source_path(state).write_text(REFERENCE, encoding="utf-8")

    def complete(self):
        self.start()
        self.solve()
        self.lab.test("practice", done=True)
        self.lab.reveal("practice")
        self.lab.test("practice", done=True)
        self.lab.reveal("practice")
