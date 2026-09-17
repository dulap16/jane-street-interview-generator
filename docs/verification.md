# Verification record

Verified on **2026-09-17**, Windows, Python **3.12.10**. This record describes
observed results, not a promise that untested host capabilities work.

## Final automated suite

```text
python -m unittest discover -v

Ran 187 tests
OK (skipped=15)
```

**172 passed, 15 skipped, zero failures/errors.**

Fourteen skips require a native C++ compiler, which was not present. They cover
the native demo/smoke and compiler/candidate execution cases, including wrong
answers, unexpected exceptions, crashes, malformed protocol, timeout, noisy
output, typed values and mutation. They automatically execute when a compiler
is provided. One Windows symlink-creation test skipped because the account lacks
the required OS privilege; ordinary path-traversal/ID checks passed. No OS
setting was changed to enable the skipped test.

Executed coverage includes:

- Strict typed pack/interface/fixture schemas, exact int-versus-bool checks,
  nested containers, optionals, Unicode, expected exceptions and mutation.
- Actual Python execution: passes, wrong answers, syntax/import/runtime errors,
  crashes, malformed protocol, timeout and bounded noisy output.
- Windows Job Object descendant cleanup on both normal exit and timeout.
- Generated C++ harness isolation: no hidden fixtures or future methods in
  public/current-stage drivers; serializer/code-generation checks without a
  native compiler.
- Shared compile/execution deadline budgets, including a deterministic simulated
  compiler exhausting the total budget and preventing execution launch.
- All-stage reference validation before the clock; content/part/done-bound
  advancement; edits after a pass and edits during a run; expiry before/during
  testing and at the exact reveal deadline.
- Injected-clock pause/resume/expiry/regression tests, plus an actual standalone
  watcher subprocess updating its countdown without model turns and expiring.
- Hook input/output, intentional silent narration consumption, reactive context,
  deduplication, binding/rebinding, malformed input, and project-local setup.
- Snapshots, safe comment metadata, missing observations, independent evidence,
  genuine externally authored debrief shape/citations, unknown dimensions,
  stale evidence, progress eligibility, atomic interruption and backup recovery.
- CLI entry points, paths with spaces, invalid configuration, documentation
  links and skill/grader frontmatter.

The deterministic debrief JSON inside tests is explicitly labeled synthetic
test data and stored only in temporary directories. No fabricated assessment is
shipped as an actual user's feedback.

## Real command paths exercised

```text
python -m pip install -e .
interview-lab --root PATH_TO_PROJECT config
interview-lab --root PATH_TO_PROJECT context
python -m interview_lab doctor
python -m interview_lab validate demos\ledger\pack.json --language python
python scripts\smoke.py --language python
python scripts\smoke.py --language cpp
python -m interview_lab setup-claude
python -m interview_lab setup-claude --statusline --refresh-interval 1
```

Editable installation and console/module entry points worked from a different
working directory. A wheel was also built, installed **non-editably** in a
separate clean virtual environment, and used from another directory to validate
the demo. Its packaged `cpp_runtime.hpp` was confirmed present.

The actual Python smoke completed all **three stages**, including preparation,
start, silent hook + next-prompt delivery, public/hidden gates, reveal, completion,
reference release, evidence export, and correctly ungraded/non-score-eligible
demo progress. The original demo has **19 explicit expected-output fixture cases
and 141 commands**, plus standalone reference invariant checks.

The actual C++ smoke returned **77 / SKIP**, explicitly saying runtime
verification is pending, not passed. No toolchain was downloaded or installed.

Project-local settings merge, idempotence and overwrite refusal were exercised
in temporary projects. The distributed source folder has no generated settings.
Current documented `statusLine.refreshInterval: 1` was verified as a real
configuration field and its preview shape checked, not claimed to work on an
unverified installed version.

## Not live-verified

- Native C++ compilation/execution (no available compiler).
- macOS or Linux execution; their code paths are implemented but not run on
  this Windows host.
- A paid/live Claude model turn, custom-grader execution, silent-prompt UI
  rendering, IDE integration or idle status-line rendering. Installed Claude
  Code **2.1.197** version/help were inspected. Hook protocol was exercised
  directly as real local subprocess input/output against current official docs.
- The behavioral checklist's conversational quality on a live model. It is a
  source-grounded review checklist, not an asserted stochastic model test.
- Any real hiring prediction, OS security sandbox, or distributed exactly-once
  delivery guarantee; the tool makes none of those claims.

Development virtual environments, validation reports, wheels/build outputs,
package metadata and bytecode caches were removed from the deliverable folder.
No `.git` directory, remote, commit, publication or upload was created.
