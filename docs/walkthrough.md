# Worked example: from a new problem to a finished interview

This walks one practice session start to finish: authoring a fresh problem,
opening both terminals, and using each configuration mode while the clock is
running. It assumes [one-time setup](../README.md#one-time-setup) is already
done. Nothing here is a real interview question; the skill authors an
original pack per session (see [authoring.md](../.claude/skills/interview-lab/authoring.md)).

## The two terminals

| Terminal | Role |
|---|---|
| **A — Claude** | Where you talk to Claude, edit nothing directly, and get the problem, hints, tests and feedback. |
| **B — Watch** | A plain countdown: `python -m interview_lab watch SESSION_ID`. It reads saved code and prints checkpoints independently of Claude; it does not stop the clock if you close it. |

You'll also have your editor open on the one candidate file Claude names.

## 1. Open terminal A and ask for a session

```bash
source .venv/bin/activate
claude
```

```text
/interview-lab
```

Then describe what you want in plain language, for example:

> Start a fresh 45-minute Python interview, collaborative style, standard
> hints, focused on graph problems.

Claude reads `context`/`config`/`doctor` first, then, behind the scenes, does
the authoring work you don't have to type yourself:

```text
python -m interview_lab select --family graph --seed <chosen-seed>
# writes pack.json + reference.py + reference.cpp somewhere private
python -m interview_lab validate PATH_TO_PACK --language python
python -m interview_lab prepare PATH_TO_PACK --id practice-04 --set language=python
```

`validate` and `prepare` run every part's fixtures against the reference
*before* your clock starts — a broken fixture is Claude's problem to fix, not
yours to debug. Claude then asks the one question the tool can't answer for
you:

> Have you seen a problem like this before?

Answer honestly. `--familiar no` is what makes the attempt eligible for
scored practice trends later; `--familiar yes` is still useful practice, just
not scored.

```text
python -m interview_lab start practice-04 --familiar no
```

Claude now tells you the candidate file path (e.g.
`.interview-lab/sessions/practice-04/candidate/solution.py`) and the exact
watch command for terminal B, and shows you the first stage's prompt.

## 2. Open terminal B

```bash
source .venv/bin/activate
python -m interview_lab watch practice-04
```

Leave it running. It prints the countdown and fires checkpoints at the
configured remaining-minute marks (`[15, 5, 1]` by default); Claude isn't
guaranteed to say anything on its own when one fires.

## 3. The modes you're working in

Everything below is fixed for the whole session once it's prepared — change
it by asking for it *before* you say "start", not mid-interview.

| Setting | Choices | What it actually changes |
|---|---|---|
| `mode` | `interview` (default), `study` | Interview can't pause and always counts toward scored trends when eligible. Study can pause/resume and gets guided explanation, but never scores. |
| `session_format` | `evolving` (default), `focused`, `code-and-discuss` | Shapes how the interviewer paces stages — adapting a working solution, one concentrated skill, or coded stages plus deliberate design/complexity discussion. You don't invoke this; it just changes what Claude asks. |
| `style` | `collaborative` (default), `neutral`, `skeptical` | The interviewer's conversational tone. Same rules and tests either way. |
| `hint_policy` | `standard` (default, levels 1–2), `strict` (none), `learning` (levels 1–3) | Caps how far `hint --level N` is allowed to go. |
| `narration` | `silent` (default), `reactive` | What happens when you type `think: ...` (below). |

Ask for any of these when you request the session, e.g. "use study mode",
"make this a focused 25-minute problem", "skeptical style", "learning
hints", "reactive narration".

## 4. Using each mode once you're in the interview

**Discussing and planning.** Just talk normally in terminal A — clarify the
contract, propose a design, agree on a plan. Claude won't write or edit your
code.

**Narration (`think:`).** At an ordinary prompt:

```text
think: I'll key the map by id since batch lookups need O(1) access.
```

- In **silent** mode (default) this is saved with a timestamp and
  acknowledged without a reply; your next real message delivers the
  accumulated reasoning as context. Useful for thinking out loud without
  breaking your own flow.
- In **reactive** mode the same line gets an actual response, so use it when
  you want Claude to push back on the reasoning immediately.
- `message: ...` records ordinary narration the same way if you're relying on
  it instead of a configured hook.

**Writing and testing code.** Edit and save the named file in your editor.
Then, in terminal A:

- "Show me the public tests" → `test practice-04 --public`
- "I'm done with this part" → `done practice-04`, which runs the full gate
  (public + hidden) against your last **saved** file
- Once the gate passes, Claude reveals the next stage — never before, and
  never by inspecting your code instead of running it.
- A failed hidden case gets you a category and a non-spoiling question, never
  the hidden input/expected output.

**Hints.** Ask directly: "Can I get a level 1 hint on the top-up logic?" →
`hint practice-04 --level 1`. Blocked levels stay blocked under `strict`;
asking doesn't get you an improvised equivalent instead.

**Study mode only.** "Pause here" / "Resume" → `pause practice-04` /
`resume practice-04`. Interview-mode sessions can't do this — end the session
if you need to stop.

**Checking where you stand.** "What's my status?" → `status practice-04`,
independent of whatever terminal B is showing.

## 5. Ending and getting feedback

> End the interview and give me feedback.

Claude runs `end practice-04`, then `evidence practice-04` to produce a
sanitized, digest-bound evidence file (revealed prompts and sanitized events
only — no private prompts or hidden diagnostics). It hands that file plus
`docs/rubric.md` to the `interview-grader` subagent in a **fresh context**,
imports the returned assessment with `debrief practice-04 FILE`, and then
gives you `review practice-04` (the actual feedback), `metrics practice-04`
(objective numbers), and can pull up `replay practice-04 --event eNNNNNN` for
a specific turning point. `reference practice-04` only unlocks now — full
solutions and all authored parts, not before.

None of this is a hiring prediction. `progress` only ever counts ended,
non-familiar, generated interview sessions with a genuine accepted debrief —
study runs and familiar demos are practice, not trend data.

## See also

- [README quickstart](../README.md#start-practicing-each-time) — the short version.
- [Configuration table and command map](../DEVELOPMENT.md#configuration) — every setting and every manual command, if you want to drive the CLI yourself instead of through Claude.
- [Narration/hook internals](claude-integration.md) — what the `think:` hook actually does under the hood.
- [Families](families.md) — the ten problem families the skill authors from.
