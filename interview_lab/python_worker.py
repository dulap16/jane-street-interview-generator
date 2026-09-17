"""Private subprocess worker. Candidate output never carries the result protocol."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys
import types

# -I intentionally omits both the current directory and PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import SchemaError, validate_value  # noqa: E402


def _text(value: object) -> str:
    try:
        return str(value)[:2048].encode("utf-8", "backslashreplace").decode("utf-8")
    except Exception:
        return "<exception message unavailable>"


def _exception(exc: Exception) -> dict:
    if isinstance(exc, ValueError):
        category = "invalid_argument"
    elif isinstance(exc, (IndexError, KeyError)):
        category = "out_of_range"
    elif isinstance(exc, RuntimeError):
        category = "runtime_error"
    else:
        category = "other"
    return {"kind": "exception", "category": category, "type": type(exc).__name__, "message": _text(exc)}


def _value(value: object, descriptor: object) -> dict:
    try:
        validate_value(value, descriptor)
    except SchemaError as exc:
        return {"kind": "invalid", "message": _text(exc)}
    # Later calls must not mutate a previously recorded return or after-value.
    return {"kind": "value", "value": copy.deepcopy(value)}


class _Protocol:
    def __init__(self, path: Path, limit: int):
        self.file = path.open("wb", buffering=0)
        self.remaining = limit + 1

    def write(self, record: dict) -> None:
        encoder = json.JSONEncoder(ensure_ascii=True, allow_nan=False, separators=(",", ":"))
        for fragment in encoder.iterencode(record):
            self._bytes(fragment.encode("ascii"))
        self._bytes(b"\n")

    def _bytes(self, data: bytes) -> None:
        chunk = data[:self.remaining]
        self.file.write(chunk)
        self.remaining -= len(chunk)
        if not self.remaining:
            os._exit(86)


def main() -> None:
    fixture_path, protocol_path, source_path = map(Path, sys.argv[1:4])
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    protocol = _Protocol(protocol_path, fixture["output_limit"])
    interface, cases = fixture["interface"], fixture["cases"]
    methods = {method["name"]: method for method in interface["methods"]}
    try:
        sys.path.insert(0, str(source_path.resolve().parent))
        module = types.ModuleType("_interview_candidate")
        module.__file__ = str(source_path)
        module.__package__ = ""
        sys.modules[module.__name__] = module
        # Execute the exact preflighted snapshot, never an old cached .pyc.
        exec(compile(fixture["source_text"], str(source_path), "exec"), module.__dict__)
        solution = getattr(module, "Solution")
        if not isinstance(solution, type):
            raise TypeError("Solution must be a class")
    except Exception as exc:
        protocol.write({"version": 1, "fatal": {"stage": "import", "error": _exception(exc)}})
        protocol.write({"version": 1, "done": 0})
        return

    for case in cases:
        record = {"version": 1, "id": case["id"], "constructor": {"kind": "ok"}, "commands": []}
        try:
            instance = solution(*copy.deepcopy(case["constructor"]))
        except Exception as exc:
            record["constructor"] = _exception(exc)
            protocol.write(record)
            continue
        for command in case["commands"]:
            method = methods[command["method"]]
            args = copy.deepcopy(command["args"])
            try:
                result = _value(getattr(instance, method["name"])(*args), method["returns"])
            except Exception as exc:
                result = _exception(exc)
            after = {
                param["name"]: _value(args[index], param["type"])
                for index, param in enumerate(method["params"])
                if param.get("mode", "in") == "inout"
            }
            record["commands"].append({"method": method["name"], "result": result, "after": after})
        protocol.write(record)
    protocol.write({"version": 1, "done": len(cases)})


if __name__ == "__main__":
    main()
