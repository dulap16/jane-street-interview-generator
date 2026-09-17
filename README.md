# Interview Lab

Practice evolving coding interviews with Claude Code: discuss your approach,
write Python or C++ in your editor, and get evidence-based feedback afterward.
Claude interviews you; it does not write your solution.

## What you need

- **Python 3.11+** and **Claude Code**, installed and signed in.
- An editor for your solution file.
- For C++ practice only: a working C++17/20 compiler (`g++`, `clang++`, or `cl`).

## One-time setup

Extract the folder somewhere you want to keep it. Open a terminal **inside
that folder** and run the setup for your platform.

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m interview_lab setup-claude --apply
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m interview_lab setup-claude --apply
```

This adds the interview hook to this folder's Claude settings, not your global
settings. If Claude was already open, close it and launch it again below.
If activation or installation fails, see [troubleshooting](docs/troubleshooting.md).
If you move the folder later, repeat the environment/install setup there.

## Start practicing: each time

Open a terminal in this folder, activate the environment, then launch Claude.

**Windows PowerShell**

```powershell
.\.venv\Scripts\Activate.ps1
claude
```

On macOS/Linux, use `source .venv/bin/activate` followed by `claude`.

Inside Claude, enter:

```text
/interview-lab
```

Then say, for example:

> Start a fresh 45-minute Python interview with a collaborative interviewer
> and standard hints. Tell me which solution file to open and how to show
> the timer.

Claude prepares and checks the problem before starting the clock, then gives
you the first part and your solution-file path. Say honestly if the question
is familiar, or ask for another one.

## During the interview

Keep **two terminal windows** open, with your editor alongside them:

1. **Claude terminal:** discuss the problem, ask clarifying questions and explain
   your approach. Open the solution file Claude names in your editor; edit and
   **save** that file yourself.
2. **Timer terminal:** open another terminal in this same folder, activate the
   environment as above, and paste the **session-specific timer command Claude
   gives you**. Leave it running to see the countdown while you work.

When ready, tell Claude **"I'm done with this part."** Claude runs the tests,
helps you investigate failures, and reveals the next part only after the
current saved implementation passes. Save your edits before asking to test.

Optional: type thoughts in Claude with `think:`:

```text
think: I want to check what happens when the same key appears twice.
```

In the default silent mode, this is saved and acknowledged without a model
reply. Your next ordinary message delivers the accumulated reasoning.

When finished, say **"End the interview and give me feedback."** Claude ends
the session and requests an independent, evidence-based debrief. Feedback
requires that grading step; the tool does not invent scores if it cannot run.

**Normal practice does not require manually running test, done, reveal,
evidence or grading commands. Ask Claude to handle them.** Closing a terminal
does not pause an interview clock; ask to resume the same session if needed.

## Change your preferences

Tell Claude before starting: "Use C++", "Make this 25 minutes", "No hints",
"Focus on parsers", or "Use study mode so I can pause." Preferences are fixed
when the session is prepared; study sessions stay out of scored interview trends.
See [configuration details](DEVELOPMENT.md#configuration) for all options.

## Help and important limits

[Setup troubleshooting](docs/troubleshooting.md) ·
[Claude integration details](docs/claude-integration.md) ·
[Developer guide and manual commands](DEVELOPMENT.md)

Run only code you trust: local execution is **not sandboxed**. C++ needs your
own compiler and was not runtime-verified on the build host. A live Claude
interview has not yet been verified; local CLI/hook checks are documented in the
[verification record](docs/verification.md). This is practice, not a hiring prediction.
Keep secrets out of code and narration; see [privacy and packaging](DEVELOPMENT.md#privacy-safety-and-zipping).
