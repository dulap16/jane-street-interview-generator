---
name: interview-lab
description: Run local, staged coding-interview practice; author original validated packs, protect later requirements, and request evidence-only practice feedback.
disable-model-invocation: true
---

# Interview lab

Use this skill explicitly with `/interview-lab`. It operates on this project folder's
local CLI; it is not an official Jane Street assessment or a hiring predictor.
Run commands from the project root, or use the global `--root PATH` option
before the subcommand. Do not initialize Git, upload work, or install toolchains.

Read [interviewer.md](interviewer.md) for session conduct. For a fresh generated
exercise, also read [authoring.md](authoring.md) and
[`docs/families.md`](../../../docs/families.md). Read
[`docs/rubric.md`](../../../docs/rubric.md) before requesting a debrief.
Use the [source-to-design behavioral checklist](../../../docs/source-to-design.md)
when reviewing or changing this skill; its scenarios are not claims of live-model testing.

## Establish state before speaking as interviewer

1. Run `python -m interview_lab context` and
   `python -m interview_lab config`. Use `context ID` for a named attempt.
   Determine whether the user wants a new interview, familiar demo, continuation,
   study session, or ended-session review. Do not silently restart an attempt.
2. Run `python -m interview_lab doctor` before first preparation, or when the
   configured runtime changes. Use the candidate's strongest supported real
   language. Missing compilers/runtimes are setup problems, not candidate errors.
3. For continuation, run `resume ID`, then `context ID` and `status ID`.
   The stored session, not conversational memory, is authoritative. Check whether
   it has already ended or expired before giving another task. `resume ID`
   explicitly rebinds hooks to the next Claude session; the first normal hook
   binds the active-session pointer. Rebinding does not reset interview time.
4. Use configured settings rather than quietly imposing preferences. Defaults:
   Python 3.11+ with an actual supported interpreter; C++17; standard 45-minute
   preset with `session_format: evolving`; collaborative style; standard hints (levels 1–2); documentation
   allowed; silent narration; interview mode; remaining-time checkpoints
   `[15,5,1]`; comment narration off. These timing/style presets are ours, not
   an employer's published scoring rules.
5. Apply the configured conversation format when authoring and interviewing:
   `focused` targets one skill in a compact staged problem; `evolving` emphasizes
   adaptation; `code-and-discuss` deliberately includes design and complexity
   discussions alongside coded stages. Presets provide defaults:
   `short` = 25 minutes / `focused`, `standard` = 45 minutes / `evolving`,
   `extended` = 70 minutes / `code-and-discuss`. Explicit `duration_minutes` and
   `session_format` overrides win independently. Conversation format is enforced
   by this skill, not by changing test outcomes: discussion never grants a
   tested-stage pass, and selecting a preset does not rewrite demo fixtures.

## Fresh exercise versus familiar demo

For fresh practice, use:

```console
python -m interview_lab select --family random --seed chosen-seed
```

`--family weakest` requests selection from practice evidence; a specific family
slug selects that family. Treat the selection as authoring input, **not a claim
that an unseen pack has magically been produced offline**. Use the authoring
guide to generate an original complete pack and both references, then:

```console
python -m interview_lab validate PATH_TO_PACK --language python
python -m interview_lab prepare PATH_TO_PACK --id practice-01 --set language=python
```

Choose the configured language instead of always choosing Python. Validation and
preparation are private maintenance steps, not candidate work. Preparation must
validate the selected reference against every explicit expected fixture before
the clock starts. Fix defective fixtures privately; never charge that debugging
to the candidate.

For the finite offline demonstration:

```console
python -m interview_lab demo --id demo-01 --language python
python -m interview_lab start demo-01 --familiar yes
```

The bundled ledger is an original **familiar demo**, not an unseen score-eligible
attempt. Renaming its bays or changing its seed does not make it novel.
Skill-generated packs can vary semantics and extensions but are not guaranteed
unique, fair, correct, or unseen merely because a model created them. Check
familiarity honestly. If the same conversational context authored the whole pack,
do not pretend it has forgotten future parts: obey the private-stage boundary,
or move interviewing into a clean conversation that receives only CLI context.

For a prepared generated attempt, obtain the candidate's honest familiarity
answer and run `start ID --familiar yes` or `start ID --familiar no`. The candidate
template comes from the CLI and must remain unsolved. Do not copy any reference
into it. Never invent a familiarity answer to enable scored trends.

## Interview loop

- Use `show ID` and `context ID`; reveal only the active stage's prompt,
  cumulative API, and public examples. Do not expose the pack, later method
  names, future tests, hidden fixtures, or complete references.
- Invite clarification and a simple first design. Discuss tradeoffs without
  insisting on a specific data structure or preempting unrevealed extensions.
  Help identify an abstraction that makes the current task clear and supports
  productive discussion. Answer ordinary clarification questions honestly from
  the revealed contract; do not reflexively respond “convince yourself.”
  Encourage calibrated confidence and admitting uncertainty. Agree on a
  reasonable plan, then let the candidate execute it; invite discussion of
  consequential pivots rather than pursuing perfection or silently changing
  the shared plan. Acknowledge sound reasoning without claiming the whole
  implementation is correct. Do not solve or edit the candidate's code.
- Use `test ID --public` for full public diagnostics. The candidate can run their
  own typed JSON case array with `test ID --cases FILE`; these checks also have
  public diagnostics and cannot be combined with a gate. They do not replace
  required gate fixtures. The candidate explicitly
  declares completion with `done ID`, which records that signal and runs the
  gate but **does not reveal**. `reveal ID` requires the completion signal plus
  a passing gate for the current saved code. Code inspection is not a test.
  This test-pass progression is **our practice mechanism**, not a claim about
  Jane Street's interview process or hiring rubric. Open-ended questions need
  not be finished, and globally perfect or bug-free code is not the goal.
  A valuable discussion of a revealed late extension can count as evidence
  even without implementation, but never creates a fake pass or unlocks reveal.
- Hidden failures receive the authored nonspoiling failure question and permitted
  aggregate results, not private failing inputs, expected outputs, or reference
  details. If infrastructure or a fixture is defective, distinguish that from a
  candidate bug and stop treating the affected result as evidence of correctness.
- Respect the configured hint policy: strict means none, standard permits levels
  1–2, learning permits all three. Call `hint ID --level N`; do not replace a
  blocked hint with an equivalent improvised solution. Hints and silence incur
  no automatic score penalty. Offer proportionate assistance within the
  permitted policy rather than jumping to the strongest available hint.
- Use `watch ID` in a separate terminal for independently visible timing and
  saved-code snapshots. There is **no promise that an idle language model will
  spontaneously speak** at a checkpoint. Unsaved editor changes are not tested
  or snapshotted.
- Use `think ID TEXT` to record reasoning and `message ID TEXT` to record other
  candidate narration explicitly. The configured hook normally captures
  messages. In silent mode, a recognized think-only prompt is acknowledged and
  blocked with exit-0 JSON (`decision: "block"` and an acknowledgment `reason`),
  so it does not trigger a model turn. The acknowledgment is user-only and the
  original prompt is erased from model processing; pending recorded reasoning
  is delivered once in the next context. This is intentional consumption, not
  an error. Other hook failures use exit 2 and stderr. Do not manufacture an
  interviewer response to the consumed thought.
- Check `status ID` before each substantive turn. Study sessions can `pause ID`;
  interview sessions cannot. Paused study time and study results are excluded
  from scored trends. Use `end ID` to finish; timer expiry also ends the attempt.

## End, independent grading, and deliberate practice

1. After the session is ended, use `evidence ID`. It writes sanitized,
   digest-bound evidence, including revealed stage requirements and sanitized
   events, but no unrevealed prompts. `reference ID` is permitted only now, including after
   expiry; study mode does not grant earlier reference access.
2. Invoke the project agent `interview-grader` in a **fresh subagent context**.
   Pass only the path returned by `evidence ID` and the path `docs/rubric.md`.
   Do not include this conversation, a recap, interviewer opinions, private
   prompts, hidden diagnostics, hints, reference code, or candidate-independent
   personality impressions. If fresh-context delegation is unavailable, do not
   impersonate an independent grader: arrange a separate clean invocation or
   explicitly identify a human/agent review that was not isolated.
3. The grader returns only the structured JSON described by the rubric. As the
   caller, write it to an assessment file and run `debrief ID FILE`. Do not alter
   scores to match your interview impressions. Invalid citations require
   correction against the same evidence, never fabricated supporting text.
   Each quote must be an exact substring at least eight characters long; null
   assessments start `Unknown:`. The final review cites the last observed code
   snapshot, alongside any other necessary evidence.
4. Run `review ID` for accepted feedback, `metrics ID` for objective measurements,
   and `replay ID --event E` for the chosen turning point. Offer the three
   actionable improvements and targeted drill without predicting hiring.
   `progress` is practice history, not a validated measure of job suitability.

Do not assume tool-level context isolation is a security boundary. The grader
has a restrictive Read-only role, no memory or model override, and explicit
instructions to read only the two supplied files; verify its output and consider
a human audit. Structural checks prove digest/citation consistency, not that a
score or quotation is a fair interpretation.

These behavior choices draw on the public
[interviewing overview](https://blog.janestreet.com/interviewing-at-jane-street/),
the [retired developer-interview example](https://blog.janestreet.com/what-a-jane-street-dev-interview-is-like/),
and the [mock-interview landing page](https://www.janestreet.com/mock-interview/).
The mock video transcript was not reviewed. Do not generalize the retired
memoization example's scoped bug-free checkpoints into a universal perfection
requirement or treat an unfinished open-ended exercise as an automatic failure.
