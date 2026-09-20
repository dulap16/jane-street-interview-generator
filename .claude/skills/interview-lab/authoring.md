# Private pack authoring

This guide is for the author/interviewer, not a live candidate's task sheet.
Keep authoring files, whole packs, references, hidden fixtures, future prompts,
and all unreleased hints out of candidate-facing context. Local privacy is a
workflow convention, not a filesystem security guarantee.

## Interview startup example

Terminal 1 — Claude (this one, or a new claude session in this folder)
source .venv312/bin/activate
claude
Then run /interview-lab and tell it what you want, e.g.:

▎ Start a fresh 45-minute Python interview. I'd like to try the read-budget-cache problem again as a genuine first attempt — I've only seen it while testing the tool, not actually solved it.

Since I deleted practice-01/practice-02, I (via the skill) will prepare and start a new session id against the existing .interview-lab/authoring/read-budget-cache/pack.json, ask you to confirm familiarity honestly, and give you the solution-file path plus the exact session-specific watch command.

Terminal 2 — the timer
Open a second terminal in the same folder:
source .venv312/bin/activate
python -m interview_lab watch <session-id>
<session-id> is whatever id gets picked in terminal 1 (e.g. practice-03) — leave this running for the live countdown; Ctrl+C only stops the display, not the clock.

Then edit the solution file in your editor, save, and tell Claude "I'm done with this part" when ready to test.

## Design a genuinely different task

Use the chosen family and seed to propose a new state model or grammar, a small
initial API, and two coherent extensions. [`docs/families.md`](../../../docs/families.md)
provides ten design palettes with exact examples; it is not a bank of secret
interview questions. Do not scrape interview reports or reproduce public retired
questions as if they were new. Change consequential semantics, not just names.

Record `origin.kind: "generated"` and the actual seed text. A seed records a
recipe; generation is not necessarily deterministic across model versions.
The offline CLI can select a family/seed and run supplied packs; it does not
provide infinite novel problems without an author or model. Repeated seeds,
renamed demos, and similar-looking generated exercises still need an honest
familiarity check. A duplicate check or fingerprint is evidence of local
similarity, not proof that the candidate has never encountered the idea.

The first part must be independently solvable with familiar collections and
clear examples. State success/failure semantics, ordering, ties, boundary
inclusivity, legal empty inputs, error categories, and mutation behavior.
Choose one modest new behavior per extension. Later cases can exercise earlier
methods, but must not silently change their contract. If a change is intentional,
make the new rule explicit and ensure the earlier fixtures remain coherent.
Reward reasonable adaptation, not clairvoyance or an abstract framework built
for a future prompt the candidate has not seen.

Favor an initial design where a single obvious collection is not simply
sufficient throughout. If a plain dict/list satisfies the first part *and*
every later extension without ever being reconsidered, the exercise likely has
a shallow ceiling regardless of part count: each "extension" ends up being one
more validation branch on the same representation rather than a real design
decision. Prefer a first part whose reasonable solutions already trade off
against each other (for example, needing both fast lookup and an ordering or
eviction property together), and at least one extension that plausibly forces
revisiting or augmenting that structure, not just adding another guarded
method beside it.

Do not multiply the same trivial validation rule across many methods as if
that were additional test coverage. A single one-line guard (an empty string,
a non-positive count) repeated verbatim across four or five methods tests
whether the candidate remembered to paste it everywhere, not engineering
judgment. State such a rule once, illustrate it clearly for the method it
first matters on, and spend the rest of the public/hidden fixture budget on
rules that exercise real behavior, ordering, or interaction between methods.

Design for a clear, useful abstraction and productive discussion of tradeoffs,
not a concealed optimal trick. Provide room for thoughtful clarification and
more than one reasonable plan. A reasonable plan executed well is preferable
to a pack that pressures candidates into repeatedly chasing a perfect design.
Include discussion opportunities about uncertainty, confidence, and the
reason for a pivot; do not encode one favored explanation as the only correct
answer or require extroverted narration.

Use the configured `session_format` to shape a newly authored pack and its
conversation: `focused` concentrates on one skill in compact stages, `evolving`
emphasizes adaptation, and `code-and-discuss` pairs coded stages with deliberate
design/complexity discussion. This does not authorize changing a prepared pack's
expectations or rewriting demo fixtures. Duration and format can be overridden
independently of preset defaults.

Three parts are the demo format, not a universal interview norm or a fixed
grading ladder. For generated packs use however many nonempty stages suit the
practice design and validator. A final extension may be a discussion goal, but
do not encode an untestable discussion-only requirement as a fake passing
fixture. Record discussion as evidence; never fabricate executable completion.
The test-pass progression is our local practice mechanism, not Jane Street's
published process or hiring rubric. Open-ended exercises are not designed on
the assumption that every candidate must finish everything or produce globally
perfect, bug-free code. A disclosed late extension can support a useful design
discussion without being implemented; that discussion does not grant a pass or
permission to reveal another stage. Keep concrete expected fixtures exact while
separating stage execution results from the overall practice assessment.

The public [interviewing overview](https://blog.janestreet.com/interviewing-at-jane-street/)
supports this collaborative, tradeoff-aware design. Any bug-free milestones in
the [retired memoization example](https://blog.janestreet.com/what-a-jane-street-dev-interview-is-like/)
are scoped to that example, not a universal completion requirement. The
[mock-interview page](https://www.janestreet.com/mock-interview/) is a landing-page
source here, not a claim that its video transcript was analyzed.

## Exact pack contract

A pack directory contains `pack.json`, `reference.py`, and `reference.cpp`.
Use safe basenames for reference filenames. The class is always `Solution`.
Do not add commentary keys, solutions, grading labels, or undocumented fields.

The top-level keys are exactly:

| Key | Value |
| --- | --- |
| `schema` | `1` |
| `id` | Lowercase ASCII slug |
| `title` | Nonempty descriptive string |
| `family` | `cache`, `simulation`, `parser`, `graph`, `stream`, `scheduling`, `orderbook`, `spatial`, `filesystem`, or `workflow` |
| `origin` | `{"kind":"generated","seed":"actual-seed"}`; use `demo` only for familiar demos |
| `interface` | Constructor parameters and method definitions below |
| `parts` | Ordered nonempty stage objects below |
| `references` | `{"python":"reference.py","cpp":"reference.cpp"}` |

`interface.constructor` is an ordered parameter array. Each method in
`interface.methods` is `{"name": NAME, "params": [...], "returns": TYPE,
"since": STAGE}` with a 1-based stage number. Names must be compatible with
both languages and distinct within their scope; avoid language keywords.
A parameter is `{"name": NAME, "type": TYPE, "mode": "in"}`. Omitted `mode`
defaults to `in`; use `inout` only when caller-visible mutation is intentional.
Only method parameters may be `inout`; constructor parameters cannot be.

Types are recursive:

- `"int"` is signed int64. JSON `true` is not an integer; reject Python's
  bool-as-int equivalence in validation and fixture tooling.
- `"bool"` and `"str"` are distinct primitives.
- `"void"` is legal **only as a method return type**; its expected value is null.
- `{"list": T}`, `{"optional": T}`, and `{"map": T}` compose these types.
  Maps always have string keys; optional values use JSON null when absent.
  There are no float, tuple, set, arbitrary-object, or user-defined-record types.

Python uses native `int`, `bool`, `str`, `list`, `dict`, and `None`.
C++ uses `std::int64_t`, `bool`, `std::string`, `std::vector<T>`,
`std::optional<T>`, and `std::map<std::string,T>`. An `inout` C++ parameter
requires a reference; all methods must be callable with the declared signature.
Avoid defining `main`, doing input/output, or importing third-party libraries.
Every reference implements **all** stages; the stage adapter exposes only the
cumulative declared API. Do not introduce private-method calls into fixtures.

Each stage has exactly:

```json
{
  "title": "An independently understandable step",
  "prompt": "Complete current-stage candidate contract, without later requirements.",
  "public": [],
  "hidden": [],
  "invariants": ["A precise state property."],
  "hints": ["An observation.", "A representation suggestion.", "A concrete approach."],
  "failure_question": "A question about the current contract, without a hidden counterexample?"
}
```

The empty arrays above are placeholders: **both public and hidden must contain
at least one real case**. Invariants are a nonempty array of nonempty strings;
hints are exactly three nonempty strings. A textual invariant is not
automatically an executable property test.

A case has `id`, positional `constructor` arguments, and ordered `commands`.
Use globally unique slug IDs. A command has `method`, positional `args`, and
exactly one of `expect` or `raises`; it may also have `after` for declared
`inout` arguments. For example, in a separately declared list-filter task:

```json
{
  "id": "filter-example",
  "constructor": [],
  "commands": [
    {
      "method": "remove_negative",
      "args": [[3, -1, 0]],
      "expect": 1,
      "after": {"values": [3, 0]}
    }
  ]
}
```

Here the method must declare an `inout` parameter named `values` of type
`{"list":"int"}` and return `"int"`. `expect` is the return value, not the
mutated argument; `after` explicitly checks the latter. Specify whether errors
leave an inout argument unchanged and test that with `after` as needed.
An optional-map query might instead use `"expect": null` or
`"expect": {"blue": 3}`. A failing command might use
`"raises": "invalid_argument"` and no `expect`.

Supported error categories:

| Pack category | Python | C++ |
| --- | --- | --- |
| `invalid_argument` | `ValueError` | `std::invalid_argument` |
| `out_of_range` | `KeyError` or `IndexError` | `std::out_of_range` |
| `runtime_error` | `RuntimeError` | `std::runtime_error` |

Error-message text is not the cross-language contract. Constructor arguments
must be valid fixture setup: the case schema has no constructor-raises field.
If the prompt specifies invalid constructors, cover them in separate reference
tests, or redesign the public API so the validator can exercise the behavior.

## Derive expectations independently

1. Write small input traces and compute **literal** expected results by hand.
   Include observations after both success and failure. Do not run a reference,
   capture its output, and call that the expected oracle.
2. For each rule, include a public illustration and/or hidden discriminating
   case. Hidden cases can combine revealed rules; they cannot add surprise
   requirements. Include empty, singleton, boundary, duplicate, repeated-call,
   tie, unknown-name, and overflow-relevant cases when meaningful.
3. Exercise cumulative behavior after the extension. Atomic failure tests must
   observe all state that an incorrect prefix could have changed. A return of
   `false` alone does not prove rollback.
4. Name invariants precisely: conservation, uniqueness, monotonicity, isolation,
   determinism, idempotence, or round-trip properties, with the conditions under
   which each holds. Turn them into observed fixture sequences or a separate
   small independent property/model test. Do not claim a prose invariant is
   checked when no test enforces it.
5. Implement straightforward Python and C++ references separately enough to
   catch representation errors. Prefer bounded subtraction to overflowing
   accumulations; do not rely on Python's unlimited integers to excuse C++
   undefined behavior. Explain suitable complexity without adding arbitrary
   performance requirements that the prompt does not state.
6. Validate the selected language, and validate the other reference when its
   runtime already exists. Do not install a compiler or claim skipped execution
   passed. Missing toolchains should be reported before candidate time begins.

```console
python -m interview_lab validate PACK --language python
python -m interview_lab validate PACK --language cpp --compiler g++
python -m interview_lab prepare PACK --id original-01 --set language=python
```

Preparation privately runs the selected reference against all expected fixtures
before the clock. A schema failure, reference mismatch, ambiguous rule,
unavailable runtime, or broken fixture is an authoring/setup defect. Correct it
before starting. Do not lower a candidate's score, leak hidden inputs, or revise
expectations merely to agree with a favorite implementation.

## Privacy and review checklist

- First prompt stands alone; later methods, twists, hints, and tests stay private.
- No copied real interview question or assertion that this mirrors a secret
  hiring rubric.
- Provenance, seed, and familiarity are honest.
- All branches have explicit typed expectations; every stage is nonempty.
- Public diagnostics can be shown fully; hidden diagnostics have a useful
  authored, nonspoiling failure question.
- Candidate workspace starts with the CLI-generated unsolved template only.
- Selected reference preflight is successful before timing begins.
- Stored references remain unavailable to the candidate until the session ends,
  even in study mode or after they ask for an explanation.
