"""Strict, portable configuration. Editor and docs policies are honor-system."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re

from .storage import LabError, atomic_json, file_lock, read_json, safe_child

FAMILIES = ("cache", "simulation", "parser", "graph", "stream", "scheduling",
            "orderbook", "spatial", "filesystem", "workflow")
PRESETS = {"short": 25, "standard": 45, "extended": 70}
PRESET_FORMATS = {"short": "focused", "standard": "evolving", "extended": "code-and-discuss"}
DEFAULTS = {
    "language": "python", "python_version": "3.11+", "python_executable": "python",
    "cpp_standard": "c++17", "compiler": None, "duration_minutes": 45,
    "preset": "standard", "family": "random", "style": "collaborative",
    "session_format": "evolving",
    "hint_policy": "standard", "docs_allowed": True, "narration": "silent",
    "mode": "interview", "checkpoints": [15, 5, 1], "comment_narration": False,
    "test_timeout": 3.0, "output_limit": 65536,
}
ENUMS = {
    "language": {"python", "cpp"}, "python_version": {"3.11+", "3.11", "3.12", "3.13", "3.14"},
    "cpp_standard": {"c++17", "c++20"}, "preset": set(PRESETS),
    "session_format": {"focused", "evolving", "code-and-discuss"},
    "family": set(FAMILIES) | {"random", "weakest"},
    "style": {"collaborative", "neutral", "skeptical"},
    "hint_policy": {"strict", "standard", "learning"},
    "narration": {"silent", "reactive"}, "mode": {"interview", "study"},
}


def validate(config: dict) -> dict:
    if not isinstance(config, dict) or set(config) != set(DEFAULTS):
        raise LabError("Configuration has missing or unknown keys.")
    for key, choices in ENUMS.items():
        if not isinstance(config[key], str) or config[key] not in choices:
            raise LabError(f"Invalid {key}; choose from {', '.join(sorted(choices))}.")
    for key in ("docs_allowed", "comment_narration"):
        if type(config[key]) is not bool:
            raise LabError(f"{key} must be true or false.")
    for key, low, high in (("duration_minutes", 0.01, 240), ("test_timeout", 0.05, 60)):
        value = config[key]
        if type(value) not in {int, float} or not math.isfinite(value) or not low <= value <= high:
            raise LabError(f"{key} must be a finite number from {low} to {high}.")
    if type(config["output_limit"]) is not int or not 1024 <= config["output_limit"] <= 1_048_576:
        raise LabError("output_limit must be an integer from 1024 to 1048576.")
    points = config["checkpoints"]
    if (not isinstance(points, list) or len(points) > 20
            or any(type(p) not in {int, float} or not math.isfinite(p) or not 0 < p <= 240 for p in points)
            or len(set(points)) != len(points)):
        raise LabError("checkpoints must be up to 20 distinct positive minutes (at most 240).")
    for key in ("python_executable", "compiler"):
        value = config[key]
        if value is None and key == "compiler":
            continue
        # Persist executable names, not host-specific paths or shell fragments.
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.+-]+", value):
            raise LabError(f"{key} must be a PATH executable name. Use INTERVIEW_LAB_COMPILER for an absolute compiler path.")
    return config


def parse_overrides(settings: list[str]) -> dict:
    result = {}
    for setting in settings:
        if "=" not in setting:
            raise LabError("Overrides must have the form key=value.")
        key, raw = setting.split("=", 1)
        if key not in DEFAULTS or key in result:
            raise LabError(f"Unknown or repeated setting: {key}.")
        try:
            value = json.loads(raw)
        except RecursionError as exc:
            raise LabError("Configuration JSON nesting is excessive.") from exc
        except json.JSONDecodeError:
            value = raw
        result[key] = value
    return result


def resolve(root: Path, overrides: dict | None = None) -> dict:
    result = dict(DEFAULTS)
    path = safe_child(root, ".interview-lab", "config.json")
    if path.exists():
        persisted = read_json(path)
        validate(persisted)
        result.update(persisted)
    overrides = overrides or {}
    unknown = set(overrides) - set(DEFAULTS)
    if unknown:
        raise LabError(f"Unknown settings: {', '.join(sorted(unknown))}.")
    if "preset" in overrides and "duration_minutes" not in overrides:
        if not isinstance(overrides["preset"], str) or overrides["preset"] not in PRESETS:
            raise LabError("Unknown session preset.")
        result["duration_minutes"] = PRESETS[overrides["preset"]]
    if "preset" in overrides and "session_format" not in overrides:
        if not isinstance(overrides["preset"], str) or overrides["preset"] not in PRESET_FORMATS:
            raise LabError("Unknown session preset.")
        result["session_format"] = PRESET_FORMATS[overrides["preset"]]
    result.update(overrides)
    return validate(result)


def save(root: Path, overrides: dict) -> dict:
    with file_lock(safe_child(root, ".interview-lab", ".config.lock")):
        result = resolve(root, overrides)
        atomic_json(safe_child(root, ".interview-lab", "config.json"), result)
    return result
