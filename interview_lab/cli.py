"""Portable command-line entry point."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import secrets
import sys
import time

from . import __version__, config
from .feedback import (evidence_payload, export_evidence, import_debrief, metrics, progress,
                       select_family, validate_debrief)
from .integration import hook, setup, statusline_text
from .session import Lab, tick
from .storage import LabError, digest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="interview-lab",
                                     description="Local interview practice. Running code is NOT sandboxed.")
    result.add_argument("--root", type=Path, help="Project folder; use before the command.")
    result.add_argument("--version", action="version", version=__version__)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Report available runtimes and compilers.")
    cfg = commands.add_parser("config")
    cfg.add_argument("--set", action="append", default=[])
    selection = commands.add_parser("select", help="Select a family for skill-driven authoring.")
    selection.add_argument("--family")
    selection.add_argument("--seed", help="Reproducible seed; otherwise a fresh seed is printed.")
    for name in ("validate", "prepare", "demo"):
        cmd = commands.add_parser(name)
        if name != "demo":
            cmd.add_argument("pack", type=Path)
        if name != "validate":
            cmd.add_argument("--id", required=True)
        cmd.add_argument("--language", choices=("python", "cpp"))
        cmd.add_argument("--compiler", help="Compiler executable name; absolute paths via INTERVIEW_LAB_COMPILER.")
        cmd.add_argument("--set", action="append", default=[])
    start = commands.add_parser("start")
    start.add_argument("id")
    start.add_argument("--familiar", choices=("yes", "no"), required=True)
    for name in ("show", "pause", "resume", "end", "done", "reveal", "metrics",
                 "evidence", "review", "reference"):
        commands.add_parser(name).add_argument("id")
    for name in ("status", "context"):
        commands.add_parser(name).add_argument("id", nargs="?")
    test = commands.add_parser("test")
    test.add_argument("id")
    flags = test.add_mutually_exclusive_group()
    flags.add_argument("--public", action="store_true")
    flags.add_argument("--gate", action="store_true")
    test.add_argument("--cases", type=Path, help="Candidate-authored JSON case array; public runs only.")
    hint = commands.add_parser("hint")
    hint.add_argument("id")
    hint.add_argument("--level", type=int, choices=(1, 2, 3), required=True)
    for name in ("think", "message"):
        cmd = commands.add_parser(name)
        cmd.add_argument("id")
        cmd.add_argument("text")
    watch = commands.add_parser("watch")
    watch.add_argument("id")
    watch.add_argument("--interval", type=float, default=1.0)
    watch.add_argument("--once", action="store_true")
    debrief = commands.add_parser("debrief")
    debrief.add_argument("id")
    debrief.add_argument("file", type=Path)
    replay = commands.add_parser("replay")
    replay.add_argument("id")
    replay.add_argument("--event", required=True)
    recover = commands.add_parser("recover")
    recover.add_argument("id")
    recover.add_argument("--from-backup", action="store_true", required=True)
    commands.add_parser("progress")
    commands.add_parser("hook")
    commands.add_parser("statusline")
    integration = commands.add_parser("setup-claude")
    integration.add_argument("--apply", action="store_true")
    integration.add_argument("--statusline", action="store_true")
    integration.add_argument("--refresh-interval", type=int)
    return result


def find_root(explicit: Path | None, payload: dict | None = None) -> Path:
    if explicit:
        root = explicit.resolve()
        if not root.is_dir():
            raise LabError("--root must point to an existing project folder.")
        return root
    payload = payload or {}
    workspace = payload.get("workspace", {})
    if not isinstance(workspace, dict):
        raise LabError("Invalid statusline workspace input.")
    hint = os.environ.get("CLAUDE_PROJECT_DIR") or workspace.get("project_dir") or payload.get("cwd")
    start = Path(hint).resolve() if isinstance(hint, str) else Path.cwd().resolve()
    for folder in (start, *start.parents):
        if (folder / ".interview-lab").is_dir() or (
            (folder / "pyproject.toml").is_file() and (folder / "interview_lab").is_dir()
        ):
            return folder
    return start


def doctor(root: Path) -> dict:
    from .execution import probe_python
    cfg = config.resolve(root)
    compiler = os.environ.get("INTERVIEW_LAB_COMPILER") or cfg["compiler"]
    candidates = [compiler] if compiler else ["clang++", "g++", "cl"]
    compilers = [value for value in candidates if value and shutil.which(value)]
    return {"tool_python": sys.version.split()[0], "configured_python": probe_python(cfg["python_executable"]),
            "cpp_compilers": compilers,
            "cpp_runtime_verification": "Run scripts/smoke.py --language cpp" if compilers else "UNAVAILABLE: install/provide a C++17 compiler yourself.",
            "claude_code_on_path": bool(shutil.which("claude")),
            "safety": "Candidate and reference processes run with your permissions. This is NOT a sandbox."}


def run(args: argparse.Namespace, lab: Lab):
    name = args.command
    if name == "doctor":
        return doctor(lab.root)
    if name == "config":
        overrides = config.parse_overrides(args.set)
        return config.save(lab.root, overrides) if overrides else config.resolve(lab.root)
    if name == "select":
        return select_family(lab, args.family or config.resolve(lab.root)["family"],
                             args.seed if args.seed is not None else secrets.token_hex(8))
    if name in {"validate", "prepare", "demo"}:
        overrides = config.parse_overrides(args.set)
        if args.language:
            overrides["language"] = args.language
        if args.compiler:
            overrides["compiler"] = args.compiler
        pack = lab.root / "demos" / "ledger" / "pack.json" if name == "demo" else args.pack.resolve()
        if name == "validate":
            return lab.validate_problem(pack, overrides)
        return lab.prepare(pack, args.id, overrides)
    if name == "start":
        return lab.start(args.id, args.familiar == "yes")
    if name in {"status", "show", "pause", "resume", "end", "reveal", "context", "reference", "recover"}:
        return getattr(lab, name)(args.id)
    if name == "test":
        return lab.test(args.id, gate=args.gate, cases_path=args.cases)
    if name == "done":
        return lab.test(args.id, gate=True, done=True)
    if name == "hint":
        return lab.hint(args.id, args.level)
    if name in {"think", "message"}:
        return lab.communicate(args.id, args.text, narration=name == "think")
    if name == "watch":
        if not math.isfinite(args.interval) or not 0.1 <= args.interval <= 60:
            raise LabError("--interval must be between 0.1 and 60 seconds.")
        while True:
            value = lab.observe(args.id)
            if args.once:
                return value
            seconds = math.ceil(value["remaining_seconds"])
            line = f"{value['id']} | {value['phase']} | part {value['part']}/{value['parts_total']} | {seconds // 60:02d}:{seconds % 60:02d}"
            if sys.stdout.isatty():
                print("\r" + line.ljust(90), end="", flush=True)
            else:
                print(line, flush=True)
            for alert in value["alerts"]:
                print(f"\n[checkpoint] {alert}", flush=True)
            if value["phase"] in {"ended", "ready"}:
                print()
                return {"watch": "stopped", "phase": value["phase"]}
            time.sleep(args.interval)
    if name == "metrics":
        with lab.store.transaction(args.id) as state:
            tick(state, lab.clock())
            return metrics(state)
    if name == "evidence":
        return export_evidence(lab, args.id)
    if name == "debrief":
        return import_debrief(lab, args.id, args.file.resolve())
    if name in {"review", "replay"}:
        with lab.store.transaction(args.id) as state:
            tick(state, lab.clock())
            if state["phase"] != "ended":
                raise LabError("Review and replay are available after ending the session.")
            if name == "review":
                if state["debrief"] is None:
                    return {"status": "ungraded", "notice": "No grader executed; export evidence and import a genuine debrief."}
                evidence = evidence_payload(state)
                evidence["evidence_digest"] = digest(evidence)
                validate_debrief(state["debrief"], evidence)
                return state["debrief"]
            entry = next((e for e in state["events"] if e["id"] == args.event), None)
            if entry is None:
                raise LabError("Unknown replay event ID.")
            return entry
    if name == "progress":
        return progress(lab)
    if name == "setup-claude":
        return setup(lab, apply=args.apply, statusline=args.statusline, refresh_interval=args.refresh_interval)
    raise LabError("Unimplemented command.")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        payload = None
        if args.command in {"hook", "statusline"}:
            raw = sys.stdin.read(64_001)
            if len(raw) > 64_000:
                raise LabError("Hook input exceeds 64 KiB.")
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, RecursionError) as exc:
                raise LabError("Hook input must be valid JSON.") from exc
            if not isinstance(payload, dict):
                raise LabError("Hook input must be an object.")
        lab = Lab(find_root(args.root, payload))
        if args.command == "hook":
            result = hook(lab, payload)
        elif args.command == "statusline":
            print(statusline_text(lab))
            return 0
        else:
            result = run(args, lab)
        print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
        if isinstance(result, dict) and (result.get("status") == "invalid_problem"
                                        or result.get("public", {}).get("status", "passed") != "passed"
                                        or result.get("gate_passed") is False):
            return 1
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted. Saved session state remains resumable; an interview clock does not pause.", file=sys.stderr)
        return 130
    except (LabError, OSError) as exc:
        if args.command == "hook":
            # Unlike narration, a broken integration must be surfaced as an error.
            print(f"Interview Lab hook error: {exc}", file=sys.stderr)
            return 2
        if args.command == "statusline":
            print(f"Interview Lab | error: {exc}")
            return 1
        print(json.dumps({"error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 2
