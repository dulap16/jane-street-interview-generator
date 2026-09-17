"""Deterministic end-to-end demo, with no model or API key."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=("python", "cpp"), default="python")
    args = parser.parse_args()
    compiler = os.environ.get("INTERVIEW_LAB_COMPILER")
    if args.language == "cpp" and not any(shutil.which(c) for c in ([compiler] if compiler else ["clang++", "g++", "cl"])):
        print("SKIP: no C++ compiler available. C++ runtime verification is pending, NOT passed.")
        return 77
    with tempfile.TemporaryDirectory(prefix="interview lab smoke ") as directory:
        project = Path(directory)
        shutil.copytree(ROOT / "demos" / "ledger", project / "demos" / "ledger")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        # Config stores a portable executable name, while PATH selects this
        # smoke script's interpreter even when it lives in a virtual environment.
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        def command(*parts, stdin=None):
            result = subprocess.run([sys.executable, "-m", "interview_lab", "--root", str(project), *parts],
                                    input=json.dumps(stdin) if stdin is not None else None,
                                    text=True, encoding="utf-8", capture_output=True,
                                    cwd=ROOT / "scripts", env=env, timeout=120)
            if result.returncode != 0:
                raise RuntimeError(f"{parts[0]} failed ({result.returncode}): {result.stdout}\n{result.stderr}")
            return json.loads(result.stdout)
        command("doctor")
        prepared = command("demo", "--id", "smoke", "--language", args.language)
        assert prepared["phase"] == "ready"
        start = command("start", "smoke", "--familiar", "yes")
        assert start["part"] == 1 and len(start["parts"]) == 1
        command("watch", "smoke", "--once")
        consumed = command("hook", stdin={"hook_event_name": "UserPromptSubmit", "session_id": "smoke-claude",
                                         "prompt_id": "smoke-think", "prompt": "think: I will check state invariants."})
        assert consumed["decision"] == "block"
        context = command("hook", stdin={"hook_event_name": "UserPromptSubmit", "session_id": "smoke-claude",
                                        "prompt_id": "smoke-normal", "prompt": "I am ready to test the implementation."})
        assert len(json.loads(context["hookSpecificOutput"]["additionalContext"])["narration"]) == 1
        suffix = "py" if args.language == "python" else "cpp"
        # This is deliberately a familiar demonstration, not a scored attempt.
        solution = project / ".interview-lab" / "sessions" / "smoke" / "candidate" / f"solution.{suffix}"
        shutil.copyfile(project / "demos" / "ledger" / f"reference.{suffix}", solution)
        for part in range(1, start["parts_total"] + 1):
            gate = command("done", "smoke")
            assert gate["gate_passed"], f"Part {part} did not pass"
            stage = command("reveal", "smoke")
        assert stage["phase"] == "ended" and stage["end_reason"] == "completed"
        command("reference", "smoke")
        evidence = command("evidence", "smoke")
        assert (project / evidence["path"]).is_file()
        assert command("review", "smoke")["status"] == "ungraded"
        assert command("progress")["eligible_interviews"] == 0
        command("metrics", "smoke")
        print(f"PASS: {args.language} full {start['parts_total']}-part demo, hooks, evidence, gating and ungraded progress.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
