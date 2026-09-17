# Typed pack format and execution

Schema version 1 describes a normal `Solution` class in Python or C++. Each case
constructs one instance, then executes its commands in order. Cases have separate
instances. Later parts expose every method whose `since` is at most that part's
1-based number. A suite runs in one process, so module globals are not reset
between cases.

## Complete small pack

```json
{
  "schema": 1,
  "id": "typed-accumulator",
  "title": "A stateful accumulator",
  "family": "stream",
  "origin": {"kind": "demo", "seed": "example"},
  "interface": {
    "constructor": [{"name": "start", "type": "int"}],
    "methods": [
      {
        "name": "add",
        "params": [{"name": "delta", "type": "int"}],
        "returns": "int",
        "since": 1
      },
      {
        "name": "append",
        "params": [
          {"name": "values", "type": {"list": "int"}, "mode": "inout"},
          {"name": "fail", "type": "bool"}
        ],
        "returns": "void",
        "since": 1
      }
    ]
  },
  "parts": [
    {
      "title": "State and mutation",
      "prompt": "Implement add. append appends the current total, then throws invalid_argument if fail is true.",
      "public": [
        {
          "id": "public-state",
          "constructor": [4],
          "commands": [
            {"method": "add", "args": [3], "expect": 7},
            {"method": "append", "args": [[], false], "expect": null, "after": {"values": [7]}},
            {"method": "append", "args": [[1], true], "raises": "invalid_argument", "after": {"values": [1, 7]}}
          ]
        }
      ],
      "hidden": [
        {
          "id": "hidden-negative",
          "constructor": [0],
          "commands": [
            {"method": "add", "args": [-2], "expect": -2},
            {"method": "add", "args": [2], "expect": 0}
          ]
        }
      ],
      "invariants": ["The total changes only when add is called."],
      "hints": [
        "Store the total on the instance.",
        "Update before returning.",
        "Mutation can happen before an exception."
      ],
      "failure_question": "Did the value, state, or mutation diverge first?"
    }
  ],
  "references": {"python": "reference.py", "cpp": "reference.cpp"}
}
```

Only the displayed keys are accepted, with `mode` and command `after` optional.
Every command must contain exactly one of `expect` and `raises`; `expect: null`
is still an explicit expectation. Every part requires nonempty `public` and
`hidden` lists, at least one nonempty invariant, exactly three nonempty hints,
and a nonempty title, prompt, and failure question. The pack title is nonempty.
`origin.seed` is a string (including the empty string); `origin.kind` is
`generated` or `demo`.

Supported families: `cache`, `simulation`, `parser`, `graph`, `stream`,
`scheduling`, `orderbook`, `spatial`, `filesystem`, and `workflow`.

Pack and case IDs contain 1–64 lowercase ASCII letters/digits in nonempty
hyphen-separated segments, such as `cache-17`. Case IDs are unique across the
entire pack, including parts and both visibility lists. Method and parameter
names are unique within their scopes, start with an ASCII letter, contain only
ASCII letters/digits/underscores, and are at most 64 characters. Python/C++
keywords, `Solution`, `self`, `cls`, soft keywords `match`/`case`/`type`, leading
underscores, and double underscores are rejected for cross-language safety.
Every method has a valid `since` and must be exercised somewhere in the pack.

References are simple relative filenames ending in `.py` or `.cpp`, respectively.
Default names are `reference.py` and `reference.cpp`; other safe filenames are
accepted. Directory separators, traversal, leading dots, drive/stream syntax,
trailing dots, and Windows device filenames such as `CON.py` are rejected.
Schema validation does not open reference files. The caller chooses the language
and resolves only that language's source.

## Types and exact values

| Descriptor | Python type | C++ type | JSON representation |
| --- | --- | --- | --- |
| `"int"` | `int` | `std::int64_t` | Exact signed 64-bit integer |
| `"bool"` | `bool` | `bool` | `true` or `false` |
| `"str"` | `str` | `std::string` | Unicode scalar string |
| `"void"` | `None` | `void` | `null`, only at the return root |
| `{"list": T}` | `list[T]` | `std::vector<T>` | Array |
| `{"optional": T}` | `T \| None` | `std::optional<T>` | `null` or a value of T |
| `{"map": T}` | `dict[str, T]` | `std::map<std::string, T>` | Object with string keys |

Descriptors nest, for example `{"map":{"list":{"optional":"str"}}}`. `void`
cannot be a parameter or nested type. Optional nesting is permitted; the JSON
representation does not distinguish different levels of disengaged optionals.

No coercion occurs: Python `True`, `1.0`, and `"1"` are not integer `1`.
Container subclasses, tuples, byte strings, NaN, and infinity are not valid
typed values. Strings permit embedded NUL, quotes, escapes, and supplementary
Unicode characters, but not surrogate code points. C++ strings are UTF-8 byte
strings; malformed UTF-8 results are wrong answers. List order matters; map
insertion order does not. Comparison validates types recursively before
comparing values.

Python methods are ordinary instance methods, with the implicit `self` omitted
from the descriptor. C++ methods and constructors are public. Input parameters
may be passed by value or const reference; `inout` parameters use non-const
references. C++ return types must match **exactly**, checked by `static_assert`;
implicit conversions (including `bool` to integer), references, and unrelated
integer typedefs do not bypass this requirement.

`mode` defaults to `in`. Constructors do not support `inout`. Command `after`
contains only names of `inout` arguments; it may specify any subset. The runner
captures all inout values, including when a call throws. Expected `after` values
are checked even when an exception was expected. Every captured mutation must
remain correctly typed. In Python, inout mutation is useful for mutable lists
and dictionaries; rebinding a local scalar parameter cannot change the caller's
argument. Inputs and recorded outcomes are copied so later calls do not mutate
earlier evidence.

### Exceptions

| Fixture `raises` | Python | C++ |
| --- | --- | --- |
| `invalid_argument` | `ValueError` and subclasses | `std::invalid_argument` and subclasses |
| `out_of_range` | `IndexError`/`KeyError` and subclasses | `std::out_of_range` and subclasses |
| `runtime_error` | `RuntimeError` and subclasses | `std::runtime_error` and subclasses |

Messages are diagnostic only and are not part of expected-exception comparison.
A missing or differently categorized expected exception is a wrong answer.
An exception when a value was expected is a runtime error. Constructor/import
exceptions are runtime errors; a constructor failure skips that case's commands.
Unexpected exceptions do not prevent later cases from being attempted.

## Python APIs

```python
from pathlib import Path
from interview_lab.schema import validate_pack, interface_for, validate_cases
from interview_lab.execution import run_suite

# pack is an already-parsed JSON object.
validate_pack(pack)
interface = interface_for(pack, 1)
cases = pack["parts"][0]["public"]
validate_cases(interface, cases)
result = run_suite(
    "python",
    Path("answer.py"),
    interface,
    cases,
    Path(".interview-work"),
    python_executable="python",
    timeout=3.0,
    output_limit=65536,
)
assert result["status"] in {"passed", "wrong_answer", "compile_error",
    "runtime_error", "crash", "protocol_error", "timeout", "output_limit",
    "infrastructure_error"}
```

`SchemaError` derives from `ValueError`, and includes the invalid field's
location. `validate_pack` and `validate_cases` return `None` on success and
never mutate their input. `interface_for` validates the pack and returns a deep
copy of the cumulative interface. `cpp_type` and `python_type` render validated
descriptors. The JSON-loading caller must reject duplicate raw JSON object keys
before converting them to a dict; duplicate keys cannot be recovered from an
already-parsed Python dict.

The full execution signature is:

```python
run_suite(
    language: str, source: Path, interface: dict, cases: list, work_dir: Path,
    *, python_executable: str = "python", compiler: str | None = None,
    cpp_standard: str = "c++17", timeout: float = 3.0,
    output_limit: int = 65536,
    total_timeout: float | None = None,
) -> dict
```

Languages are `python` and `cpp`; standards are `c++17` and `c++20`. `compiler`
is a single executable name/path, not a shell command or a flags string.
Autodetection checks `g++`, `clang++`, then `cl` on PATH. MSVC needs a configured
Developer Prompt environment. Paths containing spaces are preserved as argv
elements. No compiler or JSON dependency is installed or downloaded.
`timeout` remains an independent per-phase limit when `total_timeout` is omitted.
An optional finite positive `total_timeout` adds one overall monotonic budget
starting at entry to `run_suite`, including fixture preparation, compilation,
and execution. Each subprocess receives the smaller of `timeout` and the
remaining total budget. If compilation exhausts that budget, execution is **not
launched** and the result is `timeout`. Successful subprocess exits that have
exhausted the overall budget are also reported as timeouts. Mandatory process
termination, pipe draining, and owned-directory cleanup may finish after the
deadline; the runner never abandons cleanup to return earlier.

Interview callers can pass `total_timeout=min(test_timeout, remaining_seconds)`
for candidate runs, so compilation cannot grant an extra execution window.
Reference validation can omit it to retain independent phase limits.

Python requires 3.11+. The selected executable runs with `-I -B`; candidate
code runs from an exact UTF-8 source snapshot without using cached bytecode.
Its source directory is available for local imports.

Before starting a Python session, callers can probe the configured executable:

```python
from interview_lab.execution import probe_python

probe = probe_python("python")
# Successful shape: {"available": True, "version": [3, 12, 10], "error": ""}
# Failure shape: {"available": False, "version": [], "error": "diagnostic"}
```

The probe executes only a fixed standard-library version query, never a
candidate or reference. It uses the same contained process runner, with a
3-second wall-clock timeout and a combined stdout/stderr limit of 4,096 bytes.
The executable is one argv element, so paths containing spaces are supported.
Malformed responses, launch failures, nonzero exit codes, timeouts, output
overflow, and containment failures return `available: false`.

`available` means that the version query succeeded, **not** that the interpreter
matches the session configuration. The core checks its configured `python_version`
policy before starting: `3.11+`, or an exact minor from `3.11` through `3.14`.
The probe reports the actual major/minor/patch and does not silently substitute
another executable or enforce a separate version policy.

Results contain `status`, `passed`, `total`, `cases`, `diagnostics`, `stdout`,
and `stderr`. Each case contains its `id`, `status`, and diagnostics. Completed
cases also contain command-level statuses and private actual values/mutations.

* `passed`: every checked value, mutation, and expected exception matches.
* `wrong_answer`: mismatching result/type/mutation/expected exception.
* `compile_error`: Python syntax/encoding error or native compilation failure.
* `runtime_error`: candidate import/constructor exception or unexpected call exception.
* `crash`: the execution process exits with a nonzero status without a limit violation.
* `protocol_error`: a successful process exit did not produce the complete valid protocol.
* `timeout`: a phase exceeded its wall-clock limit or the overall budget was exhausted.
* `output_limit`: stdout/stderr or protocol exceeded its byte cap.
* `infrastructure_error`: invalid fixture/options, inaccessible source/work files,
  missing compiler/interpreter, or containment/cleanup failure.

For mixed completed cases, runtime errors take precedence over wrong answers.
For whole-process failures, all cases receive that failure and `passed` is zero;
partial/truncated protocol records are not credited. Diagnostics and actual
outcomes are **private evidence**: callers must redact them for hidden tests,
including stdout/stderr that could echo hidden data.

For public compilation feedback, pass only the current cumulative interface and
public/custom-public cases to `run_suite`. The generated C++ harness includes only
the supplied interface and fixtures; it does not load a pack, hidden cases,
future methods, or reference files. Compiler diagnostics may quote those supplied
fixtures, so a hidden-suite compilation is a separate private operation whose
diagnostics must never be reused as public compilation feedback.

## Bounds, containment, and protocol

* At most 16 parts, 128 methods, and 32 parameters per constructor/method.
* At most 1,024 cases per pack or suite, 256 commands per case, and 4,096
  commands across a pack or suite.
* At most 12 recursive type wrappers, 10,000 entries per collection,
  and 100,000 typed value nodes across a validated pack or suite.
* Strings are at most 1 MiB in UTF-8. A pack or case suite is at most 8 MiB
  in `ensure_ascii=True` JSON. UTF-8 source is at most 2 MiB.
* Timeout must be finite, positive, and at most 600 seconds. It applies
  independently to compilation and to the complete execution suite.
  Optional `total_timeout` must be finite and positive and additionally limits
  both phases together; exhausted budgets prohibit launching another phase.
* Output limit is 1–16,777,216 bytes. Stdout and stderr share that many raw
  bytes; the private protocol has an independent limit of the same size.
  UTF-8 replacement decoding may expand the displayed diagnostic string.

Private results use bounded JSON Lines files, not stdout. Protocol writers stop
after at most `output_limit + 1` bytes; the extra byte marks overflow. The host
rejects duplicate JSON keys, non-finite numbers, invalid Unicode, unknown keys,
wrong case/method IDs, duplicates, missing/reordered records, bad outcome shapes,
and missing terminal records. C++ fixture values are generated as typed literals,
with explicit UTF-8 byte escapes and string lengths (including NUL). Its small
serializer is bundled in `cpp_runtime.hpp`.

Output pipes are continuously drained into bounded buffers. On Windows,
processes start suspended, are assigned to a kill-on-close Job Object, and only
then resume. Closing the job kills descendants on timeout **and on normal
parent exit**, before waiting for inherited output pipes. POSIX uses a new
process group and kills it on every exit path. Each invocation owns a unique
subdirectory of `work_dir`, cleans it after execution, and never removes the
caller-owned work root or source.

**This is process containment, not a security sandbox.** Candidate code retains
the current account's filesystem/network permissions. Malicious code could
tamper with fixtures/protocol or, on POSIX, deliberately leave the process group;
ordinary subprocess descendants are contained. Candidate allocation, arbitrary
file writes, and system-wide resource usage are not sandboxed. Do not run
untrusted code on a sensitive host; use an OS sandbox or disposable account
when that threat model matters.

## Validation

Run the focused tests without installing anything:

```text
python -m unittest tests.test_schema tests.test_execution -v
```

Native C++ tests skip with an explicit reason when no supported compiler is on
PATH. Typed harness generation, quoting, exact-return assertions, and compiler
argument construction are tested even without a compiler. A skipped native
test is not evidence that a C++ binary was compiled or executed.
