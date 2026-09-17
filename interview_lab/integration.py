"""Claude Code documented hook protocol; no global settings are modified."""

from __future__ import annotations

import json
import math

from .session import Lab, tick
from .storage import LabError, atomic_json, file_lock, read_json, safe_child


def hook(lab: Lab, payload: dict) -> dict:
    if not isinstance(payload, dict) or payload.get("hook_event_name") != "UserPromptSubmit":
        raise LabError("Expected a UserPromptSubmit JSON object.")
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        raise LabError("Hook prompt must be a string.")
    if payload.get("agent_id"):
        return {}
    session_id = lab.store.active()
    if session_id is None:
        return {}
    with lab.store.transaction(session_id) as state:
        now = lab.clock()
        tick(state, now)
        if state["phase"] == "ready":
            return {}
        owner = payload.get("session_id")
        if not isinstance(owner, str) or not owner:
            raise LabError("Hook input requires a Claude session_id.")
        if state.get("claude_session") not in {None, owner}:
            return {"decision": "block", "reason": "This interview is bound to another Claude session. "
                    "Use interview-lab resume ID to explicitly rebind."}
        state["claude_session"] = owner
        delivery = payload.get("prompt_id")
        if delivery is not None and (not isinstance(delivery, str) or len(delivery) > 200):
            raise LabError("Invalid hook prompt_id.")
        # At-most-once locally: hook delivery cannot atomically commit with
        # Claude's context. A killed hook after commit may lose a delivery.
        if delivery and delivery in state["delivery_ids"]:
            if prompt.lstrip().lower().startswith("think:") and state["config"]["narration"] == "silent":
                return {"decision": "block", "reason": "Narration already saved; no model turn requested."}
            context = lab._context(state, consume=False)
            context["narration"] = []
            return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                           "additionalContext": json.dumps(context, ensure_ascii=True)}}
        is_think = prompt.lstrip().lower().startswith("think:")
        if state["phase"] == "ended":
            context = lab._context(state)
            return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                           "additionalContext": json.dumps(context, ensure_ascii=True)}}
        text = prompt.lstrip()[6:].strip() if is_think else prompt
        record = lab.record_text(state, text, narration=is_think, now=now)
        if delivery:
            state["delivery_ids"].append(delivery)
        if is_think and state["config"]["narration"] == "silent":
            return {"decision": "block",
                    "reason": f"Narration saved ({record['id']}, {record['elapsed']:.1f}s). "
                              "Intentionally consumed in silent-listener mode; no model reply."}
        context = lab._context(state)
        return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                       "additionalContext": json.dumps(context, ensure_ascii=True)}}


def setup(lab: Lab, *, apply: bool, statusline: bool, refresh_interval: int | None = None) -> dict:
    if refresh_interval is not None and (type(refresh_interval) is not int or refresh_interval < 1 or not statusline):
        raise LabError("--refresh-interval requires --statusline and an integer of at least 1.")
    command = "python -m interview_lab hook"
    entry = {"hooks": [{"type": "command", "command": command, "timeout": 10}]}
    additions = {"hooks": {"UserPromptSubmit": [entry]}}
    if statusline:
        additions["statusLine"] = {"type": "command", "command": "python -m interview_lab statusline"}
        if refresh_interval is not None:
            additions["statusLine"]["refreshInterval"] = refresh_interval
    if not apply:
        return {"settings": additions, "scope": ".claude/settings.json",
                "notice": "Preview only. Install this package first, then use --apply. "
                          "Watch is the reliable independent countdown; refreshInterval is opt-in for current Claude."}
    path = safe_child(lab.root, ".claude", "settings.json")
    with file_lock(safe_child(lab.root, ".claude", ".interview-lab-setup.lock")):
        settings = read_json(path) if path.exists() else {}
        if not isinstance(settings, dict):
            raise LabError("Existing project settings must be an object; nothing was changed.")
        hooks = settings.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise LabError("Existing hooks are invalid; nothing was changed.")
        existing = hooks.setdefault("UserPromptSubmit", [])
        if not isinstance(existing, list):
            raise LabError("Existing UserPromptSubmit hooks must be an array; nothing was changed.")
        if statusline and "statusLine" in settings and settings["statusLine"] != additions["statusLine"]:
            raise LabError("An existing statusLine would be overwritten. Merge the preview manually instead.")
        if entry not in existing:
            existing.append(entry)
        if statusline:
            settings["statusLine"] = additions["statusLine"]
        atomic_json(path, settings)
    return {"configured": ".claude/settings.json", "global_settings_modified": False,
            "notice": "Restart Claude after adding the first skill/agent directories. Test narration locally. "
                      "Existing hooks remain; another hook can still block or change prompt handling."}


def statusline_text(lab: Lab) -> str:
    if lab.store.active() is None:
        return "Interview Lab | no active interview"
    status = lab.status()
    seconds = math.ceil(status["remaining_seconds"])
    return f"Interview Lab | {status['phase']} | part {status['part']}/{status['parts_total']} | {seconds // 60:02d}:{seconds % 60:02d}"
