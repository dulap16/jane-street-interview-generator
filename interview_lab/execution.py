"""Bounded local execution. Process containment is not a security sandbox."""

from __future__ import annotations

import copy
import ctypes
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import threading
import time
from typing import Any
import uuid

from .schema import (
    EXCEPTIONS, MAX_SOURCE_BYTES, SchemaError, cpp_type, validate_cases,
    validate_interface, validate_value,
)


class _InfrastructureError(Exception):
    pass


class _ProtocolError(Exception):
    pass


@dataclass
class _ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    timeout: bool = False
    output_limit: bool = False


_PROBE_TIMEOUT = 3.0
_PROBE_OUTPUT_LIMIT = 4096
_PROBE_SCRIPT = "import json, sys; print(json.dumps(list(sys.version_info[:3])))"


class _WindowsJob:
    """Create suspended, assign to a kill-on-close job, then resume atomically."""

    def __init__(self) -> None:
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IOCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
            )]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimits),
                ("IoInfo", IOCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.kernel.SetInformationJobObject.restype = wintypes.BOOL
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.resume = ctypes.WinDLL("ntdll").NtResumeProcess
        self.resume.argtypes = [wintypes.HANDLE]
        self.resume.restype = ctypes.c_long
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise _InfrastructureError(f"CreateJobObjectW failed: {ctypes.get_last_error()}")
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.get_last_error()
            self.close()
            raise _InfrastructureError(f"SetInformationJobObject failed: {error}")

    def attach_and_resume(self, process: subprocess.Popen) -> None:
        if not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise _InfrastructureError(f"AssignProcessToJobObject failed: {ctypes.get_last_error()}")
        if self.resume(int(process._handle)) < 0:
            raise _InfrastructureError("NtResumeProcess failed")

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def _run_process(
    argv: list[str], cwd: Path, timeout: float, output_limit: int, protocol: Path | None = None,
) -> _ProcessResult:
    job = _WindowsJob() if os.name == "nt" else None
    process = None
    threads: list[threading.Thread] = []
    captured = {"stdout": bytearray(), "stderr": bytearray()}
    lock = threading.Lock()
    exceeded = threading.Event()
    total = 0
    timed_out = False
    started = time.monotonic()

    def drain(pipe: Any, name: str) -> None:
        nonlocal total
        try:
            while True:
                chunk = os.read(pipe.fileno(), 8192)
                if not chunk:
                    return
                with lock:
                    keep = max(0, output_limit - total)
                    captured[name].extend(chunk[:keep])
                    total += len(chunk)
                    if total > output_limit:
                        exceeded.set()
        except (OSError, ValueError):
            return
        finally:
            pipe.close()

    def limit_file() -> bool:
        try:
            return protocol is not None and protocol.stat().st_size > output_limit
        except FileNotFoundError:
            return False

    try:
        options: dict[str, Any] = {"creationflags": 0x00000004 | 0x08000000} if job else {"start_new_session": True}
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        process = subprocess.Popen(
            argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            shell=False, env=environment, **options,
        )
        if job:
            job.attach_and_resume(process)
        for name in ("stdout", "stderr"):
            thread = threading.Thread(target=drain, args=(getattr(process, name), name), daemon=True)
            threads.append(thread)
            thread.start()
        while True:
            if limit_file():
                exceeded.set()
            if exceeded.is_set():
                break
            if process.poll() is not None:
                break
            if time.monotonic() - started >= timeout:
                timed_out = True
                break
            time.sleep(0.01)
    except (OSError, ValueError) as exc:
        raise _InfrastructureError(f"could not launch or supervise {argv[0]!r}: {exc}") from exc
    finally:
        # Closing the job / killing the group also handles children that retained
        # stdout after their parent exited normally. Never wait on pipes first.
        if job:
            job.close()
        elif process:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process:
            if process.poll() is None:
                process.kill()
            process.wait()
            for thread in threads:
                thread.join(timeout=2)
            for name in ("stdout", "stderr"):
                pipe = getattr(process, name)
                if pipe is not None and not threads and not pipe.closed:
                    pipe.close()
    if any(thread.is_alive() for thread in threads):
        raise _InfrastructureError("a descendant escaped process containment and retained an output pipe")
    if limit_file():
        exceeded.set()
    return _ProcessResult(
        process.returncode,
        captured["stdout"].decode("utf-8", "replace"),
        captured["stderr"].decode("utf-8", "replace"),
        timed_out,
        exceeded.is_set(),
    )


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def probe_python(executable: str) -> dict:
    """Report the configured interpreter's version without loading candidate code.

    Availability describes a successful probe, not compatibility with the core's
    configured version policy. Failure always returns an empty version list.
    """
    unavailable = {"available": False, "version": [], "error": ""}
    if type(executable) is not str or not executable.strip():
        unavailable["error"] = "python executable must be a nonempty executable name or path"
        return unavailable
    try:
        result = _run_process(
            [executable, "-I", "-B", "-c", _PROBE_SCRIPT],
            Path.cwd(), timeout=_PROBE_TIMEOUT, output_limit=_PROBE_OUTPUT_LIMIT,
        )
        if result.output_limit:
            error = f"Python version probe exceeded {_PROBE_OUTPUT_LIMIT} bytes of output"
        elif result.timeout:
            error = f"Python version probe exceeded {_PROBE_TIMEOUT:g}s wall-clock limit"
        elif result.returncode:
            error = f"Python version probe exited with code {result.returncode}"
        else:
            try:
                version = json.loads(result.stdout)
            except (ValueError, RecursionError):
                version = None
            if (
                type(version) is list
                and len(version) == 3
                and all(type(item) is int and item >= 0 for item in version)
                and version[0] > 0
            ):
                return {"available": True, "version": version, "error": ""}
            error = "Python version probe returned a malformed version; expected three nonnegative integers"
        if result.stdout:
            error += "\n[stdout]\n" + result.stdout
        if result.stderr:
            error += "\n[stderr]\n" + result.stderr
        unavailable["error"] = error
    except (_InfrastructureError, OSError, TypeError, ValueError) as exc:
        unavailable["error"] = f"Python version probe failed: {exc}"
    return unavailable


def _cpp_string(value: str) -> str:
    encoded = value.encode("utf-8")
    literal = "".join(f"\\x{byte:02x}" for byte in encoded)
    return f'std::string("{literal}", {len(encoded)})'


def _cpp_literal(value: Any, descriptor: Any) -> str:
    if descriptor == "int":
        number = "(-9223372036854775807LL - 1)" if value == -(1 << 63) else f"{value}LL"
        return f"std::int64_t{{{number}}}"
    if descriptor == "bool":
        return "true" if value else "false"
    if descriptor == "str":
        return _cpp_string(value)
    kind, nested = next(iter(descriptor.items()))
    type_name = cpp_type(descriptor)
    if kind == "optional":
        return f"{type_name}{{std::nullopt}}" if value is None else f"{type_name}{{std::in_place, {_cpp_literal(value, nested)}}}"
    if kind == "list":
        return type_name + "{" + ",".join(_cpp_literal(item, nested) for item in value) + "}"
    return type_name + "{" + ",".join(
        "{" + _cpp_string(key) + "," + _cpp_literal(item, nested) + "}" for key, item in value.items()
    ) + "}"


def generate_cpp_harness(source_text: str, interface: dict, cases: list, output_limit: int = 65536) -> str:
    """Generate a standalone C++17/20 harness; does not require a compiler."""
    validate_cases(interface, cases)
    if type(source_text) is not str or len(source_text.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise SchemaError("source: expected bounded UTF-8 source text")
    if type(output_limit) is not int or not 1 <= output_limit <= 16 * 1024 * 1024:
        raise SchemaError("output_limit: expected an integer in 1..16777216")
    runtime = Path(__file__).with_name("cpp_runtime.hpp").read_text(encoding="utf-8")
    lines = [runtime, '#line 1 "candidate.cpp"', source_text, '\n#line 1 "interview_harness.cpp"']
    methods = {method["name"]: method for method in interface["methods"]}
    for method in interface["methods"]:
        arguments = ", ".join(f"std::declval<{cpp_type(param['type'])}&>()" for param in method["params"])
        lines.append(
            f"static_assert(std::is_same_v<decltype(std::declval<Solution&>().{method['name']}({arguments})), "
            f"{cpp_type(method['returns'])}>, \"{method['name']}: return type must match exactly\");"
        )
    lines.extend([
        "int main(int il_argc, char** il_argv) {",
        "  if (il_argc != 2) return 87;",
        f"  interview_lab_detail::protocol_writer il_output(il_argv[1], {output_limit});",
    ])

    def write(text: str) -> None:
        lines.append(f"  il_output.write({_cpp_string(text)});")

    for case in cases:
        lines.append("  {")
        for index, (value, param) in enumerate(zip(case["constructor"], interface["constructor"])):
            lines.append(f"  auto il_ctor_{index} = {_cpp_literal(value, param['type'])};")
        args = ", ".join(f"il_ctor_{index}" for index in range(len(case["constructor"])))
        lines.extend([
            "  std::optional<Solution> il_instance;",
            f"  auto il_construct = interview_lab_detail::invoke([&]() {{ il_instance.emplace({args}); }});",
        ])
        write('{"version":1,"id":' + _json(case["id"]) + ',"constructor":')
        lines.append('  if (il_instance) il_output.write("{\\"kind\\":\\"ok\\"}");')
        lines.append("  else il_output.write(il_construct);")
        write(',"commands":[')
        lines.append("  if (il_instance) {")
        for command_index, command in enumerate(case["commands"]):
            method = methods[command["method"]]
            if command_index:
                write(",")
            lines.append("  {")
            for index, (value, param) in enumerate(zip(command["args"], method["params"])):
                lines.append(f"  auto il_arg_{index} = {_cpp_literal(value, param['type'])};")
            args = ", ".join(f"il_arg_{index}" for index in range(len(command["args"])))
            lines.append(
                "  auto il_result = interview_lab_detail::invoke([&]() -> decltype(auto) "
                f"{{ return il_instance->{method['name']}({args}); }});"
            )
            write('{"method":' + _json(method["name"]) + ',"result":')
            lines.append("  il_output.write(il_result);")
            write(',"after":{')
            first = True
            for index, param in enumerate(method["params"]):
                if param.get("mode", "in") == "inout":
                    write(("" if first else ",") + _json(param["name"]) + ":")
                    lines.append(f"  il_output.write(interview_lab_detail::value_outcome(il_arg_{index}));")
                    first = False
            write("}}")
            lines.append("  }")
        lines.append("  }")
        write("]}\n")
        lines.append("  }")
    write(_json({"version": 1, "done": len(cases)}) + "\n")
    lines.extend(["  return 0;", "}"])
    harness = "\n".join(lines)
    if len(harness.encode("utf-8")) > 32 * 1024 * 1024:
        raise SchemaError("generated harness exceeds 32 MiB")
    return harness


def find_compiler(compiler: str | None = None) -> str | None:
    """Resolve g++, clang++, or cl without downloading or installing anything."""
    names = [compiler] if compiler is not None else ["g++", "clang++", "cl"]
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return str(Path(resolved).resolve())
    return None


def _compiler_command(compiler: str, harness: Path, executable: Path, source: Path, standard: str) -> list[str]:
    name = Path(compiler).name.lower()
    if name in {"cl", "cl.exe"}:
        return [
            compiler, "/nologo", "/EHsc", "/utf-8", f"/std:{standard}", "/Od",
            "/I" + str(source.parent), str(harness), "/Fe:" + str(executable),
        ]
    return [
        compiler, f"-std={standard}", "-O0", "-I", str(source.parent),
        str(harness), "-o", str(executable),
    ]


def _keys(value: Any, expected: set[str], at: str) -> None:
    if type(value) is not dict or set(value) != expected:
        raise _ProtocolError(f"{at}: malformed record keys")


def _exception_shape(value: Any, at: str) -> None:
    _keys(value, {"kind", "category", "type", "message"}, at)
    if value["kind"] != "exception" or type(value["category"]) is not str or value["category"] not in EXCEPTIONS | {"other"}:
        raise _ProtocolError(f"{at}: invalid exception category")
    for key in ("type", "message"):
        try:
            validate_value(value[key], "str", f"{at}.{key}")
        except SchemaError as exc:
            raise _ProtocolError(str(exc)) from exc


def _outcome_shape(value: Any, descriptor: Any, at: str, *, exception: bool) -> None:
    if type(value) is not dict:
        raise _ProtocolError(f"{at}: expected an outcome")
    kind = value.get("kind")
    if kind == "exception" and exception:
        _exception_shape(value, at)
    elif kind == "invalid":
        _keys(value, {"kind", "message"}, at)
        if type(value["message"]) is not str:
            raise _ProtocolError(f"{at}: invalid error message")
        try:
            validate_value(value["message"], "str")
        except SchemaError as exc:
            raise _ProtocolError(str(exc)) from exc
    elif kind == "value":
        _keys(value, {"kind", "value"}, at)
        # Incorrect typed values remain wrong answers, not protocol failures.
        _json_scalar_strings(value["value"], at)
    else:
        raise _ProtocolError(f"{at}: invalid outcome kind")


def _json_scalar_strings(value: Any, at: str, depth: int = 0) -> None:
    if depth > 32:
        raise _ProtocolError(f"{at}: protocol value nesting exceeds 32")
    if type(value) is str:
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise _ProtocolError(f"{at}: invalid Unicode scalar string") from exc
    elif type(value) is list:
        for item in value:
            _json_scalar_strings(item, at, depth + 1)
    elif type(value) is dict:
        for key, item in value.items():
            _json_scalar_strings(key, at, depth + 1)
            _json_scalar_strings(item, at, depth + 1)


def _read_protocol(path: Path, interface: dict, cases: list, limit: int) -> tuple[list, dict | None]:
    def pairs(entries: list) -> dict:
        result = {}
        for key, value in entries:
            if key in result:
                raise _ProtocolError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    def bad_constant(value: str) -> None:
        raise _ProtocolError(f"invalid JSON constant {value}")

    def finite_float(value: str) -> float:
        number = float(value)
        if not math.isfinite(number):
            raise _ProtocolError("non-finite JSON number")
        return number

    try:
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise _ProtocolError("oversized protocol")
        text = data.decode("utf-8")
        if not text.endswith("\n"):
            raise _ProtocolError("protocol is missing its terminal newline")
        lines = text[:-1].split("\n")
        if len(lines) > len(cases) + 2:
            raise _ProtocolError("protocol contains too many records")
        records = [json.loads(line, object_pairs_hook=pairs, parse_constant=bad_constant, parse_float=finite_float) for line in lines]
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise _ProtocolError(f"missing or malformed result protocol: {exc}") from exc
    for record in records:
        if type(record) is not dict or type(record.get("version")) is not int or record["version"] != 1:
            raise _ProtocolError("invalid protocol version or record")
    if len(records) == 2 and "fatal" in records[0]:
        _keys(records[0], {"version", "fatal"}, "fatal record")
        fatal = records[0]["fatal"]
        _keys(fatal, {"stage", "error"}, "fatal")
        if fatal["stage"] != "import":
            raise _ProtocolError("invalid fatal stage")
        _exception_shape(fatal["error"], "fatal.error")
        _keys(records[1], {"version", "done"}, "terminal")
        if type(records[1]["done"]) is not int or records[1]["done"] != 0:
            raise _ProtocolError("invalid fatal terminal record")
        return [], fatal
    if len(records) != len(cases) + 1:
        raise _ProtocolError(f"expected {len(cases)} case records and a terminal record")
    _keys(records[-1], {"version", "done"}, "terminal")
    if type(records[-1]["done"]) is not int or records[-1]["done"] != len(cases):
        raise _ProtocolError("terminal case count mismatch")
    methods = {method["name"]: method for method in interface["methods"]}
    for record, case in zip(records[:-1], cases):
        at = f"case {case['id']}"
        _keys(record, {"version", "id", "constructor", "commands"}, at)
        if record["id"] != case["id"]:
            raise _ProtocolError(f"{at}: duplicate, reordered, or unknown case id")
        constructor = record["constructor"]
        if constructor != {"kind": "ok"}:
            _exception_shape(constructor, f"{at}.constructor")
        expected_count = len(case["commands"]) if constructor == {"kind": "ok"} else 0
        if type(record["commands"]) is not list or len(record["commands"]) != expected_count:
            raise _ProtocolError(f"{at}: missing or extra command records")
        for index, (actual, command) in enumerate(zip(record["commands"], case["commands"])):
            method = methods[command["method"]]
            cmd_at = f"{at}.commands[{index}]"
            _keys(actual, {"method", "result", "after"}, cmd_at)
            if actual["method"] != command["method"]:
                raise _ProtocolError(f"{cmd_at}: method mismatch")
            _outcome_shape(actual["result"], method["returns"], f"{cmd_at}.result", exception=True)
            mutable = {p["name"]: p for p in method["params"] if p.get("mode", "in") == "inout"}
            _keys(actual["after"], set(mutable), f"{cmd_at}.after")
            for name, param in mutable.items():
                _outcome_shape(actual["after"][name], param["type"], f"{cmd_at}.after.{name}", exception=False)
    return records[:-1], None


def _compare_value(outcome: dict, expected: Any, descriptor: Any) -> str | None:
    if outcome["kind"] == "invalid":
        return outcome["message"]
    try:
        validate_value(outcome["value"], descriptor)
    except SchemaError as exc:
        return str(exc)
    if outcome["value"] != expected:
        return f"expected {_json(expected)[:1000]}, got {_json(outcome['value'])[:1000]}"
    return None


def _grade(records: list, interface: dict, cases: list) -> list[dict]:
    methods = {method["name"]: method for method in interface["methods"]}
    graded = []
    for record, case in zip(records, cases):
        result = {"id": case["id"], "status": "passed", "commands": []}
        if record["constructor"] != {"kind": "ok"}:
            result.update(status="runtime_error", diagnostics=f"constructor: {_json(record['constructor'])}")
            graded.append(result)
            continue
        for index, (actual, expected) in enumerate(zip(record["commands"], case["commands"])):
            method = methods[expected["method"]]
            outcome = actual["result"]
            status = "passed"
            issues = []
            if "raises" in expected:
                if outcome["kind"] != "exception" or outcome["category"] != expected["raises"]:
                    status = "wrong_answer"
                    issues.append(f"expected {expected['raises']}; got {_json(outcome)[:2000]}")
            elif outcome["kind"] == "exception":
                status = "runtime_error"
                issues.append(f"unexpected exception: {_json(outcome)}")
            else:
                issue = _compare_value(outcome, expected["expect"], method["returns"])
                if issue:
                    status = "wrong_answer"
                    issues.append(issue)
            for param in method["params"]:
                name = param["name"]
                if name in expected.get("after", {}):
                    issue = _compare_value(actual["after"][name], expected["after"][name], param["type"])
                    if issue:
                        if status != "runtime_error":
                            status = "wrong_answer"
                        issues.append(f"after.{name}: {issue}")
                elif name in actual["after"] and actual["after"][name]["kind"] == "invalid":
                    if status != "runtime_error":
                        status = "wrong_answer"
                    issues.append(f"after.{name}: {actual['after'][name]['message']}")
                elif name in actual["after"]:
                    try:
                        validate_value(actual["after"][name]["value"], param["type"])
                    except SchemaError as exc:
                        if status != "runtime_error":
                            status = "wrong_answer"
                        issues.append(f"after.{name}: {exc}")
            result["commands"].append({
                "index": index, "method": method["name"], "status": status,
                "diagnostics": "; ".join(issues), "actual": actual,
            })
            if status == "runtime_error" or (status == "wrong_answer" and result["status"] == "passed"):
                result["status"] = status
        result["diagnostics"] = "\n".join(
            f"command {item['index']} ({item['method']}): {item['diagnostics']}"
            for item in result["commands"] if item["status"] != "passed"
        )
        graded.append(result)
    return graded


def _cleanup_run(path: Path) -> None:
    def writable(function: Any, target: str, error: Any) -> None:
        os.chmod(target, stat.S_IRWXU if Path(target).is_dir() else stat.S_IWRITE | stat.S_IREAD)
        function(target)

    for attempt in range(20):
        try:
            shutil.rmtree(path, onerror=writable)
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt == 19:
                raise
            time.sleep(0.05)


def run_suite(
    language: str,
    source: Path,
    interface: dict,
    cases: list,
    work_dir: Path,
    *,
    python_executable: str = "python",
    compiler: str | None = None,
    cpp_standard: str = "c++17",
    timeout: float = 3.0,
    output_limit: int = 65536,
    total_timeout: float | None = None,
) -> dict:
    """Run one stateful Solution per case, returning structured private evidence.

    The timeout is a wall-clock budget per subprocess (compilation and execution).
    total_timeout optionally caps both phases together, including preparation.
    stdout+stderr share one byte cap; the private protocol has an independent cap.
    Infrastructure failures never execute candidate code in the host interpreter.
    """
    started = time.monotonic()
    total = len(cases) if type(cases) is list else 0
    run_dir: Path | None = None
    final_result: dict | None = None
    stdout, stderr = "", ""

    def failure(status: str, message: str) -> dict:
        nonlocal final_result
        diagnostics = message
        if stdout:
            diagnostics += "\n[stdout]\n" + stdout
        if stderr:
            diagnostics += "\n[stderr]\n" + stderr
        ids = [
            case["id"] if type(case) is dict and type(case.get("id")) is str and len(case["id"]) <= 64 else f"case-{index}"
            for index, case in enumerate(cases)
        ] if type(cases) is list else []
        final_result = {
            "status": status, "passed": 0, "total": total,
            "cases": [{"id": name, "status": status, "diagnostics": message} for name in ids],
            "diagnostics": diagnostics, "stdout": stdout, "stderr": stderr,
        }
        return final_result

    def phase_budget() -> float:
        if total_timeout is None:
            return timeout
        return min(timeout, total_timeout - (time.monotonic() - started))

    def overall_timeout() -> dict:
        return failure("timeout", f"overall {total_timeout:g}s wall-clock budget exhausted")

    def process_failure(
        result: _ProcessResult, phase_limit: float, *, compiling: bool = False,
    ) -> dict | None:
        if result.output_limit:
            return failure("output_limit", f"{'compiler' if compiling else 'candidate'} exceeded output limit")
        if result.timeout:
            return failure("timeout", f"{'compilation' if compiling else 'execution'} exceeded {phase_limit:g}s wall-clock limit")
        if total_timeout is not None and phase_budget() <= 0:
            return overall_timeout()
        if result.returncode:
            return failure(
                "compile_error" if compiling else "crash",
                f"{'compiler' if compiling else 'candidate process'} exited with code {result.returncode}",
            )
        return None

    try:
        if language not in ("python", "cpp"):
            raise SchemaError("language: expected python or cpp")
        if cpp_standard not in ("c++17", "c++20"):
            raise SchemaError("cpp_standard: only c++17 and c++20 are supported")
        if type(timeout) not in (float, int) or not 0 < timeout <= 600 or not math.isfinite(timeout):
            raise SchemaError("timeout: expected a finite number in (0, 600]")
        if total_timeout is not None:
            if type(total_timeout) not in (float, int):
                raise SchemaError("total_timeout: expected a finite positive number or None")
            try:
                total_timeout = float(total_timeout)
            except OverflowError as exc:
                raise SchemaError("total_timeout: expected a finite positive number or None") from exc
            if not math.isfinite(total_timeout) or total_timeout <= 0:
                raise SchemaError("total_timeout: expected a finite positive number or None")
        if type(output_limit) is not int or not 1 <= output_limit <= 16 * 1024 * 1024:
            raise SchemaError("output_limit: expected an integer in 1..16777216")
        if type(python_executable) is not str or not python_executable.strip():
            raise SchemaError("python_executable: expected an executable name or path")
        if compiler is not None and (type(compiler) is not str or not compiler.strip()):
            raise SchemaError("compiler: expected an executable name or path")
        validate_interface(interface)
        validate_cases(interface, cases)
        interface, cases = copy.deepcopy(interface), copy.deepcopy(cases)
        source, work_dir = Path(source).resolve(), Path(work_dir).resolve()
        with source.open("rb") as stream:
            source_bytes = stream.read(MAX_SOURCE_BYTES + 1)
        if len(source_bytes) > MAX_SOURCE_BYTES:
            raise SchemaError(f"source: exceeds {MAX_SOURCE_BYTES} bytes")
        try:
            source_text = source_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            return failure("compile_error", f"source must be UTF-8: {exc}")
        if language == "python":
            try:
                compile(source_text, str(source), "exec")
            except (SyntaxError, ValueError, OverflowError) as exc:
                return failure("compile_error", f"{type(exc).__name__}: {exc}")
        selected_compiler = find_compiler(compiler) if language == "cpp" else None
        if language == "cpp" and selected_compiler is None:
            raise _InfrastructureError("no supported C++ compiler found; configure g++, clang++, or cl in a Developer Prompt")
        work_dir.mkdir(parents=True, exist_ok=True)
        run_dir = work_dir / ("run-" + uuid.uuid4().hex)
        run_dir.mkdir(mode=0o700)
        protocol = run_dir / "outcomes.jsonl"
        if language == "python":
            fixture = run_dir / "fixture.json"
            fixture.write_text(_json({
                "interface": interface, "cases": cases, "output_limit": output_limit, "source_text": source_text,
            }), encoding="utf-8")
            worker = Path(__file__).with_name("python_worker.py").resolve()
            # -B also prevents bytecode writes outside this invocation's directory.
            argv = [python_executable, "-I", "-B", str(worker), str(fixture), str(protocol), str(source)]
        else:
            harness = run_dir / "harness.cpp"
            harness.write_text(generate_cpp_harness(source_text, interface, cases, output_limit), encoding="utf-8")
            executable = run_dir / ("candidate.exe" if os.name == "nt" else "candidate")
            compiler_argv = _compiler_command(selected_compiler, harness, executable, source, cpp_standard)
            compile_budget = phase_budget()
            if compile_budget <= 0:
                return overall_timeout()
            compiled = _run_process(
                compiler_argv, run_dir, compile_budget, output_limit,
            )
            stdout, stderr = compiled.stdout, compiled.stderr
            failed = process_failure(compiled, compile_budget, compiling=True)
            if failed:
                return failed
            if not executable.is_file():
                return failure("infrastructure_error", "compiler succeeded but did not create an executable")
            # A relative ASCII protocol filename also works with Windows' narrow
            # C++ main argv when the user's absolute workspace path is Unicode.
            argv = [str(executable), protocol.name]
        execute_budget = phase_budget()
        if execute_budget <= 0:
            return overall_timeout()
        executed = _run_process(argv, run_dir, execute_budget, output_limit, protocol)
        stdout, stderr = executed.stdout, executed.stderr
        failed = process_failure(executed, execute_budget)
        if failed:
            return failed
        records, fatal = _read_protocol(protocol, interface, cases, output_limit)
        if fatal:
            return failure("runtime_error", f"candidate import failed: {_json(fatal['error'])}")
        graded = _grade(records, interface, cases)
        passed = sum(case["status"] == "passed" for case in graded)
        status = "runtime_error" if any(case["status"] == "runtime_error" for case in graded) else (
            "passed" if passed == total else "wrong_answer"
        )
        final_result = {
            "status": status, "passed": passed, "total": total, "cases": graded,
            "diagnostics": "\n".join(f"{case['id']}: {case['diagnostics']}" for case in graded if case["diagnostics"]),
            "stdout": stdout, "stderr": stderr,
        }
        return final_result
    except (SchemaError, _InfrastructureError, OSError, TypeError, ValueError, RecursionError) as exc:
        return failure("infrastructure_error", str(exc))
    except _ProtocolError as exc:
        return failure("protocol_error", str(exc))
    finally:
        if run_dir is not None:
            # Only remove our own directory, never the caller's source or work root.
            try:
                _cleanup_run(run_dir)
            except OSError as exc:
                if final_result is not None:
                    returned = final_result
                    replacement = failure("infrastructure_error", f"could not clean owned run directory {run_dir.name}: {exc}")
                    returned.clear()
                    returned.update(replacement)
