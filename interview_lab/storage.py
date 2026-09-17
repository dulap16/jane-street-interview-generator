"""Checksummed, atomic session transactions with kernel-owned file locks."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time


class LabError(Exception):
    """An actionable error safe to show to the candidate."""


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", value):
        raise LabError("IDs must be 1-64 lowercase letters, digits or hyphens, starting with a letter.")
    if re.fullmatch(r"(con|prn|aux|nul|com[1-9]|lpt[1-9])", value):
        raise LabError("Reserved filesystem ID.")
    return value


def safe_child(root: Path, *pieces: str) -> Path:
    root = root.resolve()
    target = root.joinpath(*pieces)
    if not target.resolve().is_relative_to(root):
        raise LabError("Path escapes its storage directory (including symlinks).")
    return target


def read_json(path: Path, limit: int = 16_000_000) -> object:
    if path.stat().st_size > limit:
        raise LabError(f"JSON file exceeds {limit} bytes.")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise LabError("Duplicate JSON object key.")
            result[key] = value
        return result
    def invalid_constant(value):
        raise LabError(f"Non-finite JSON number: {value}.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                           parse_constant=invalid_constant)
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            if depth > 64:
                raise LabError("JSON container nesting exceeds 64 levels.")
            if isinstance(item, dict):
                pending.extend((child, depth + 1) for child in item.values())
            elif isinstance(item, list):
                pending.extend((child, depth + 1) for child in item)
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise LabError("Invalid UTF-8 JSON file or excessive JSON nesting.") from exc


def atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, value: object) -> None:
    atomic_bytes(path, canonical(value) + b"\n")


@contextlib.contextmanager
def file_lock(path: Path, timeout: float = 3.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        deadline = time.monotonic() + timeout
        acquired = False
        while not acquired:
            stream.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise LabError("Session is busy. Retry after the current command finishes.") from exc
                time.sleep(0.025)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.home = safe_child(self.root, ".interview-lab")

    def session(self, session_id: str) -> Path:
        return safe_child(self.home, "sessions", identifier(session_id))

    def load(self, session_id: str, *, backup: bool = False) -> dict:
        path = safe_child(self.session(session_id), "state.backup.json" if backup else "state.json")
        if not path.exists():
            raise LabError("Session state not found. Prepare a session first.")
        record = read_json(path, limit=32_000_000)
        if (not isinstance(record, dict) or set(record) != {"payload", "sha256"}
                or digest(record["payload"]) != record["sha256"]):
            raise LabError("Session state checksum failed. Inspect files, then use recover --from-backup.")
        state = record["payload"]
        if (not isinstance(state, dict) or state.get("schema") != 1
                or state.get("id") != session_id or not isinstance(state.get("events"), list)
                or state.get("phase") not in {"ready", "active", "paused", "ended"}):
            raise LabError("Unsupported or corrupt session state.")
        for index, event in enumerate(state["events"], 1):
            if not isinstance(event, dict) or event.get("id") != f"e{index:06d}":
                raise LabError("Broken session event sequence.")
        return state

    def save(self, state: dict, *, keep_backup: bool = True) -> None:
        path = safe_child(self.session(state["id"]), "state.json")
        if keep_backup and path.exists():
            # A complete previous revision remains available after a torn write.
            atomic_bytes(path.with_name("state.backup.json"), path.read_bytes())
        atomic_json(path, {"payload": state, "sha256": digest(state)})

    @contextlib.contextmanager
    def transaction(self, session_id: str):
        folder = self.session(session_id)
        if not safe_child(folder, "state.json").is_file():
            raise LabError("Session state not found. Prepare a session first.")
        with file_lock(safe_child(folder, ".lock")):
            state = self.load(session_id)
            before = digest(state)
            try:
                yield state
            finally:
                # Expiry and completed evidence survive even a rejected operation.
                if digest(state) != before:
                    self.save(state)

    def active(self) -> str | None:
        path = safe_child(self.home, "active.json")
        if not path.exists():
            return None
        value = read_json(path)
        if not isinstance(value, dict) or set(value) != {"id"}:
            raise LabError("Corrupt active-session pointer.")
        return identifier(value["id"])

    def set_active(self, session_id: str) -> None:
        with file_lock(safe_child(self.home, ".active.lock")):
            atomic_json(safe_child(self.home, "active.json"), {"id": identifier(session_id)})
