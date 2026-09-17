# Claude Code integration and verification

Official sources inspected on **2026-09-17**:

- [Skills](https://code.claude.com/docs/en/skills): project
  `.claude/skills/<name>/SKILL.md`, YAML frontmatter, supporting files and
  `disable-model-invocation`.
- [Hooks reference](https://code.claude.com/docs/en/hooks): project settings,
  `UserPromptSubmit` JSON stdin, `decision: "block"`, user-only `reason`,
  and `hookSpecificOutput.additionalContext`.
- [Status line](https://code.claude.com/docs/en/statusline): `statusLine`
  `type: "command"`, shell command and JSON stdin, optional `padding`, and
  **`refreshInterval` (minimum 1 second)**.
- [Subagents](https://code.claude.com/docs/en/sub-agents): project
  `.claude/agents/*.md`, required name/description and tools frontmatter,
  separate context and no need for Git/worktree isolation.

The development host has **Claude Code 2.1.197**. Reading current documentation
is not proof every current optional feature exists in this older binary.
Tests exercise actual hook stdin/stdout and session behavior locally; they
do not claim a live paid Claude turn, silent-prompt UI rendering, IDE extension,
grader invocation or idle status-line refresh was observed.

## Safe project-local setup

After package installation:

```text
python -m interview_lab setup-claude
python -m interview_lab setup-claude --apply
```

Preview:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python -m interview_lab hook",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

No matcher is needed for this event. The conservative shell command has no
hard-coded script path, shell-specific path expansion or newly introduced exec
`args` field. Both the hook and status-line command need `python` to resolve
to the environment where the package is installed. Hook input `cwd`,
`CLAUDE_PROJECT_DIR` when supplied, and status-line `workspace.project_dir`
let the handler locate its project even when another command changes cwd.

Setup merges exactly one identical hook and preserves existing hook groups and
unrelated project settings. It refuses to replace an existing different status
line. Inspect the preview and merge manually for a customized configuration.
The tool never writes `~/.claude` or any global settings. `.gitignore` excludes
generated project settings so local choices are not accidentally published.

## Countdown

`watch ID` prints independently of model turns, observes saved code, and emits
configured checkpoints. It works in a separate terminal without a background
daemon. Ctrl+C stops the watcher, **not** the interview clock.

An optional event-updated status line can be enabled:

```text
python -m interview_lab setup-claude --apply --statusline
```

Current official docs additionally support a one-second idle refresh:

```text
python -m interview_lab setup-claude --statusline --refresh-interval 1
```

This previews the optional setting; apply it only to a compatible Claude version
after inspecting/merging the preview. Default setup does **not** set
`refreshInterval` because the installed older host has not been verified to
honor it. It is a real current documented option, not an invented field.
Status lines may hide during UI interactions. Keep `watch` as the dependable
visible clock. Claude is not promised to speak while idle or after a checkpoint.

Official hook documentation says hook events also fire in IDE/desktop/cloud
surfaces. This project has **not** live-tested those surfaces, and does not
claim a terminal status bar is rendered by an IDE. Run watch in a terminal when
using an IDE. The hooks execute only where this local Python package and project
files actually exist; a remote/cloud session needs its own installed copy.

## Silent listener protocol

1. A `think:` prompt is saved in the active session with a timestamp/event ID.
2. Silent mode returns exit **0**, JSON `decision: "block"` and an acknowledgement
   in `reason`. Per the official `UserPromptSubmit` semantics, the prompt is
   removed before model processing and `reason` is shown to the user, not added
   to model context. This is intentional consumption, not an application error.
3. The next normal prompt is saved as candidate communication and gets one
   `additionalContext` JSON string containing current clock/part, resolved
   settings, and pending narration. Pending entries are consumed transactionally.
4. Reactive mode instead allows the prompt and injects its narration immediately.

Example JSON input for a direct local protocol check:

```json
{
  "hook_event_name": "UserPromptSubmit",
  "session_id": "local-probe",
  "prompt_id": "one",
  "prompt": "think: I should state my invariant before coding."
}
```

Feed it to `python -m interview_lab hook` via stdin with a started active session.
Then feed a normal prompt with a new `prompt_id`. The automated smoke script
does exactly this, with no model call.

First input binds the active interview to its Claude `session_id`; input from
another Claude session is blocked rather than contaminating evidence. Run
`resume ID` to explicitly rebind on the next prompt. Subagent-tagged hook
events are ignored as non-candidate communication.

`prompt_id` deduplicates retries when supplied (official docs introduce it in
2.1.196). Older/omitting clients lack a reliable retry key: identical intended
utterances are not deduplicated by content. The local transaction provides
**at-most-once delivery**, not a distributed exactly-once promise: if the hook
is killed after committing consumption but before stdout reaches Claude, the
delivery can be lost. Original evidence remains available for a human to
inspect/replay. `context ID` also consumes pending entries, so don't call it
speculatively just before a hook expecting the same notes.

A malformed hook, missing runtime, busy state or storage error is a real
integration failure. The hook exits 2 with an explicit error, rather than
pretending narration was stored. A command hook timeout can fail open according
to current Claude docs; this integration is not a security enforcement system.

## Fresh grading context

The `interview-grader` definition uses a read-only tool scope and a separate
context. Pass only `docs/rubric.md` and the ended interview's exported evidence
path, not the interviewer's opinion or entire conversation. Do not use a
conversation fork, worktree isolation, persistent agent memory, or a global
agent installation. Project CLAUDE.md files can still be loaded by supported
Claude versions: this distribution supplies none. The newer `omitClaudeMd`
option is intentionally not relied on by the older installed host.

The agent returns structured JSON; the interviewer writes that artifact and
runs `debrief ID FILE`. If custom subagents are unavailable, open a **fresh**
Claude context and supply the same two files, or obtain a human-authored debrief.
Never substitute made-up output when no grader has run. Citation checks attest
to source presence and document shape, not whether an assessment is wise.
