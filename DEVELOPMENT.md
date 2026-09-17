# Interview Lab development guide

For setup and everyday practice, start with the [user guide](README.md).
This document preserves the original technical reference, manual CLI workflows
and development guidance. Normal practice is driven through Claude, not by
manually orchestrating these commands.

A local coding-interview practice tool and a project-local **Claude Code skill**.
Practice explaining, implementing, testing and adapting real Python or C++ code
as a problem evolves. The interviewer collaborates without writing your solution.
The CLI owns the clock, test gates, saved evidence and reference-release rules;
Claude authors original problems and, in a fresh grading context, an evidence-cited
debrief. No separate model API key or network service is required by the tooling.

**This is a folder, not a Git repository.** Nothing initializes Git, creates a
remote, uploads code, or publishes feedback. Zip the source folder when ready.
No license has been chosen on your behalf.

## How the parts fit together

| Component | Responsibility |
|---|---|
| Claude Code skill | Authors original problem packs, conducts the interview, answers clarifications and invokes the CLI |
| Python CLI | Validates packs, persists sessions, enforces timing and advancement, captures evidence |
| Typed language adapters | Execute the candidate's `Solution` class in Python or C++ against shared JSON fixtures |
| Independent grading agent | Reads only the rubric and ended-session evidence, returns a cited assessment for CLI validation |

The skill is the conversational layer; the CLI is the authority on session
state and executed results. Claude cannot certify correctness by inspection,
grant a fake pass or turn an unimplemented discussion into a completed stage.
See [architecture and durability](docs/architecture.md) for the implementation
boundaries, process handling and storage guarantees.

### Execution lifecycle

1. Claude privately authors all stages, public/hidden fixtures, invariants,
   hints and reference files. `validate` and `prepare` check the schema and every
   stage against the selected reference before any candidate clock starts.
2. `start` creates the candidate file and reveals only the first stage. Hooks
   capture communication; a separate `watch` terminal shows the countdown and
   observes saved code. Only study mode can pause.
3. On the candidate's completion signal, `done` runs cumulative public/hidden
   tests. `reveal` requires a passing gate bound to the current part, saved
   content and completion signal. Changed code or late results cannot advance.
4. The final successful reveal, explicit `end`, or expiry ends the session.
   Only then are reference solutions and grading evidence available.
5. A fresh grader produces a structured debrief. The CLI checks its evidence
   digest/citations before accepting it; eligible interviews enter progress.

These are this tool's practice rules, not an employer's interview procedure.
The [source-to-design mapping](docs/source-to-design.md) explains that distinction.

### Project layout

```text
interview_lab\                  CLI, config, state, runners, timer and feedback
.claude\skills\interview-lab\    Interviewer and private authoring instructions
.claude\agents\                 Independent grading-agent definition
demos\ledger\                  Complete original pack and both references
scripts\smoke.py                Deterministic non-AI end-to-end check
tests\                         Unit, integration and documentation checks
docs\                          Detailed formats, architecture and protocols
.interview-lab\                 Generated private sessions and reports; do not ship
```

The [typed format](docs/typed-format.md) defines `Solution` interfaces,
stage-specific methods, JSON command scripts, exact values, expected exceptions,
mutations and Python/C++ adapters. The [family catalog](docs/families.md) and
[authoring guide](.claude/skills/interview-lab/authoring.md) describe generation.

## Install

Python **3.11+** is required. Runtime code uses only the Python standard library.
Use a virtual environment so the CLI, hooks and candidate interpreter resolve
consistently:

```text
python -m venv .venv
```

Activate with `.venv\Scripts\Activate.ps1` in Windows PowerShell, or
`source .venv/bin/activate` on macOS/Linux. If PowerShell disallows activation,
run `.venv\Scripts\python.exe` explicitly; launch Claude from a terminal whose
PATH selects that environment when using hooks.

```text
python -m pip install -e .
python -m interview_lab doctor
python -m unittest discover -v
```

`interview-lab` and `python -m interview_lab` are equivalent after installation.
Python packaging may obtain setuptools as a build dependency; there are no
runtime dependencies. For an already provisioned offline environment:
`python -m pip install --no-build-isolation --no-deps -e .` requires setuptools
and wheel to be installed already. The unpacked module also runs directly from
the folder without installation; installed entry points are preferable for
hooks and use from other working directories.

For a non-editable packaging check, build a wheel from the project folder:

```text
python -m pip wheel --no-deps --wheel-dir dist .
```

Install the produced wheel into a separate test environment to check its entry
points and packaged runtime data. Keep build outputs and virtual environments
out of the distributable source folder. The tests above are developer checks,
not a prerequisite for users starting an interview.

### C++ prerequisite

Provide an existing **C++17 or C++20 compiler**: `clang++`, `g++`, or `cl` in a
Visual Studio Developer terminal with the matching standard library configured.
`doctor` discovers PATH executables, not an entire IDE installation. Set a
portable default with `--set compiler=g++`. For a compiler outside PATH, set
`INTERVIEW_LAB_COMPILER` to its executable path in your current shell; paths with
spaces work and are not persisted into portable configuration. No compiler is
downloaded by this project.

This build was developed on Windows with Python 3.12.10. No C++ compiler was
available on that host: C++ integration tests explicitly skip rather than claim
success. macOS/Linux behavior is implemented but not host-verified here.

## Quickstart: a real, deterministic demo

These commands need no Claude session:

```text
python -m interview_lab demo --id first-demo --language python
python -m interview_lab start first-demo --familiar yes
python -m interview_lab watch first-demo
```

Preparation validates **every part's** explicit expected fixtures against the
selected language's reference, before starting the clock. Start then creates
`.interview-lab/sessions/first-demo/candidate/solution.py`, showing only the
first prompt, public fixtures and current interface. Leave `watch` in a second
terminal, and edit that normal class file in your usual editor.
Each submission is a single source file; put helper classes/functions in that
file and use standard-library imports/includes. Sibling source files and local
headers are not copied into the sealed submission used by the session CLI.

In your command terminal:

```text
python -m interview_lab think first-demo "I will check empty and repeated operations."
python -m interview_lab test first-demo --public
python -m interview_lab done first-demo
python -m interview_lab reveal first-demo
```

`done` is the candidate's completion signal and runs the public + hidden gate.
`reveal` works only with that signal and a passing gate for unchanged saved code.
Add the newly revealed methods to your class; do not overwrite earlier behavior.
Repeat `done` and `reveal` for each part. Revealing after the final successful
gate ends the interview. A failed hidden run gives only its category and a
non-spoiling question, never the hidden input/expected output/debug stream.

To stop early and inspect your evidence:

```text
python -m interview_lab end first-demo
python -m interview_lab metrics first-demo
python -m interview_lab evidence first-demo
python -m interview_lab review first-demo
python -m interview_lab reference first-demo
```

There are **no invented scores**: `review` says `ungraded` until a genuine grader
produces and imports a validated debrief. `reference` releases solutions and all
authored parts only after ending, including expiry. Demo/familiar sessions never
enter scored trends.

For a reproducible all-parts smoke run that deliberately uses the demo reference
as the candidate (and cleans its temporary folder):

```text
python scripts\smoke.py --language python
python scripts\smoke.py --language cpp
```

On macOS/Linux use `scripts/smoke.py`. The C++ smoke exits **77** with `SKIP` if
no compiler exists, and **0** only after actually compiling/running every stage.

## Claude Code interviews

Use this folder as the Claude working project and install the package in the
Python environment available on Claude's PATH.

```text
python -m interview_lab setup-claude
python -m interview_lab setup-claude --apply
claude
```

The first setup command previews JSON without changing anything. `--apply`
merges the hook into **this project's** `.claude/settings.json` without replacing
unrelated settings. It does not change user/global Claude configuration.
Restart Claude after first adding the skill/agent directories, then invoke:

```text
/interview-lab
```

Choose your strongest language when practicing general interview performance;
choose Python deliberately when practicing Python fluency. The skill uses ten
families and meaningful twists to **author a fresh pack**, not to pretend a
finite offline template collection is an unlimited generator. It privately
authors all later requirements, fixtures, invariants, hints and both reference
files before invoking `prepare`, then presents the first stage at `start`.
Validation is per selected runtime: a Python receipt does not certify C++.

Say if a question is familiar: end it and request a fresh pack, or start with
`--familiar yes` for useful unscored practice. Family selection is available
through `select --family random` and `select --family weakest`; weakest falls
back explicitly to seeded random when there is no eligible grading evidence.
See [the families](docs/families.md) and [the interviewer skill](.claude/skills/interview-lab/SKILL.md).

### Narrate without triggering a model response

At a regular Claude terminal prompt:

```text
think: The map holds the active reservations, so a duplicate should be rejected.
think: I want to test that a failed batch leaves all prior state unchanged.
```

In **silent** mode the `UserPromptSubmit` hook timestamps and saves each entry,
then returns an intentional block with a short acknowledgement. The narration
prompt is consumed, not sent to the model. Your next ordinary message gets the
pending reasoning once, together with current clock/part/config context.
In `reactive` mode narration is forwarded for a model response instead.

The terminal `think ID "text"` command always only saves/acknowledges; it cannot
invoke Claude itself. `message ID "text"` records ordinary communication if
you're not using hooks. Avoid double-recording the same message manually.
Optional `comment_narration=true` extracts standalone `# THINK:` or `// THINK:`
comments from saved snapshots; original source is never rewritten. String
literals and ordinary comments are not stripped. See [integration details](docs/claude-integration.md).

## Configuration

```text
python -m interview_lab config
python -m interview_lab config --set language=python --set hint_policy=standard
python -m interview_lab demo --id study-demo --language python --set mode=study --set preset=extended
python -m interview_lab start study-demo --familiar yes
python -m interview_lab pause study-demo
python -m interview_lab resume study-demo
```

Settings are validated, resolved and frozen per session. Saved defaults affect
future sessions only; unknown keys, malformed values and runtime version
mismatches fail explicitly. `--set` accepts JSON values or bare strings.

| Setting | Default / choices |
|---|---|
| `language` | `python`, or `cpp` |
| `python_version` | `3.11+`, or exact minor `3.11` through `3.14`; actual executable checked |
| `python_executable` | `python`; PATH executable name, no shell fragment |
| `cpp_standard`, `compiler` | `c++17` (`c++20` supported); compiler auto-discovery or PATH name |
| `preset`, `duration_minutes` | `standard` = 45; `short` = 25; `extended` = 70; explicit duration wins |
| `session_format` | `evolving` (standard), `focused` (short), `code-and-discuss` (extended); explicit format wins |
| `family` | `random`, `weakest`, or one of the ten documented family IDs |
| `style` | `collaborative`, `neutral`, `skeptical`; respectful in every style |
| `hint_policy` | `strict`: none; `standard`: levels 1-2; `learning`: levels 1-3 |
| `docs_allowed` | `true`; an honor-system interview agreement |
| `narration` | `silent`, or `reactive` |
| `mode` | `interview` (no pause), or `study` (pause/resume, guided explanation) |
| `checkpoints` | `[15,5,1]` minutes remaining; watcher emits each once |
| `comment_narration` | `false`; opt in to standalone narration-comment extraction |
| `test_timeout`, `output_limit` | 3 seconds and 65536 bytes; timed candidate compile + execution share the time budget |

Presets are **illustrative practice formats**, not a company's stated timing.
Focused practice targets one skill in a compact staged problem; evolving practice
emphasizes adapting a working implementation; code-and-discuss adds deliberate
design/complexity discussion alongside the coded stages. The skill controls that
conversation format. A discussion does not count as passing an unimplemented
stage, and presets do not rewrite or weaken an already authored demo's fixtures.
Editor autocomplete, external AI, browser use and documentation access are
**not disabled by this tool**. Style, the no-solution rule and explanations are
skill behavior; clock/gates/reference release/hint levels are CLI-enforced.
Study never contributes to scored interview trends.

## Command map

All commands accept `--root "path to interview-lab"` **before** the command,
so they work from other working directories and folders with spaces.

| Commands | Purpose |
|---|---|
| `doctor`, `config`, `select` | Environment, defaults, deterministic family selection |
| `validate PACK --language python`, `prepare PACK --id ID` | Private schema/reference check; sealed ready session |
| `demo --id ID --language python` | Prepare the complete original offline demo |
| `start ID --familiar yes\|no`, `status [ID]`, `show ID` | Start, timing state, revealed requirements |
| `test ID --public`, `test ID --gate`, `done ID`, `reveal ID` | Test current code; signal completion; advance |
| `test ID --cases FILE` | Run your own typed JSON case array with public diagnostics; cannot grant a gate |
| `hint ID --level 1`, `pause ID`, `resume ID`, `end ID` | Hint ladder and lifecycle |
| `watch ID [--once] [--interval 1]` | Visible independent countdown, checkpoints, saved-code snapshots |
| `think ID TEXT`, `message ID TEXT`, `context [ID]` | Communication capture; consume pending narration context |
| `metrics ID`, `evidence ID`, `debrief ID FILE`, `review ID` | Objective evidence and citation-validated external grading |
| `reference ID`, `replay ID --event e000004`, `progress` | End-only spoilers, event replay, eligible trends |
| `recover ID --from-backup` | Explicit prior-revision recovery; invalidates gates and scored eligibility |
| `setup-claude [--apply] [--statusline]`, `hook`, `statusline` | Local integration; hook/statusline read JSON on stdin |

Exit codes: **0** successful command (also intentional narration consumption);
**1** failed tests or a failed `validate` result; **2** invalid request/tool error
(including preparation refused for a broken pack); **130**
interrupted. A C++ smoke with no compiler exits 77. Full public test diagnostics
are visible; detailed reference-validation/hidden reports stay under `private`.

## Evidence and debrief

The grader receives the rubric, revealed requirements, candidate messages,
narration, code snapshots and objective test/timing/hint evidence. It does **not**
receive the interviewer's rapport or subjective opinions, hidden diagnostics or
future requirements. Unknown dimensions stay unknown, not automatic zero.
Narration-only comments are identified as excluded review lines without changing
executable source.

The nine dimensions cover understanding, communication, correctness, clarity,
testing, complexity, adaptability, language fluency and time management.
Non-null scores require event IDs and verbatim quotes; a debrief also needs
three actionable improvements, a final-code review, a replay alternative and a
targeted drill. The CLI verifies schema, evidence digest and citations, **not
the truth of a model's interpretation**. Human audit is still important. It
doesn't automatically infer grades from elapsed time, hints, line changes or
silence. Progress includes only ended, unfamiliar, generated interview sessions
with trustworthy state and a genuine accepted debrief.

See [rubric](docs/rubric.md), [architecture](docs/architecture.md),
[source-to-design mapping and behavioral checklist](docs/source-to-design.md),
[typed authoring format](docs/typed-format.md) and [troubleshooting](docs/troubleshooting.md).

## Privacy, safety and zipping

**Local execution is not sandboxed.** Candidate and reference code can access
your files/network with your account's privileges. Process timeouts, bounded
captured output and child-process cleanup are reliability features, not a
security boundary. Run only code you trust; use a separate OS sandbox/container
yourself for untrusted code. Private folders are **spoiler control only**:
a local user, editor, model with file tools or candidate process can read them.

Logs and snapshots can contain personal information. The CLI makes no uploads;
using Claude sends conversation/tool-visible data according to your Claude
account and provider policies. Keep secrets out of practice. This project does
not edit global Claude settings or delete Claude's own transcripts.

To zip a clean distributable, include `interview_lab`, `tests`, `scripts`,
`demos`, `docs`, `.claude/skills`, `.claude/agents`, `README.md`, `DEVELOPMENT.md`, `pyproject.toml`
and `.gitignore`/`MANIFEST.in`. **Exclude** `.interview-lab` (all personal sessions),
`.venv`, `.claude/settings.json`, `.claude/settings.local.json`, Python caches,
`*.egg-info`, build outputs and existing zip files. `.gitignore` is future
guidance; most zip tools do **not** honor it automatically. The supplied demo
contains spoilers in its clearly labeled reference files by design. Generated
packs belong under `.interview-lab/authoring`, not tracked source.

No `.git` directory is needed or created. Later, after reviewing the zip
contents and choosing a license if desired, you can decide to create a GitHub
repository yourself.

## Sources and realism limits

Official guidance informed the practice design, not a claim of endorsement:

- [Interviewing at Jane Street](https://blog.janestreet.com/interviewing-at-jane-street/)
- [Jane Street: preparing for a software engineering interview](https://www.janestreet.com/preparing-for-a-software-engineering-interview/)
- [What a Jane Street dev interview is like](https://blog.janestreet.com/what-a-jane-street-dev-interview-is-like/)
- [Published mock interview](https://www.janestreet.com/mock-interview/)

The guidance emphasizes real-language collaborative coding, clear reasoning,
familiar data structures, multiple approaches and the journey rather than only
the final snapshot. The retired example's part-based observations are not a
universal scoring rule for arbitrarily generated problems. Later extensions
can also be useful discussion exercises; this executable tool gates *implemented*
stages on tests, while the interviewer may discuss alternatives without claiming
they were implemented. No leaked questions, algorithm-bingo tricks, claims of a
"perfect candidate", or predictions of actual hiring outcomes are included.

Claude Code integration is based on official documentation checked
**2026-09-17**; see the [versioned verification notes](docs/claude-integration.md).
The [verification record](docs/verification.md) lists actual test counts,
real command runs and capability skips.
