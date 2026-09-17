import copy
import ctypes
import json
import os
from pathlib import Path
import shutil
import sys
import time
import unittest
from unittest import mock
import uuid

from interview_lab import execution, schema


def _interface(returns="int", params=None, constructor=None):
    return {
        "constructor": constructor or [],
        "methods": [{"name": "run", "params": params or [], "returns": returns, "since": 1}],
    }


def _case(expect=1, args=None, id_="one", constructor=None):
    return {"id": id_, "constructor": constructor or [], "commands": [{"method": "run", "args": args or [], "expect": expect}]}


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.root = Path.cwd() / (".execution-tests-" + uuid.uuid4().hex)
        self.root.mkdir()
        self.work = self.root / "work with spaces"
        self.source = self.root / "candidate with spaces.py"

    def tearDown(self):
        shutil.rmtree(self.root)

    def run_python(self, source, interface=None, cases=None, **options):
        self.source.write_text(source, encoding="utf-8")
        return execution.run_suite(
            "python", self.source, interface or _interface(), cases or [_case()], self.work,
            python_executable=sys.executable, **options,
        )

    def assert_status(self, result, status):
        self.assertEqual(result["status"], status, result)
        self.assertIn("diagnostics", result)
        self.assertIs(type(result["passed"]), int)
        self.assertIs(type(result["total"]), int)
        self.assertEqual(result["total"], len(result["cases"]))
        self.assertEqual(result["passed"], sum(case["status"] == "passed" for case in result["cases"]))

    def test_pass_and_output_is_separate(self):
        result = self.run_python(
            "import sys\nprint('import output')\nclass Solution:\n"
            " def run(self):\n  print('debug output'); print('debug error', file=sys.stderr); return 1\n"
        )
        self.assert_status(result, "passed")
        self.assertIn("import output", result["stdout"])
        self.assertIn("debug output", result["stdout"])
        self.assertIn("debug error", result["stderr"])
        self.assertEqual(list(self.work.iterdir()), [])
        self.assertTrue(self.source.is_file())

    def test_primitive_and_nested_roundtrips(self):
        values = [
            ("int", -(1 << 63)), ("int", (1 << 63) - 1), ("bool", False),
            ("str", 'nul\0 "quoted" \\ \r\n é 中文 🦊'),
            ({"list": {"map": {"optional": "str"}}}, [{"nul\0": ["not a string"]}]),
            ({"optional": {"list": "int"}}, None),
            ({"optional": {"list": "int"}}, [0, -1]),
            ({"map": {"list": {"optional": "str"}}}, {"nul\0🦉": ["", "文", None]}),
        ]
        # The deliberately wrong fixture below is rejected before launch.
        bad = values.pop(4)
        result = self.run_python("raise AssertionError('must not execute')", _interface(bad[0], [{"name": "value", "type": bad[0]}]), [_case(bad[1], [bad[1]])])
        self.assert_status(result, "infrastructure_error")
        for descriptor, value in values:
            with self.subTest(descriptor=descriptor, value=value):
                result = self.run_python(
                    "class Solution:\n def run(self, value): return value\n",
                    _interface(descriptor, [{"name": "value", "type": descriptor}]), [_case(value, [value])],
                )
                self.assert_status(result, "passed")

    def test_strict_actual_values_wrong_answers(self):
        for expression, descriptor, expect in (
            ("True", "int", 1), ("1", "bool", True), ("1.0", "int", 1),
            ("2**63", "int", 0), ("float('nan')", "int", 0),
            ("{'x': [True]}", {"map": {"list": "int"}}, {"x": [1]}),
            ("'\\ud800'", "str", ""), ("set()", {"list": "int"}, []),
            ("(1,)", {"list": "int"}, [1]), ("1", "void", None),
        ):
            with self.subTest(expression=expression):
                result = self.run_python(
                    f"class Solution:\n def run(self): return {expression}\n",
                    _interface(descriptor), [_case(expect)],
                )
                self.assert_status(result, "wrong_answer")

    def test_stateful_commands_constructor_and_reset(self):
        interface = _interface(constructor=[{"name": "start", "type": "int"}])
        cases = [_case(5, constructor=[4]), _case(2, id_="two", constructor=[1])]
        cases[0]["commands"].append({"method": "run", "args": [], "expect": 6})
        result = self.run_python(
            "class Solution:\n def __init__(self, start): self.n = start\n"
            " def run(self): self.n += 1; return self.n\n",
            interface, cases,
        )
        self.assert_status(result, "passed")
        self.assertEqual(result["passed"], 2)

    def test_mutation_and_snapshot_even_after_exception(self):
        interface = _interface("void", [
            {"name": "values", "type": {"list": "int"}, "mode": "inout"},
            {"name": "fail", "type": "bool"},
        ])
        case = _case(None, [[1], False])
        case["commands"][0]["after"] = {"values": [1, 7]}
        case["commands"].append({
            "method": "run", "args": [[2], True], "raises": "invalid_argument", "after": {"values": [2, 7]},
        })
        original = copy.deepcopy(case)
        result = self.run_python(
            "class Solution:\n def run(self, values, fail):\n"
            "  values.append(7)\n  if fail: raise ValueError('after mutation')\n",
            interface, [case],
        )
        self.assert_status(result, "passed")
        self.assertEqual(case, original)
        self.assertEqual(result["cases"][0]["commands"][1]["actual"]["after"]["values"]["value"], [2, 7])

    def test_wrong_mutation_after_expected_exception(self):
        interface = _interface("void", [{"name": "values", "type": {"list": "int"}, "mode": "inout"}])
        case = _case(None, [[]])
        case["commands"] = [{"method": "run", "args": [[]], "raises": "runtime_error", "after": {"values": [9]}}]
        result = self.run_python(
            "class Solution:\n def run(self, values): values.append(3); raise RuntimeError('x')\n",
            interface, [case],
        )
        self.assert_status(result, "wrong_answer")
        self.assertIn("after.values", result["diagnostics"])

    def test_map_mutation_and_invalid_unasserted_mutation(self):
        descriptor = {"map": {"list": "int"}}
        interface = _interface("void", [{"name": "values", "type": descriptor, "mode": "inout"}])
        case = _case(None, [{"x": [1]}])
        case["commands"][0]["after"] = {"values": {"x": [1, 2], "nul\0": []}}
        self.assert_status(self.run_python(
            "class Solution:\n def run(self, values): values['x'].append(2); values['nul\\0'] = []\n",
            interface, [case],
        ), "passed")
        del case["commands"][0]["after"]
        self.assert_status(self.run_python(
            "class Solution:\n def run(self, values): values['x'].append(True)\n",
            interface, [case],
        ), "wrong_answer")

    def test_return_and_after_values_are_snapshotted(self):
        descriptor = {"list": "int"}
        interface = _interface(descriptor, [{"name": "values", "type": descriptor, "mode": "inout"}])
        case = _case([1], [[1]])
        case["commands"][0]["after"] = {"values": [1]}
        case["commands"].append({"method": "run", "args": [[2]], "expect": [2]})
        result = self.run_python(
            "class Solution:\n def run(self, values):\n"
            "  if hasattr(self, 'old'): self.old.append(99)\n"
            "  self.old = values\n  return values\n",
            interface, [case],
        )
        self.assert_status(result, "passed")

    def test_expected_exceptions(self):
        for exception, mapped in (("ValueError", "invalid_argument"), ("IndexError", "out_of_range"),
                                  ("KeyError", "out_of_range"), ("RuntimeError", "runtime_error")):
            case = _case()
            case["commands"] = [{"method": "run", "args": [], "raises": mapped}]
            with self.subTest(exception=exception):
                self.assert_status(self.run_python(
                    f"class Solution:\n def run(self): raise {exception}('expected')\n", cases=[case],
                ), "passed")

    def test_exception_mismatch_is_wrong_answer(self):
        case = _case()
        case["commands"] = [{"method": "run", "args": [], "raises": "invalid_argument"}]
        for implementation in ("return 1", "raise RuntimeError('wrong')", "raise TypeError('wrong')"):
            with self.subTest(implementation=implementation):
                self.assert_status(self.run_python(
                    f"class Solution:\n def run(self): {implementation}\n", cases=[case],
                ), "wrong_answer")

    def test_unexpected_exception_is_runtime_error(self):
        self.assert_status(self.run_python(
            "class Solution:\n def run(self): raise ValueError('unexpected')\n",
        ), "runtime_error")

    def test_import_and_constructor_errors_are_runtime_errors(self):
        for source in (
            "raise RuntimeError('import failed')",
            "import module_that_does_not_exist_interview_lab",
            "class Solution:\n def __init__(self): raise ValueError('constructor failed')",
            "class NotSolution: pass",
            "Solution = 4",
            "class Solution: pass",
        ):
            with self.subTest(source=source):
                self.assert_status(self.run_python(source), "runtime_error")

    def test_syntax_errors_are_compile_errors(self):
        for source in ("class Solution(\n", "class Solution:\n \0"):
            with self.subTest(source=source):
                self.assert_status(self.run_python(source), "compile_error")

    def test_invalid_source_encoding_is_compile_error(self):
        self.source.write_bytes(b"\xff")
        result = execution.run_suite("python", self.source, _interface(), [_case()], self.work)
        self.assert_status(result, "compile_error")

    def test_nonzero_exit_is_crash(self):
        result = self.run_python("import os\nclass Solution:\n def run(self): os._exit(23)\n")
        self.assert_status(result, "crash")
        self.assertIn("23", result["diagnostics"])

    def test_crash_during_import(self):
        self.assert_status(self.run_python("import os\nos._exit(19)\n"), "crash")

    def test_success_exit_without_protocol_is_protocol_error(self):
        self.assert_status(self.run_python("import os\nos._exit(0)\n"), "protocol_error")

    def test_malformed_private_protocol(self):
        self.assert_status(self.run_python(
            "import os, sys\nfrom pathlib import Path\n"
            "Path(sys.argv[2]).write_text('not json\\n')\nos._exit(0)\n",
        ), "protocol_error")

    def test_timeout_import_and_method(self):
        for source in (
            "while True: pass\n",
            "class Solution:\n def run(self):\n  while True: pass\n",
        ):
            with self.subTest(source=source):
                start = time.monotonic()
                result = self.run_python(source, timeout=0.3)
                self.assert_status(result, "timeout")
                self.assertLess(time.monotonic() - start, 5)
                self.assertEqual(list(self.work.iterdir()), [])

    def test_noisy_stdout_stderr_and_protocol_are_bounded(self):
        for source, limit in (
            ("import os\nwhile True: os.write(1, b'x' * 4096)\n", 128),
            ("import os\nwhile True: os.write(2, b'x' * 4096)\n", 128),
            ("class Solution:\n def run(self): return 1\n", 32),
        ):
            with self.subTest(source=source):
                result = self.run_python(source, timeout=1, output_limit=limit)
                self.assert_status(result, "output_limit")
                self.assertLessEqual(len(result["stdout"].encode()) + len(result["stderr"].encode()), limit)

    def test_bad_harness_inputs_never_run_candidate(self):
        self.source.write_text("raise AssertionError('must not run')", encoding="utf-8")
        for options in (
            {"language": "rust"}, {"cpp_standard": "c++23"}, {"timeout": float("nan")},
            {"timeout": True}, {"timeout": 0}, {"output_limit": False}, {"output_limit": 0},
            {"python_executable": ""}, {"interface": {}}, {"cases": []},
        ):
            arguments = dict(
                language="python", source=self.source, interface=_interface(), cases=[_case()], work_dir=self.work,
            )
            arguments.update(options)
            with self.subTest(options=options):
                self.assert_status(execution.run_suite(**arguments), "infrastructure_error")

    def test_missing_executable_and_source_are_infrastructure_errors(self):
        self.assert_status(self.run_python(
            "class Solution:\n def run(self): return 1\n", compiler="missing-unused-compiler",
        ), "passed")
        result = execution.run_suite(
            "python", self.source, _interface(), [_case()], self.work,
            python_executable="missing-interview-python-executable",
        )
        self.assert_status(result, "infrastructure_error")
        self.source.unlink()
        self.assert_status(execution.run_suite("python", self.source, _interface(), [_case()], self.work), "infrastructure_error")

    def test_source_bound(self):
        self.source.write_bytes(b"#" * (schema.MAX_SOURCE_BYTES + 1))
        result = execution.run_suite("python", self.source, _interface(), [_case()], self.work)
        self.assert_status(result, "infrastructure_error")

    def test_partial_case_pass_count_and_status_precedence(self):
        cases = [_case(1), _case(2, id_="wrong")]
        result = self.run_python("class Solution:\n def run(self): return 1\n", cases=cases)
        self.assert_status(result, "wrong_answer")
        self.assertEqual(result["passed"], 1)

    def test_cpp_missing_compiler_and_simulated_compiler_failures(self):
        self.source = self.root / "answer.cpp"
        self.source.write_text("class Solution {};", encoding="utf-8")
        with mock.patch.object(execution, "find_compiler", return_value=None):
            self.assert_status(
                execution.run_suite("cpp", self.source, _interface(), [_case()], self.work),
                "infrastructure_error",
            )
        for process, expected in (
            (execution._ProcessResult(1, "", "error: expected ';'"), "compile_error"),
            (execution._ProcessResult(-1, "", "", timeout=True), "timeout"),
            (execution._ProcessResult(-1, "", "noisy", output_limit=True), "output_limit"),
            (execution._ProcessResult(0, "", ""), "infrastructure_error"),
        ):
            with self.subTest(expected=expected):
                with mock.patch.object(execution, "find_compiler", return_value="fake compiler"):
                    with mock.patch.object(execution, "_run_process", return_value=process):
                        result = execution.run_suite("cpp", self.source, _interface(), [_case()], self.work)
                self.assert_status(result, expected)
                if expected == "compile_error":
                    self.assertIn("expected ';'", result["diagnostics"])

    def test_candidate_cleanup_readonly_file(self):
        self.assert_status(self.run_python(
            "import os\nfrom pathlib import Path\n"
            "Path('readonly.txt').write_text('owned')\nos.chmod('readonly.txt', 0o400)\n"
            "class Solution:\n def run(self): return 1\n",
        ), "passed")
        self.assertEqual(list(self.work.iterdir()), [])

    def test_total_timeout_compilation_exhaustion_prevents_execution(self):
        self.source = self.root / "answer.cpp"
        self.source.write_text("class Solution {};", encoding="utf-8")
        for elapsed in (2.0, 2.5):
            clock = [100.0]

            def compile_only(argv, cwd, timeout, output_limit, protocol=None):
                self.assertIsNone(protocol)
                self.assertEqual(timeout, 2.0)
                clock[0] += elapsed
                return execution._ProcessResult(0, "", "")

            with self.subTest(elapsed=elapsed):
                with mock.patch.object(execution.time, "monotonic", side_effect=lambda: clock[0]):
                    with mock.patch.object(execution, "find_compiler", return_value="fake compiler"):
                        with mock.patch.object(execution, "_run_process", side_effect=compile_only) as run:
                            result = execution.run_suite(
                                "cpp", self.source, _interface(), [_case()], self.work,
                                timeout=4.0, total_timeout=2.0,
                            )
                self.assert_status(result, "timeout")
                self.assertIn("overall", result["diagnostics"])
                self.assertEqual(run.call_count, 1, "candidate must not launch after compilation used the total budget")
                self.assertEqual(list(self.work.iterdir()), [])

    def test_total_timeout_caps_each_phase_without_changing_omitted_semantics(self):
        self.source = self.root / "answer.cpp"
        self.source.write_text("class Solution {};", encoding="utf-8")
        for total_timeout, elapsed, limits, expected in (
            (5.0, (3.0, 1.0), [4.0, 2.0], "passed"),
            (None, (3.5, 3.5), [4.0, 4.0], "passed"),
            (5.0, (3.0, 2.0), [4.0, 2.0], "timeout"),
        ):
            clock = [100.0]
            seen = []

            def process(argv, cwd, timeout, output_limit, protocol=None):
                seen.append(timeout)
                if protocol is None:
                    Path(argv[-1]).write_bytes(b"mock executable")
                    clock[0] += elapsed[0]
                else:
                    record = {
                        "version": 1, "id": "one", "constructor": {"kind": "ok"},
                        "commands": [{"method": "run", "result": {"kind": "value", "value": 1}, "after": {}}],
                    }
                    protocol.write_text(
                        json.dumps(record) + "\n" + json.dumps({"version": 1, "done": 1}) + "\n",
                        encoding="utf-8",
                    )
                    clock[0] += elapsed[1]
                return execution._ProcessResult(0, "", "")

            with self.subTest(total_timeout=total_timeout, elapsed=elapsed):
                with mock.patch.object(execution.time, "monotonic", side_effect=lambda: clock[0]):
                    with mock.patch.object(execution, "find_compiler", return_value="fake compiler"):
                        with mock.patch.object(execution, "_run_process", side_effect=process):
                            result = execution.run_suite(
                                "cpp", self.source, _interface(), [_case()], self.work,
                                timeout=4.0, total_timeout=total_timeout,
                            )
                self.assert_status(result, expected)
                self.assertEqual(seen, limits)

    def test_total_timeout_preparation_exhaustion_prevents_first_launch(self):
        clock = [100.0]
        validate = execution.validate_cases

        def slow_validation(interface, cases):
            validate(interface, cases)
            clock[0] += 1.0

        with mock.patch.object(execution.time, "monotonic", side_effect=lambda: clock[0]):
            with mock.patch.object(execution, "validate_cases", side_effect=slow_validation):
                with mock.patch.object(execution, "_run_process") as run:
                    result = self.run_python(
                        "class Solution:\n def run(self): return 1\n",
                        timeout=3.0, total_timeout=0.5,
                    )
        self.assert_status(result, "timeout")
        run.assert_not_called()

    def test_total_timeout_validation(self):
        for total_timeout in (True, False, 0, -1, "3", float("nan"), float("inf"), -(float("inf")), 10**10000):
            with self.subTest(value_type=type(total_timeout).__name__):
                result = self.run_python(
                    "class Solution:\n def run(self): return 1\n", total_timeout=total_timeout,
                )
                self.assert_status(result, "infrastructure_error")
                self.assertIn("total_timeout", result["diagnostics"])

    def test_python_total_timeout_caps_real_execution(self):
        start = time.monotonic()
        result = self.run_python(
            "import time\nclass Solution:\n def run(self): time.sleep(60); return 1\n",
            timeout=3.0, total_timeout=0.25,
        )
        self.assert_status(result, "timeout")
        self.assertLess(time.monotonic() - start, 3)
        self.assertEqual(list(self.work.iterdir()), [])

    def test_cleanup_failure_is_reported_not_hidden(self):
        with mock.patch.object(execution, "_cleanup_run", side_effect=OSError("locked")):
            result = self.run_python("class Solution:\n def run(self): return 1\n")
        self.assert_status(result, "infrastructure_error")
        self.assertIn("could not clean owned run directory", result["diagnostics"])

    def test_same_size_source_edits_do_not_use_stale_bytecode(self):
        self.assert_status(self.run_python("class Solution:\n def run(self): return 1\n"), "passed")
        timestamp = self.source.stat().st_mtime
        self.source.write_text("class Solution:\n def run(self): return 2\n", encoding="utf-8")
        os.utime(self.source, (timestamp, timestamp))
        self.assert_status(
            execution.run_suite("python", self.source, _interface(), [_case(2)], self.work, python_executable=sys.executable),
            "passed",
        )

    @staticmethod
    def _alive(pid):
        if os.name == "nt":
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel.WaitForSingleObject.restype = wintypes.DWORD
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.OpenProcess(0x00100000, False, pid)
            if not handle:
                return False
            try:
                return kernel.WaitForSingleObject(handle, 0) == 0x102
            finally:
                kernel.CloseHandle(handle)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        status = Path("/proc") / str(pid) / "stat"
        if status.is_file():
            return status.read_text().split(")", 1)[1].strip().split()[0] != "Z"
        return True

    def test_descendants_killed_after_normal_exit_and_timeout(self):
        for waits in (False, True):
            marker = self.root / "child.pid"
            marker.unlink(missing_ok=True)
            source = (
                "import subprocess, sys, time\nfrom pathlib import Path\n"
                "class Solution:\n def run(self):\n"
                "  child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                "  (Path(__file__).parent / 'child.pid').write_text(str(child.pid))\n"
                + ("  time.sleep(60)\n" if waits else "  return 1\n")
            )
            with self.subTest(timeout=waits):
                start = time.monotonic()
                result = self.run_python(source, timeout=0.8)
                self.assert_status(result, "timeout" if waits else "passed")
                self.assertLess(time.monotonic() - start, 5)
                self.assertTrue(marker.exists(), result)
                pid = int(marker.read_text())
                for _ in range(100):
                    if not self._alive(pid):
                        break
                    time.sleep(0.01)
                self.assertFalse(self._alive(pid), f"descendant {pid} survived")


class PythonProbeTests(unittest.TestCase):
    def assert_unavailable(self, result):
        self.assertEqual(set(result), {"available", "version", "error"})
        self.assertIs(result["available"], False)
        self.assertEqual(result["version"], [])
        self.assertIs(type(result["error"]), str)
        self.assertTrue(result["error"])

    def test_current_interpreter(self):
        result = execution.probe_python(sys.executable)
        self.assertEqual(result, {
            "available": True, "version": list(sys.version_info[:3]), "error": "",
        })

    def test_missing_and_invalid_interpreters(self):
        for executable in ("missing-interview-probe-python", "", "  ", None, 7, "invalid\0python"):
            with self.subTest(executable=executable):
                self.assert_unavailable(execution.probe_python(executable))

    def test_argv_paths_bounds_and_version_policy_separation(self):
        executable = str(Path("folder with spaces") / "python.exe")
        for version in ([3, 10, 15], [3, 11, 0], [3, 12, 10], [3, 13, 1], [3, 14, 0]):
            process = execution._ProcessResult(0, json.dumps(version) + "\n", "")
            with self.subTest(version=version):
                with mock.patch.object(execution, "_run_process", return_value=process) as run:
                    result = execution.probe_python(executable)
                self.assertEqual(result, {"available": True, "version": version, "error": ""})
                run.assert_called_once_with(
                    [executable, "-I", "-B", "-c", execution._PROBE_SCRIPT],
                    Path.cwd(), timeout=3.0, output_limit=4096,
                )

    def test_malformed_or_nonzero_version_responses(self):
        for output in (
            "", "Python 3.12.10", "[3, 12]", "[3, 12, 0, 1]", "[true, 12, 0]",
            '["3", 12, 0]', "[3, 12.0, 0]", "[3, -1, 0]", "[0, 12, 0]",
            '{"version":[3,12,0]}', "[3, 12, NaN]", "[3, 12, 0]\nextra",
        ):
            with self.subTest(output=output):
                process = execution._ProcessResult(0, output, "")
                with mock.patch.object(execution, "_run_process", return_value=process):
                    result = execution.probe_python("python")
                self.assert_unavailable(result)
                self.assertIn("malformed version", result["error"])
        with mock.patch.object(execution, "_run_process", return_value=execution._ProcessResult(4, "", "bad launcher")):
            result = execution.probe_python("python")
        self.assert_unavailable(result)
        self.assertIn("code 4", result["error"])
        self.assertIn("bad launcher", result["error"])

    def test_probe_timeout_uses_contained_runner(self):
        start = time.monotonic()
        with mock.patch.object(execution, "_PROBE_SCRIPT", "import time; time.sleep(60)"):
            with mock.patch.object(execution, "_PROBE_TIMEOUT", 0.2):
                result = execution.probe_python(sys.executable)
        self.assert_unavailable(result)
        self.assertIn("wall-clock", result["error"])
        self.assertLess(time.monotonic() - start, 5)

    def test_probe_output_limit_uses_contained_runner(self):
        with mock.patch.object(execution, "_PROBE_SCRIPT", "import os; os.write(1, b'x' * 65536)"):
            with mock.patch.object(execution, "_PROBE_OUTPUT_LIMIT", 128):
                result = execution.probe_python(sys.executable)
        self.assert_unavailable(result)
        self.assertIn("128 bytes", result["error"])
        self.assertLess(len(result["error"]), 512)

    def test_containment_failure_is_reported(self):
        with mock.patch.object(execution, "_run_process", side_effect=execution._InfrastructureError("job failure")):
            result = execution.probe_python("python")
        self.assert_unavailable(result)
        self.assertIn("job failure", result["error"])


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.root = Path.cwd() / (".protocol-tests-" + uuid.uuid4().hex)
        self.root.mkdir()
        self.path = self.root / "result.jsonl"
        self.record = {
            "version": 1, "id": "one", "constructor": {"kind": "ok"},
            "commands": [{"method": "run", "result": {"kind": "value", "value": 1}, "after": {}}],
        }

    def tearDown(self):
        shutil.rmtree(self.root)

    def parse(self, records):
        self.path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
        return execution._read_protocol(self.path, _interface(), [_case()], 65536)

    def test_valid_protocol(self):
        records, fatal = self.parse([self.record, {"version": 1, "done": 1}])
        self.assertEqual(records, [self.record])
        self.assertIsNone(fatal)

    def test_duplicate_missing_extra_reordered_cases(self):
        for records in (
            [self.record], [self.record, self.record, {"version": 1, "done": 1}],
            [{**self.record, "id": "other"}, {"version": 1, "done": 1}],
            [self.record, {"version": 1, "done": True}],
            [self.record, {"version": 1, "done": 2}],
            [{**self.record, "commands": []}, {"version": 1, "done": 1}],
            [{**self.record, "version": True}, {"version": 1, "done": 1}],
        ):
            with self.subTest(records=records), self.assertRaises(execution._ProtocolError):
                self.parse(records)

    def test_bad_json_duplicate_keys_nonfinite_and_surrogates(self):
        for text in (
            '{"version":1,"version":1}\n',
            '{"version":1,"value":NaN}\n',
            '{"version":1,"value":Infinity}\n',
            '{"version":1,"value":1e9999}\n',
            '{}',
            '\n',
        ):
            self.path.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaises(execution._ProtocolError):
                execution._read_protocol(self.path, _interface(), [_case()], 65536)
        self.record["commands"][0]["result"]["value"] = "\ud800"
        with self.assertRaises(execution._ProtocolError):
            self.parse([self.record, {"version": 1, "done": 1}])

    def test_unknown_record_and_command_keys(self):
        for patch in ({"untrusted": 1}, {"commands": [{"method": "bad", "result": {}, "after": {}}]}):
            with self.subTest(patch=patch), self.assertRaises(execution._ProtocolError):
                self.parse([{**self.record, **patch}, {"version": 1, "done": 1}])

    def test_protocol_cannot_bypass_exact_types(self):
        self.record["commands"][0]["result"]["value"] = True
        records, _ = self.parse([self.record, {"version": 1, "done": 1}])
        graded = execution._grade(records, _interface(), [_case()])
        self.assertEqual(graded[0]["status"], "wrong_answer")

    def test_unasserted_mutation_is_still_typed(self):
        interface = _interface("int", [{"name": "values", "type": {"list": "int"}, "mode": "inout"}])
        case = _case(1, [[]])
        self.record["commands"][0]["after"] = {"values": {"kind": "value", "value": [True]}}
        self.path.write_text(
            json.dumps(self.record) + "\n" + json.dumps({"version": 1, "done": 1}) + "\n", encoding="utf-8",
        )
        records, _ = execution._read_protocol(self.path, interface, [case], 65536)
        self.assertEqual(execution._grade(records, interface, [case])[0]["status"], "wrong_answer")


class CppGenerationTests(unittest.TestCase):
    def test_public_harness_excludes_hidden_cases_and_future_interface(self):
        public_value = "PUBLIC_CURRENT_PAYLOAD"
        hidden_value = "HIDDEN_PRIVATE_PAYLOAD"
        future_value = "FUTURE_PRIVATE_PAYLOAD"
        current = _interface("int", [{"name": "value", "type": "str"}])
        current["methods"].append({
            "name": "futureOnly", "params": [{"name": "value", "type": "str"}],
            "returns": "int", "since": 2,
        })
        future_public = _case(1, [future_value], "future-public")
        future_public["commands"][0]["method"] = "futureOnly"
        future_hidden = copy.deepcopy(future_public)
        future_hidden["id"] = "future-hidden"
        common = {
            "title": "Part", "prompt": "Implement this interface.",
            "invariants": ["State is local."], "hints": ["One", "Two", "Three"],
            "failure_question": "What failed?",
        }
        pack = {
            "schema": 1, "id": "isolation-check", "title": "Isolation", "family": "simulation",
            "origin": {"kind": "demo", "seed": "isolation"}, "interface": current,
            "references": {"python": "reference.py", "cpp": "reference.cpp"},
            "parts": [
                {
                    **common, "public": [_case(1, [public_value], "current-public")],
                    "hidden": [_case(1, [hidden_value], "current-hidden")],
                },
                {**common, "public": [future_public], "hidden": [future_hidden]},
            ],
        }
        generated = execution.generate_cpp_harness(
            "class Solution {};",
            schema.interface_for(pack, 1),
            pack["parts"][0]["public"],
        )
        self.assertIn(execution._cpp_string(public_value), generated)
        self.assertNotIn(execution._cpp_string(hidden_value), generated)
        self.assertNotIn(execution._cpp_string(future_value), generated)
        self.assertNotIn("futureOnly", generated)
        self.assertIn("std::declval<Solution&>().run", generated)

    def test_typed_fixture_literals_and_static_assertions(self):
        descriptor = {"map": {"list": {"optional": "str"}}}
        value = {'nul\0 "\\ 🧪': [None, "中文", ""]}
        generated = execution.generate_cpp_harness(
            "class Solution {};", _interface(descriptor, [{"name": "value", "type": descriptor}]),
            [_case(value, [value])],
        )
        self.assertIn("static_assert(std::is_same_v<decltype", generated)
        self.assertIn("std::map<std::string, std::vector<std::optional<std::string>>>", generated)
        self.assertIn("std::in_place", generated)
        self.assertIn("std::nullopt", generated)
        self.assertIn("\\x00", generated)
        self.assertIn("\\xf0\\x9f\\xa7\\xaa", generated)
        self.assertIn("std::string(\"\", 0)", generated)
        self.assertIn("protocol_writer", generated)
        self.assertNotIn("nlohmann", generated)

    def test_minimum_int_and_void_mutation_generation(self):
        self.assertEqual(execution._cpp_literal(-(1 << 63), "int"), "std::int64_t{(-9223372036854775807LL - 1)}")
        interface = _interface("void", [{"name": "values", "type": {"list": "int"}, "mode": "inout"}])
        case = _case(None, [[1]])
        generated = execution.generate_cpp_harness("class Solution {};", interface, [case])
        self.assertIn("value_outcome(il_arg_0)", generated)
        self.assertIn("void>,", generated)

    def test_compiler_argv_preserves_spaces_and_standards(self):
        root = Path("folder with spaces")
        for compiler in ("g++", "clang++", "cl.exe", str(root / "g++.exe"), str(root / "cl.exe")):
            args = execution._compiler_command(compiler, root / "harness.cpp", root / "output.exe", root / "answer.cpp", "c++20")
            self.assertIn(str(root / "harness.cpp"), args)
            self.assertTrue(any("c++20" in arg for arg in args))
            self.assertEqual(args[0], compiler)
            self.assertFalse(any(arg.startswith('"') for arg in args))

    def test_cpp_generation_handles_all_exception_categories(self):
        generated = execution.generate_cpp_harness("class Solution {};", _interface(), [_case()])
        for name in schema.EXCEPTIONS:
            self.assertIn(f"std::{name}", generated)
        self.assertIn("std::exception", generated)
        self.assertIn("catch (...)", generated)

    def test_missing_compiler_does_not_install_anything(self):
        with mock.patch.object(execution.shutil, "which", return_value=None):
            self.assertIsNone(execution.find_compiler())
            self.assertIsNone(execution.find_compiler("not-a-compiler"))

    def test_generation_rejects_invalid_fixtures(self):
        with self.assertRaises(schema.SchemaError):
            execution.generate_cpp_harness("", _interface(), [_case(True)])


_COMPILER = execution.find_compiler()


@unittest.skipUnless(_COMPILER, "no g++, clang++, or cl on PATH; no compiler is installed or downloaded by tests")
class CppExecutionTests(unittest.TestCase):
    setUp = ExecutionTests.setUp
    tearDown = ExecutionTests.tearDown
    assert_status = ExecutionTests.assert_status

    def run_cpp(self, source, interface=None, cases=None, **options):
        self.source = self.root / "candidate with spaces.cpp"
        self.source.write_text(source, encoding="utf-8")
        return execution.run_suite(
            "cpp", self.source, interface or _interface(), cases or [_case()], self.work,
            compiler=_COMPILER, timeout=20, **options,
        )

    def test_cpp_int_and_debug_output(self):
        self.assert_status(self.run_cpp(
            '#include <iostream>\nclass Solution { public: std::int64_t run() { std::cout << "debug"; std::cerr << "err"; return 1; } };'
        ), "passed")

    def test_cpp_rejects_bool_to_int_conversion_at_compile_time(self):
        self.assert_status(self.run_cpp("class Solution { public: bool run() { return true; } };"), "compile_error")

    def test_cpp_nested_unicode(self):
        descriptor = {"map": {"list": {"optional": "str"}}}
        value = {'nul\0 "\\ 🧪': [None, "中文", ""]}
        type_name = schema.cpp_type(descriptor)
        self.assert_status(self.run_cpp(
            f"class Solution {{ public: {type_name} run(const {type_name}& value) {{ return value; }} }};",
            _interface(descriptor, [{"name": "value", "type": descriptor}]), [_case(value, [value])],
        ), "passed")

    def test_cpp_mutation_on_exception(self):
        descriptor = {"list": "int"}
        case = _case(None, [[1]])
        case["commands"] = [{"method": "run", "args": [[1]], "raises": "invalid_argument", "after": {"values": [1, 7]}}]
        self.assert_status(self.run_cpp(
            'class Solution { public: void run(std::vector<std::int64_t>& values) { values.push_back(7); throw std::invalid_argument("expected"); } };',
            _interface("void", [{"name": "values", "type": descriptor, "mode": "inout"}]), [case],
        ), "passed")

    def test_cpp_stateful_constructor(self):
        case = _case(6, constructor=[5])
        case["commands"].append({"method": "run", "args": [], "expect": 7})
        self.assert_status(self.run_cpp(
            "class Solution { std::int64_t value; public: Solution(std::int64_t start): value(start) {} std::int64_t run() { return ++value; } };",
            _interface(constructor=[{"name": "start", "type": "int"}]), [case],
        ), "passed")

    def test_cpp_crash(self):
        self.assert_status(self.run_cpp(
            "class Solution { public: std::int64_t run() { std::_Exit(23); } };",
        ), "crash")

    def test_cpp_syntax_failure(self):
        self.assert_status(self.run_cpp("not valid C++"), "compile_error")


if __name__ == "__main__":
    unittest.main()
