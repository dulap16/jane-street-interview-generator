"""Native failure-path checks automatically enabled when a compiler exists."""

import os
from pathlib import Path
import shutil
import tempfile
import unittest

from interview_lab.execution import run_suite

requested = os.environ.get("INTERVIEW_LAB_COMPILER")
COMPILER = next((shutil.which(name) for name in ([requested] if requested else ["g++", "clang++", "cl"])
                 if name and shutil.which(name)), None)
INTERFACE = {"constructor": [], "methods": [
    {"name": "value", "params": [], "returns": "int", "since": 1}]}
CASES = [{"id": "one-value", "constructor": [], "commands": [
    {"method": "value", "args": [], "expect": 7}]}]


@unittest.skipUnless(COMPILER, "No existing C++ compiler; native failure paths remain unverified, not passed.")
class NativeCppFailureTests(unittest.TestCase):
    def execute(self, body, *, output_limit=65536):
        with tempfile.TemporaryDirectory(prefix="interview cpp failure ") as directory:
            root = Path(directory)
            source = root / "candidate.cpp"
            source.write_text(
                "#include <cstdint>\n#include <cstdlib>\n#include <iostream>\n"
                "#include <stdexcept>\n#include <thread>\n#include <chrono>\n"
                "class Solution { public: std::int64_t value() { " + body + " } };\n",
                encoding="utf-8")
            return run_suite("cpp", source, INTERFACE, CASES, root / "work",
                             compiler=COMPILER, timeout=15, output_limit=output_limit)

    def test_cpp_unexpected_runtime_exception(self):
        result = self.execute('throw std::runtime_error("ordinary runtime failure");')
        self.assertEqual(result["status"], "runtime_error", result)

    def test_cpp_wrong_answer(self):
        result = self.execute("return 8;")
        self.assertEqual(result["status"], "wrong_answer", result)

    def test_cpp_executed_loop_times_out_not_just_compilation(self):
        result = self.execute('std::cout << "entered-loop" << std::endl; '
                              'while (true) { std::this_thread::sleep_for(std::chrono::milliseconds(20)); }')
        self.assertEqual(result["status"], "timeout", result)
        self.assertIn("entered-loop", result["stdout"], "Compilation timeout is not an execution-timeout test.")

    def test_cpp_noisy_output_is_bounded(self):
        result = self.execute('for (int i = 0; i < 1000000; ++i) { std::cout << "debug-noise"; } return 7;',
                              output_limit=1024)
        self.assertEqual(result["status"], "output_limit", result)
        self.assertLessEqual(len(result["stdout"].encode("utf-8")), 1024)

    def test_cpp_successful_exit_without_complete_protocol(self):
        result = self.execute("std::_Exit(0);")
        self.assertEqual(result["status"], "protocol_error", result)
