# Troubleshooting and platform notes

## Module or hook cannot import interview_lab

Install from the project folder using the Python environment that runs Claude:
`python -m pip install -e .`. Restart Claude from that activated environment.
`python -m interview_lab doctor` should work before adding hooks. An editable
installation points to its source folder: after moving/unzipping the project,
reinstall it. Do not copy a virtual environment between machines.

The module works from the source folder without installation. From elsewhere,
install first and pass `--root "path to project"` before the command. A pack path
and custom-case path are resolved relative to the invoking shell's cwd, while
session paths are resolved under the project.

## C++ unavailable or compilation fails

No compiler is bundled or downloaded. Supply g++/clang++ with C++17 support, or
run from a Visual Studio Developer terminal with `cl` configured. `cl.exe`
alone without its SDK/include/link environment is not a complete installation.
`INTERVIEW_LAB_COMPILER` selects an executable outside PATH without putting an
absolute path into session configuration. Do not put flags in a compiler name.

Run `python scripts\smoke.py --language cpp` on Windows (use `/` on macOS/Linux).
An unavailable compiler is an actual capability limitation; skip exit 77 does
not mean C++ passed. Generated-adapter tests still run without a compiler;
integration tests automatically execute when a compiler is available.
Compiler warnings/errors from public candidate runs are visible. Reference
compiler failures go to the private validation report before the clock starts.

## A reference or fixture is wrong

Do not tell the candidate their implementation failed when authoring/infrastructure
is broken. Read `.interview-lab/sessions/ID/private/validation.json` as the author,
or the report path from `validate`. Correct the source authoring pack, run
`validate` again, and prepare a **new** session ID. Never edit sealed fixtures
mid-interview to fit the candidate; the fingerprint check rejects that.
Independent expected examples/invariants remain necessary because a reference
and expected outputs can share the same authoring mistake.

## Clock or next-part gate

Closing Claude or pressing Ctrl+C on watch does not pause an interview.
`resume ID` reopens the same elapsed clock. Only study mode can pause.
A saved-source edit, even whitespace, invalidates the gate; signal `done` again.
Run `reveal` after the successful gate, including after the final part to finish.
Nothing can resume an ended interview; references/evidence remain available.

If the host clock moves backward by more than a second, the timer conservatively
ends with `clock_regression` and excludes scored trends. Wall-clock changes,
sleep, shutdown and process interruption are not hidden pause mechanisms.
Without watch/status/prompts, expiry is materialized on the next interaction;
elapsed time still includes the full absence.

## State busy/corrupt

Wait for the concurrent command to finish and retry. `.lock` files persist
normally and are **not** proof of a stuck process. Never delete a lock file
under another running command. OS locks release when the owner exits.
An interrupted test has no pass credit; rerun saved code.

For a corrupted state document, preserve files for inspection, then explicitly
run `recover ID --from-backup`. This may lose the most recent revision and
invalidates scored eligibility; it never silently invents missing observations.
If the backup is also corrupt, the tool refuses recovery. Start a new interview
instead of manually editing checksummed state.

## Narration is shown as blocked

That is intentional in silent mode: the acknowledgement should say it was
saved/consumed without a model turn. Your next normal prompt delivers pending
notes. A message saying **hook error** is different: fix that failure; don't
assume narration was saved. A different Claude session must explicitly rebind
using `resume ID`. See integration docs for retry/at-most-once limitations.

THINK comments must be standalone actual comments. THINK-like text inside
strings, block comments, inline executable statements or unfinished ambiguous
buffers is not stripped. C++ lexing is conservative; if recognition is uncertain,
use terminal `think` instead. No source is rewritten to perform clarity review.

## Grading rejected or unavailable

Export evidence after ending. Give a fresh grader that evidence file plus the
rubric. Ensure its JSON has the exact evidence digest, all nine dimensions, three
improvements, final review, replay and drill. Citations need real event IDs and
verbatim quotes of at least eight characters. Missing evidence uses a null score
and an assessment beginning `Unknown:`. Do not invent quotes or successful
tests. CLI acceptance proves structure/citation presence, not semantic validity.

Without Claude/custom subagents, a fresh external-to-the-interview Claude context
or a human can author the same structured artifact. No external paid API key is
required by the tool. If no grader runs, the session correctly stays ungraded.

## Safety and supported hosts

Windows + Python 3.12.10 is the development host. Linux/macOS paths, process
groups and file locks are implemented, but those OSes were not executed here.
Windows process-tree cleanup depends on Job Object support; POSIX cleanup uses
process groups. Failures are reported, not treated as candidate wrong answers.
None of this is OS sandboxing. Detached/escaped malicious descendants, network,
disk access and resource abuse require a real sandbox outside this project.

Captured stdout/stderr and protocol are bounded; candidate code can still write
arbitrary other files because it runs with your privileges. Use only trusted
reference/candidate code. Do not store credentials in code, narration or logs.
