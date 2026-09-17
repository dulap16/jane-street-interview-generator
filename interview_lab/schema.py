"""Strict, bounded validation for language-independent interview fixtures."""

from __future__ import annotations

import copy
import json
import keyword
import re
from typing import Any


class SchemaError(ValueError):
    """An invalid pack, interface, or fixture, with a location in the message."""


MAX_PARTS = 16
MAX_METHODS = 128
MAX_PARAMS = 32
MAX_CASES = 1024
MAX_COMMANDS = 256
MAX_TOTAL_COMMANDS = 4096
MAX_TYPE_DEPTH = 12
MAX_COLLECTION = 10000
MAX_VALUE_NODES = 100000
MAX_STRING_BYTES = 1048576
MAX_SOURCE_BYTES = 2097152
MAX_PACK_BYTES = 8388608

FAMILIES = frozenset(
    "cache simulation parser graph stream scheduling orderbook spatial filesystem workflow".split()
)
EXCEPTIONS = frozenset(("invalid_argument", "out_of_range", "runtime_error"))
_CPP_KEYWORDS = frozenset(
    """alignas alignof and and_eq asm atomic_cancel atomic_commit atomic_noexcept
    auto bitand bitor bool break case catch char char8_t char16_t char32_t class
    compl concept const consteval constexpr constinit const_cast continue co_await
    co_return co_yield decltype default delete do double dynamic_cast else enum
    explicit export extern false float for friend goto if inline int long mutable
    namespace new noexcept not not_eq nullptr operator or or_eq private protected
    public reflexpr register reinterpret_cast requires return short signed sizeof
    static static_assert static_cast struct switch synchronized template this
    thread_local throw true try typedef typeid typename union unsigned using
    virtual void volatile wchar_t while xor xor_eq final override import module""".split()
)
_RESERVED = _CPP_KEYWORDS | frozenset(keyword.kwlist) | {
    "Solution", "self", "cls", "match", "type", "None", "True", "False"
}
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z", re.ASCII)
_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z", re.ASCII)
_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z", re.ASCII)


def _fail(where: str, message: str) -> None:
    raise SchemaError(f"{where}: {message}")


def _object(value: Any, required: set[str], optional: set[str], where: str) -> None:
    if type(value) is not dict:
        _fail(where, "expected an object")
    if any(type(key) is not str for key in value):
        _fail(where, "object keys must be strings")
    missing, extra = required - value.keys(), value.keys() - required - optional
    if missing:
        _fail(where, f"missing keys: {', '.join(sorted(missing))}")
    if extra:
        _fail(where, f"unknown keys: {', '.join(sorted(extra))}")


def _string(value: Any, where: str, *, nonempty: bool = False) -> None:
    if type(value) is not str:
        _fail(where, "expected a string")
    if len(value) > MAX_STRING_BYTES:
        _fail(where, f"string exceeds {MAX_STRING_BYTES} UTF-8 bytes")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        _fail(where, "string must contain Unicode scalar values (no surrogates)")
    if size > MAX_STRING_BYTES:
        _fail(where, f"string exceeds {MAX_STRING_BYTES} UTF-8 bytes")
    if nonempty and not value.strip():
        _fail(where, "expected a nonempty string")


def _slug(value: Any, where: str) -> None:
    if type(value) is not str or not 1 <= len(value) <= 64 or not _SLUG.fullmatch(value):
        _fail(where, "expected a 1-64 character lowercase ASCII, hyphen-separated slug")


def _identifier(value: Any, where: str) -> None:
    if (
        type(value) is not str
        or not _IDENTIFIER.fullmatch(value)
        or "__" in value
        or value in _RESERVED
    ):
        _fail(where, "expected a non-reserved identifier safe in both Python and C++")


def _array(value: Any, where: str, maximum: int, minimum: int = 0) -> None:
    if type(value) is not list or not minimum <= len(value) <= maximum:
        _fail(where, f"expected a list with {minimum}..{maximum} entries")


def _serialized_bound(value: Any, where: str) -> None:
    size = 0
    for fragment in json.JSONEncoder(ensure_ascii=True, allow_nan=False).iterencode(value):
        size += len(fragment)
        if size > MAX_PACK_BYTES:
            _fail(where, f"serialized JSON exceeds {MAX_PACK_BYTES} bytes")


def validate_type(type_: Any, *, allow_void: bool = False, where: str = "type", depth: int = 0) -> None:
    """Validate a recursive type descriptor without modifying it."""
    if depth > MAX_TYPE_DEPTH:
        _fail(where, f"type nesting exceeds {MAX_TYPE_DEPTH}")
    if type(type_) is str:
        if type_ not in {"int", "bool", "str"} and not (allow_void and type_ == "void"):
            _fail(where, "expected int, bool, str, or a recursive type (void is return-only)")
        return
    if type(type_) is not dict or len(type_) != 1:
        _fail(where, "expected a primitive type or a single-key recursive type object")
    kind = next(iter(type_))
    if type(kind) is not str or kind not in {"list", "map", "optional"}:
        _fail(where, "recursive type key must be list, map, or optional")
    validate_type(type_[kind], where=f"{where}.{kind}", depth=depth + 1)


def validate_value(value: Any, type_: Any, where: str = "value", *, _budget: list[int] | None = None) -> None:
    """Check exact runtime values; bool is never accepted as int.

    The descriptor must already have been validated with :func:`validate_type`.
    """
    budget = [MAX_VALUE_NODES] if _budget is None else _budget

    def visit(item: Any, descriptor: Any, path: str, depth: int) -> None:
        budget[0] -= 1
        if budget[0] < 0:
            _fail(path, f"value node budget exceeds {MAX_VALUE_NODES}")
        if depth > MAX_TYPE_DEPTH + 1:
            _fail(path, "value nesting exceeds the supported depth")
        if descriptor == "int":
            if type(item) is not int or not -(1 << 63) <= item < (1 << 63):
                _fail(path, "expected an exact signed 64-bit integer (not bool)")
        elif descriptor == "bool":
            if type(item) is not bool:
                _fail(path, "expected an exact bool")
        elif descriptor == "str":
            _string(item, path)
        elif descriptor == "void":
            if item is not None:
                _fail(path, "void must be represented by null")
        elif type(descriptor) is dict:
            kind, nested = next(iter(descriptor.items()))
            if kind == "optional":
                if item is not None:
                    visit(item, nested, path, depth + 1)
            elif kind == "list":
                _array(item, path, MAX_COLLECTION)
                for index, child in enumerate(item):
                    visit(child, nested, f"{path}[{index}]", depth + 1)
            elif kind == "map":
                if type(item) is not dict or len(item) > MAX_COLLECTION:
                    _fail(path, f"expected a string-keyed map with at most {MAX_COLLECTION} entries")
                for key, child in item.items():
                    _string(key, f"{path}.<key>")
                    visit(child, nested, f"{path}[{key[:80]!r}]", depth + 1)
            else:
                _fail(path, "invalid type descriptor")
        else:
            _fail(path, "invalid type descriptor")

    visit(value, type_, where, 0)


def _params(params: Any, where: str, *, constructor: bool = False) -> None:
    _array(params, where, MAX_PARAMS)
    names: set[str] = set()
    for index, param in enumerate(params):
        at = f"{where}[{index}]"
        _object(param, {"name", "type"}, {"mode"}, at)
        _identifier(param["name"], f"{at}.name")
        if param["name"] in names:
            _fail(at, f"duplicate parameter {param['name']!r}")
        names.add(param["name"])
        validate_type(param["type"], where=f"{at}.type")
        mode = param.get("mode", "in")
        if type(mode) is not str or mode not in {"in", "inout"}:
            _fail(f"{at}.mode", "expected in or inout")
        if constructor and mode != "in":
            _fail(f"{at}.mode", "constructor parameters cannot be inout")


def validate_interface(interface: Any, *, part_count: int | None = None, where: str = "interface") -> None:
    _object(interface, {"constructor", "methods"}, set(), where)
    _params(interface["constructor"], f"{where}.constructor", constructor=True)
    _array(interface["methods"], f"{where}.methods", MAX_METHODS)
    names: set[str] = set()
    for index, method in enumerate(interface["methods"]):
        at = f"{where}.methods[{index}]"
        _object(method, {"name", "params", "returns", "since"}, set(), at)
        _identifier(method["name"], f"{at}.name")
        if method["name"] in names:
            _fail(at, f"duplicate method {method['name']!r}")
        names.add(method["name"])
        _params(method["params"], f"{at}.params")
        validate_type(method["returns"], allow_void=True, where=f"{at}.returns")
        since = method["since"]
        if type(since) is not int or since < 1 or since > (part_count or MAX_PARTS):
            _fail(f"{at}.since", "expected a valid 1-based part number")


def validate_cases(interface: dict, cases: list, *, _where: str = "cases", _budget: list[int] | None = None) -> None:
    """Validate a nonempty suite against a cumulative interface."""
    validate_interface(interface)
    _array(cases, _where, MAX_CASES, 1)
    methods = {method["name"]: method for method in interface["methods"]}
    ids: set[str] = set()
    budget = [MAX_VALUE_NODES] if _budget is None else _budget
    command_count = 0

    def arguments(values: Any, params: list, where: str) -> None:
        _array(values, where, MAX_PARAMS)
        if len(values) != len(params):
            _fail(where, f"expected {len(params)} arguments, got {len(values)}")
        for index, (value, param) in enumerate(zip(values, params)):
            validate_value(value, param["type"], f"{where}[{index}]", _budget=budget)

    for index, case in enumerate(cases):
        at = f"{_where}[{index}]"
        _object(case, {"id", "constructor", "commands"}, set(), at)
        _slug(case["id"], f"{at}.id")
        if case["id"] in ids:
            _fail(f"{at}.id", f"duplicate case id {case['id']!r}")
        ids.add(case["id"])
        arguments(case["constructor"], interface["constructor"], f"{at}.constructor")
        _array(case["commands"], f"{at}.commands", MAX_COMMANDS, 1)
        command_count += len(case["commands"])
        if command_count > MAX_TOTAL_COMMANDS:
            _fail(_where, f"total command count exceeds {MAX_TOTAL_COMMANDS}")
        for command_index, command in enumerate(case["commands"]):
            cmd_at = f"{at}.commands[{command_index}]"
            _object(command, {"method", "args"}, {"expect", "raises", "after"}, cmd_at)
            name = command["method"]
            if type(name) is not str or name not in methods:
                _fail(f"{cmd_at}.method", f"method {name!r} is not available in this part")
            method = methods[name]
            arguments(command["args"], method["params"], f"{cmd_at}.args")
            if ("expect" in command) == ("raises" in command):
                _fail(cmd_at, "exactly one of expect or raises is mandatory")
            if "expect" in command:
                validate_value(command["expect"], method["returns"], f"{cmd_at}.expect", _budget=budget)
            elif type(command["raises"]) is not str or command["raises"] not in EXCEPTIONS:
                _fail(f"{cmd_at}.raises", "expected invalid_argument, out_of_range, or runtime_error")
            if "after" in command:
                mutable = {
                    param["name"]: param for param in method["params"] if param.get("mode", "in") == "inout"
                }
                _object(command["after"], set(), set(mutable), f"{cmd_at}.after")
                for param_name, value in command["after"].items():
                    validate_value(value, mutable[param_name]["type"], f"{cmd_at}.after.{param_name}", _budget=budget)
    _serialized_bound(cases, _where)


def _reference(value: Any, language: str, where: str) -> None:
    if type(value) is not str or not _FILENAME.fullmatch(value) or ".." in value:
        _fail(where, "reference must be a simple safe relative filename")
    stem = value.split(".", 1)[0].upper()
    reserved = {"CON", "PRN", "AUX", "NUL", "CLOCK$"}
    reserved.update(f"{prefix}{index}" for prefix in ("COM", "LPT") for index in range(1, 10))
    if stem in reserved or value.endswith("."):
        _fail(where, "reserved filenames are not permitted")
    if not value.endswith(".py" if language == "python" else ".cpp"):
        _fail(where, f"reference must end with {'.py' if language == 'python' else '.cpp'}")


def validate_pack(pack: dict) -> None:
    _object(
        pack,
        {"schema", "id", "title", "family", "origin", "interface", "parts", "references"},
        set(),
        "pack",
    )
    if type(pack["schema"]) is not int or pack["schema"] != 1:
        _fail("pack.schema", "only schema version 1 is supported")
    _slug(pack["id"], "pack.id")
    _string(pack["title"], "pack.title", nonempty=True)
    if type(pack["family"]) is not str or pack["family"] not in FAMILIES:
        _fail("pack.family", "unknown family")
    _object(pack["origin"], {"kind", "seed"}, set(), "pack.origin")
    if type(pack["origin"]["kind"]) is not str or pack["origin"]["kind"] not in {"generated", "demo"}:
        _fail("pack.origin.kind", "expected generated or demo")
    _string(pack["origin"]["seed"], "pack.origin.seed")
    _object(pack["references"], {"python", "cpp"}, set(), "pack.references")
    for language, reference in pack["references"].items():
        _reference(reference, language, f"pack.references.{language}")
    _array(pack["parts"], "pack.parts", MAX_PARTS, 1)
    validate_interface(pack["interface"], part_count=len(pack["parts"]), where="pack.interface")
    if not pack["interface"]["methods"]:
        _fail("pack.interface.methods", "at least one method is required")
    seen: set[str] = set()
    exercised: set[str] = set()
    budget = [MAX_VALUE_NODES]
    command_count = 0
    for index, part in enumerate(pack["parts"]):
        at = f"pack.parts[{index}]"
        _object(part, {"title", "prompt", "public", "hidden", "invariants", "hints", "failure_question"}, set(), at)
        for name in ("title", "prompt", "failure_question"):
            _string(part[name], f"{at}.{name}", nonempty=True)
        _array(part["invariants"], f"{at}.invariants", 64, 1)
        _array(part["hints"], f"{at}.hints", 3, 3)
        for name in ("invariants", "hints"):
            for item_index, text in enumerate(part[name]):
                _string(text, f"{at}.{name}[{item_index}]", nonempty=True)
        active = _interface_for(pack, index + 1)
        for visibility in ("public", "hidden"):
            validate_cases(active, part[visibility], _where=f"{at}.{visibility}", _budget=budget)
            for case in part[visibility]:
                if case["id"] in seen:
                    _fail(f"{at}.{visibility}", f"duplicate case id {case['id']!r} across the pack")
                seen.add(case["id"])
                exercised.update(command["method"] for command in case["commands"])
                command_count += len(case["commands"])
                if command_count > MAX_TOTAL_COMMANDS:
                    _fail("pack.parts", f"total command count exceeds {MAX_TOTAL_COMMANDS}")
                if len(seen) > MAX_CASES:
                    _fail("pack.parts", f"total case count exceeds {MAX_CASES}")
    unused = {method["name"] for method in pack["interface"]["methods"]} - exercised
    if unused:
        _fail("pack.interface.methods", f"methods never exercised: {', '.join(sorted(unused))}")
    _serialized_bound(pack, "pack")


def _interface_for(pack: dict, part: int) -> dict:
    return {
        "constructor": copy.deepcopy(pack["interface"]["constructor"]),
        "methods": [copy.deepcopy(method) for method in pack["interface"]["methods"] if method["since"] <= part],
    }


def interface_for(pack: dict, part: int) -> dict:
    """Return an independent cumulative interface for a 1-based part."""
    validate_pack(pack)
    if type(part) is not int or not 1 <= part <= len(pack["parts"]):
        _fail("part", "expected a valid 1-based part number")
    return _interface_for(pack, part)


def cpp_type(type_: Any) -> str:
    validate_type(type_, allow_void=True)
    if type(type_) is str:
        return {"int": "std::int64_t", "bool": "bool", "str": "std::string", "void": "void"}[type_]
    kind, nested = next(iter(type_.items()))
    inner = cpp_type(nested)
    return {
        "list": f"std::vector<{inner}>",
        "optional": f"std::optional<{inner}>",
        "map": f"std::map<std::string, {inner}>",
    }[kind]


def python_type(type_: Any) -> str:
    validate_type(type_, allow_void=True)
    if type(type_) is str:
        return {"int": "int", "bool": "bool", "str": "str", "void": "None"}[type_]
    kind, nested = next(iter(type_.items()))
    inner = python_type(nested)
    return {"list": f"list[{inner}]", "optional": f"{inner} | None", "map": f"dict[str, {inner}]"}[kind]
