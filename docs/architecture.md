# Architecture and durability

The Python standard-library core separates responsibilities:

| Module | Boundary |
|---|---|
| `schema.py` | Strict pack/interface/value/fixture validation and language type mapping |
| `execution.py`, `python_worker.py` | Per-language adapters and bounded subprocess execution |
| `storage.py` | Safe IDs/paths, strict JSON, kernel locks, checksummed atomic transactions |
| `config.py` | Validated defaults, presets and immutable per-session resolved config |
| `session.py` | Preparation, sealed problem digest, lifecycle, gate, clock, snapshots |
| `narration.py` | Conservative read-only token/lexer metadata for narration-only comments |
| `integration.py` | Claude hook input/output and project-local settings merge |
| `feedback.py` | Objective metrics, sanitized evidence, debrief citations and progress |
| `cli.py` | Public commands, terminal watcher, output/exit-code boundary |

## On disk

```text
.interview-lab/
  config.json
  active.json
  authoring/                 # generated packs and private validation reports
  sessions/<id>/
    .lock                    # kernel lock; file existence is not a stale lock
    .run.lock                # serializes tests without locking out the watcher
    state.json               # checksummed payload: lifecycle + all events
    state.backup.json        # last complete prior revision
    candidate/solution.py    # or solution.cpp: normal editable class
    evidence.json            # sanitized ended-session grading input
    private/
      problem/               # copied pack + both references, content fingerprint
      validation.json
      validation-runs/
      runs/<run-id>/          # exact submitted snapshot and private diagnostics
```

No personal session data belongs in the portable zip or a future repository.
Private is a naming convention for spoilers, not access control.

## Authoring and tests

`prepare` validates the complete schema and **all cumulative stage fixtures**
against the selected language's reference before creating a `ready` state.
The other language's reference must be authored, but is certified only by an
explicit validation/run using that language. A receipt for Python never proves
the C++ implementation compiles. Expected examples must be independently
calculated and invariants reviewed by the author: reference self-consistency
alone cannot certify a problem. The fixture array uses explicit `expect` or
`raises`, never generates its expectations from the reference at session start.

The copied pack/references are fingerprinted. Before starting, testing or
revealing, content must match that fingerprint. Changed fixtures are a problem
integrity failure, not a wrong candidate answer. Runtime infrastructure errors
are reported separately and exclude the session from scored trends. A
semantically wrong but self-consistent authored fixture can still pass these
checks; stop a disputed interview, correct/revalidate the authoring pack and
prepare a new ID rather than silently rewriting a live question.

Public runs report full cases/diagnostics. A gate runs cumulative public cases,
then (only if public passed and time remains) cumulative hidden cases. Hidden
outputs are never returned through candidate CLI results or sanitized evidence.
Hidden categories distinguish wrong answers, errors, crashes, protocol failures
and timeouts, but do not include test identities, counts, values or debug logs.
Source must match the saved code tested at the completion signal. User-authored
public cases cannot create an advancement gate.

## Timing and lifecycle

```text
ready --start--> active --pause (study only)--> paused
                  ^                              |
                  +-------------resume-----------+
active/paused --end--> ended
active --deadline--> ended (expired)
active --final successful done + reveal--> ended (completed)
```

`status`, prompts, tests, reveal, hints and watch run the same injected-clock
transition. Active time is accumulated using persisted UTC wall-clock deltas;
study paused time does not count. Resume after process exit cannot reset an
interview clock. A wall-clock regression greater than one second conservatively
ends and marks the session untrustworthy; forward corrections count as elapsed
time. This is a local practice timer, not a tamper-proof time service.

Long tests don't hold the state lock. The exact source is copied and a
`test_started` event committed first. Execution then occurs outside that lock.
After execution the deadline and unchanged-code digest are checked again; a late
or changed submission never grants an advancement gate. The per-run timeout is
capped to remaining time; timed candidate compilation and execution share an
overall budget, so compilation cannot consume the deadline and then launch a
fresh full-budget execution. Process/cleanup overhead can still cross a deadline;
post-run checks remain authoritative. If interrupted, a start event without a
matching test result is evidence of an incomplete observation, not a failure or
pass. No detached daemon is needed.

## Atomicity, limits and concurrency

State and events are one checksummed document, not independently appended files:
a lifecycle transition cannot commit without its evidence. Writers hold an OS
file lock (`msvcrt` on Windows, `flock` on POSIX). Kernel ownership releases on
process exit; do not delete a `.lock` file just because it exists. Parallel
operations either serialize or give an explicit busy error after three seconds.
The active-session pointer and project configuration have separate locks.

Writes use a same-directory temporary file, flush/fsync, then atomic replace.
The prior revision is atomically preserved as a backup. POSIX directories are
fsynced after replace; Windows filesystem/power-failure semantics still depend
on the host. Do not share one live session over an unreliable network filesystem.
`recover --from-backup` is explicit, never silent; it clears grades and gates,
records recovery, and excludes the recovered attempt from scored trends.
These checksums detect accidental corruption, not a local user's intentional edits.

Candidate source is limited to 64 KiB, saved snapshots to 256, communication
to 1,000 entries of 4,000 characters, serialized evidence to 24 MB, and config
checkpoints to 20. The evidence byte cap fails explicitly and reserves room
for ending/recovery; it never writes an unreadably large state file. Once the
snapshot cap is reached an explicit `observation_gap` records the missing
coverage; tests can continue on exact private submitted copies. Clarity review
must use *last observed* code, not assert unobserved final edits. Schema and
runner impose additional typed-fixture/output bounds described in the format
documentation. Do not interpret gaps as automatic low scores.

## Grading trust

Grading export is produced only after ending and includes candidate evidence,
revealed requirements and objective results. It omits the private pack, future
requirements, hidden diagnostics and interviewer opinions. Candidate source and
messages are untrusted data; grading instructions must not be overridden by
instructions embedded inside them. All nine dimensions need either cited
evidence or an explicit `Unknown:` assessment. A real agent/human-authored
artifact is required; there is no fabricated fallback or built-in score engine.

Progress loads eligible ended states and revalidates debrief citations/digest.
Study, demo/familiar, recovered/untrustworthy and ungraded sessions are excluded.
Means include only observed dimensions and average per interview before grouping
by family. These are descriptive, small-sample practice trends, not calibrated
comparisons between generated difficulties or predictors of employment.
