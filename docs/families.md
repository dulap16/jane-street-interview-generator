# Ten authoring families

These are original **authoring palettes**, not real interview questions, secret
tests, or claims about what any employer will ask. Reading a concrete palette
may make a closely matching future exercise familiar. Do not label a renamed
example unseen. The bundled ledger is one finite familiar demo; new packs
require an author or skill-assisted generation, independent expectations, and
reference validation. A random family or seed alone is not novel content.

Each palette below gives a complete small starting contract and two potential
extensions. An author must write the selected extension's **full** contract,
types, fixtures, and error precedence into the private pack before starting.
Examples under different twists are independent unless explicitly connected.
Do not show this whole guide to a candidate whose later stages should remain
private. Implement ordinary clear solutions first; optimize only for stated
constraints. All quantities are signed int64; specify overflow behavior rather
than relying on a language's accident.

## 1. `cache` — freshness directory

**First task.** `Solution(lifetime)` stores string values under nonempty string
keys. Lifetime is positive. `put(key,value,now)` returns void and replaces a
value; `get(key,now)` returns optional string. Times are nonnegative and
nondecreasing across valid operations; equal times are allowed. A value written
at time `t` is available while `now < t + lifetime`, and absent at equality.
Empty keys, backward time, or an overflowing expiry raise `invalid_argument`
without changing anything, including the last accepted time. Missing keys are
ordinary misses. Empty values are valid.

**Expected trace.** Lifetime 4: `put("r","red",2) -> null`;
`get("r",5) -> "red"`; `get("r",6) -> null`;
`get("missing",6) -> null`.

**Twist A: targeted invalidation.** Add `erase_prefix(prefix,now) -> int`,
counting only live removed entries. Empty prefix matches every key. With
lifetime 10, `put("ab","1",0)`, `put("ac","2",0)`, `put("b","3",0)`,
then `erase_prefix("a",1) -> 2`, `get("ab",1) -> null`,
`get("b",1) -> "3"`.

**Twist B: nonrefreshing bulk reads.** Add
`get_many(keys,now) -> list[optional[str]]`. Evaluate all keys at the same
logical time, preserve duplicates and input order, and do not refresh expiry.
With lifetime 3 and `put("k","v",0)`,
`get_many(["k","x","k"],2) -> ["v",null,"v"]`;
`get_many(["k"],3) -> [null]`. Validate all keys before advancing time.

**Pitfalls and invariants.** Expiry is exclusive, misses do not insert, reads
do not extend lifetime, and rejected calls cannot advance the clock. Compare
bulk reads with repeated single reads at one time. Include expiry equality,
overwrite-before-expiry, empty values, and a bad later key in a bulk request.

## 2. `simulation` — container-space ledger

**First task.** `Solution(capacities)` accepts nonnegative per-zone capacities.
`reserve(id,zone,amount) -> bool` requires a nonempty globally unique active ID
and positive amount. Unknown zones raise `out_of_range`, malformed requests
raise `invalid_argument`, and insufficient capacity returns false without
consuming the ID. `remaining(zone) -> int` exposes free space.
Define error precedence explicitly in a concrete pack.

**Expected trace.** Capacity `{"a":5}`:
`reserve("x","a",3) -> true`; `reserve("y","a",3) -> false`;
`remaining("a") -> 2`; `reserve("y","a",2) -> true`.

**Twist A: cancellation and lookup.** `cancel(id) -> bool` returns false for
an absent nonempty ID, otherwise restores its units once. `allocation(id)`
returns an optional one-entry zone-to-quantity map. After the trace:
`cancel("x") -> true`; `cancel("x") -> false`;
`remaining("a") -> 3`; `allocation("x") -> null`.

**Twist B: atomic replacement.** Cancel named reservations and create zipped
new reservations as one operation; reuse of a canceled ID is allowed. With
capacities `{"a":2,"b":2}`, `x` holding all of `a`, and `y` all of `b`,
replacing both with `x` in `b` and `y` in `a` succeeds. Replacing `x` with
3 units in `b` fails and leaves both original allocations unchanged.

**Pitfalls and invariants.** Free plus allocated equals initial capacity;
no ID is burned by rejection; cancellation is not double-counted. Test
aggregate overcommit, unknown later elements, rollback of both IDs and counts,
ID reuse, and totals exceeding int64. **This palette resembles the familiar
offline ledger and must not be reused as an “unseen” attempt.**

## 3. `parser` — route-label notation

**First task.** `Solution()` exposes `parse(text) -> map[str,list[str]]`.
An empty string is the empty map. Otherwise grammar is
`record (";" record)*`, where a record is `name "=" name ("," name)*`.
Names contain one or more lowercase ASCII letters. No whitespace, empty
record, trailing separator, or duplicate record key is allowed. Invalid text
raises `invalid_argument`; parsing has no persistent state.

**Expected examples.** `parse("a=x,y;b=z") -> {"a":["x","y"],"b":["z"]}`;
`parse("") -> {}`; `parse("a=x;")` raises `invalid_argument`;
`parse("a=x;a=y")` raises `invalid_argument`.

**Twist A: expansion.** A value item may become `name "*" positive_integer`;
leading zeroes are forbidden. Limit each expanded value list to 100 elements
and reject before excessive allocation. `parse("a=x*3,y") ->
{"a":["x","x","x","y"]}`; `parse("a=x*0")` raises `invalid_argument`.
Define an overflow-safe count parser, not an unbounded expansion.

**Twist B: canonical serialization.** Add
`render(map[str,list[str]]) -> str`, accepting only grammar-valid keys and
nonempty value lists. Sort record keys lexically, preserve value order, and
emit expanded items without compression. `render({"b":["z"],"a":["x","x"]})
-> "a=x,x;b=z"`; `render({}) -> ""`.

**Pitfalls and invariants.** Reject partially valid suffixes rather than
returning a prefix. Parsing canonical rendering reproduces the input map;
rendering a parsed valid string yields a canonical equivalent, not necessarily
the original spelling. Specify total-input bounds and invalid map behavior.

## 4. `graph` — directed handoff network

**First task.** `Solution(nodes)` takes unique nonempty node names; duplicates
or empty names are invalid. `link(source,target) -> bool` inserts a directed
edge, returning false if already present. Self-edges are valid.
`reachable(source,target) -> bool` includes the zero-edge path, so each node
reaches itself. Unknown endpoints raise `out_of_range`; no call creates nodes.

**Expected trace.** Nodes `["a","b","c"]`: `link("a","b") -> true`;
`link("a","b") -> false`; `reachable("a","b") -> true`;
`reachable("b","a") -> false`; `reachable("c","c") -> true`.

**Twist A: deterministic route.** Add
`route(source,target) -> optional[list[str]]`: fewest edges, then
lexicographically smallest full node sequence. With edges `a->c`, `c->d`,
`a->b`, `b->d`, `route("a","d") -> ["a","b","d"]`;
`route("d","a") -> null`; `route("a","a") -> ["a"]`.

**Twist B: disabled nodes.** `disable(node) -> bool` returns true only on
transition to disabled; `enable` reverses it. Links remain stored, but traversal
cannot enter or leave disabled nodes. A disabled endpoint has no route, even
to itself. Disabling `b` in the diamond above makes `route("a","d") ->
["a","c","d"]`; enabling it restores the earlier route.

**Pitfalls and invariants.** Direction matters; cycles terminate; results do
not depend on edge insertion order. Adding an edge cannot destroy reachability
when enabled state is fixed. Test equal-length routes, disconnected cycles,
self-paths, and restored edges after enable.

## 5. `stream` — trailing event counter

**First task.** `Solution(width)` uses a positive integer window width.
`record(time,key) -> void` and `count(time,key) -> int` accept nonnegative
nondecreasing times; equal times are allowed, empty keys are invalid.
Counts include records satisfying `time - width < event_time <= time`.
Every record counts, including identical ones. Invalid calls leave both data
and the logical clock unchanged. Use safe boundary arithmetic.

**Expected trace.** Width 5: `record(2,"a") -> null`;
`record(2,"a") -> null`; `record(6,"a") -> null`;
`count(6,"a") -> 3`; `count(7,"a") -> 1`; `count(7,"x") -> 0`.

**Twist A: ranked summary.** Add `top(time,k) -> list[str]` for positive-count
keys, ordered by decreasing count then lexical key, returning at most `k`.
Negative `k` is invalid; zero returns `[]`. With records `b,a,b,c,c` all
at time 2 and width 5, `top(3,3) -> ["b","c","a"]`.

**Twist B: explicit correction.** Add `retract(time,key,event_time) -> bool`.
Remove one matching still-live event; return false if none exists.
Require `0 <= event_time <= time`, and the usual nondecreasing call time.
After two records `(2,"a")`, `retract(3,"a",2) -> true`,
`count(3,"a") -> 1`, `retract(7,"a",2) -> false` for width 5.

**Pitfalls and invariants.** Do not confuse event multiplicity with a set,
or rank zero-count keys. Counts are nonnegative and equal the live multiset;
rank order is stable under permutation of equal-time insertions.
Expiration and retraction must never decrement an event twice.

## 6. `scheduling` — one-room booking

**First task.** `Solution()` exposes `book(id,start,end) -> bool` and
`schedule() -> list[str]`. Nonempty IDs are unique among accepted bookings;
`0 <= start < end` is required. Intervals are half-open: touching endpoints
do not overlap. Malformed/duplicate IDs raise `invalid_argument`; an overlap
returns false without consuming the ID. `schedule` orders by start then ID.

**Expected trace.** `book("a",2,5) -> true`;
`book("b",5,7) -> true`; `book("c",4,6) -> false`;
`schedule() -> ["a","b"]`.

**Twist A: next available slot.** Add
`next_slot(earliest,duration) -> int`, where earliest is nonnegative and
duration positive; return the smallest start at or after earliest that fits
without overlap. With bookings `[2,5)` and `[5,7)`,
`next_slot(0,2) -> 0`; `next_slot(0,3) -> 7`.
If no representable end exists, raise `out_of_range`.

**Twist B: atomic rescheduling.** Add
`move(id,new_start,new_end) -> bool`, evaluating overlap after removing only
that booking. Unknown ID raises `out_of_range`; malformed endpoints raise
`invalid_argument` first. With `a=[2,5)` and `b=[5,7)`,
`move("a",1,5) -> true`; `move("a",6,8) -> false`;
`schedule() -> ["a","b"]` and `next_slot(0,2) -> 7` still reflect `a=[1,5)`.

**Pitfalls and invariants.** Touching is legal, failed moves preserve the
original interval, and next-slot queries do not reserve anything.
Test nested overlaps, containment in either direction, beginning at an end,
and moving to a position earlier or later in the order.

## 7. `orderbook` — one-sided stock offers

**First task.** `Solution()` stores offers with nonempty unique IDs, positive
integer price ticks, and positive quantity. `offer(id,price,quantity) -> void`
raises `invalid_argument` on malformed or duplicate offers.
`take(quantity) -> map[str,int]` buys as much as available up to the positive
requested quantity, cheapest price first and then original arrival order.
The return map records positive filled quantities by offer ID; filled offers
are removed and their IDs become reusable. An empty book returns `{}`.

**Expected trace.** Add `a` at price 4 quantity 2 and `b` at price 3 quantity 3.
`take(4) -> {"b":3,"a":1}`; `take(2) -> {"a":1}`;
`take(1) -> {}`. Map iteration order is not a fill-order assertion.

**Twist A: price ceiling.** Add `take_up_to(quantity,max_price) -> map[str,int]`.
Both arguments are positive; fill only prices at or below the ceiling using
the existing priority rule. With `a=(4,2)` and `b=(3,3)`,
`take_up_to(5,3) -> {"b":3}`, then `take(3) -> {"a":2}`.

**Twist B: quantity amendments.** `amend(id,new_quantity) -> void` requires an
active ID and positive quantity. A decrease or unchanged quantity keeps
priority; an increase moves the offer to the back of its price level.
With same-price arrivals `a=(5,2)`, `b=(5,2)`, `amend("a",3) -> null`,
then `take(2) -> {"b":2}`.

**Pitfalls and invariants.** Price-time ordering is not lexical ID ordering.
An amendment changes remaining quantity, not original quantity.
For each offer, accepted supply plus amendments minus fills equals remaining
stock. No negative fills; no fills above a price ceiling.
This is an inventory simulation, not trading advice or a mental-math test.

## 8. `spatial` — grid occupancy

**First task.** `Solution(width,height)` takes positive dimensions, with cells
`0 <= x < width`, `0 <= y < height`. `place(id,x,y) -> bool` accepts a nonempty
unique ID. Malformed/duplicate IDs raise `invalid_argument`; invalid coordinates
raise `out_of_range`. An occupied cell returns false without reserving the ID.
`at(x,y) -> optional[str]` returns the occupant or null.

**Expected trace.** Grid 3 by 2: `place("a",1,0) -> true`;
`place("b",1,0) -> false`; `at(1,0) -> "a"`; `at(2,1) -> null`.
Specify duplicate-ID versus coordinate-error precedence in the pack.

**Twist A: movement.** `move(id,x,y) -> bool` requires an existing ID and valid
target. Its current cell counts as available, making a no-op move true.
After the trace, `move("a",1,0) -> true`; `move("a",2,1) -> true`;
`at(1,0) -> null`; `at(2,1) -> "a"`.

**Twist B: nearest free cell.** Add
`nearest(x,y) -> optional[list[int]]` for a valid origin. Minimize Manhattan
distance, then `x`, then `y`, without changing the grid. Return `[x,y]` or
null when full. In a 3-by-3 grid with only `(1,1)` occupied,
`nearest(1,1) -> [0,1]`. A free origin returns itself.

**Pitfalls and invariants.** One cell has at most one ID and one active ID
occupies exactly one cell. Failed placement/movement preserves both indexes.
Distance ties require a stated rule; a scanning solution is adequate for small
stated grids. Bounds, full grids, and coordinate arithmetic deserve fixtures.

## 9. `filesystem` — virtual path table

**First task.** `Solution()` stores text files without directories as separate
objects. `write(path,text) -> void` creates or overwrites; `read(path) ->
optional[str]` returns null if absent. Paths must be absolute. Canonicalization
collapses repeated separators, ignores `.`, and resolves `..`; moving above
root or using root as a file is `invalid_argument`. Components other than `.`
and `..` are case-sensitive nonempty ASCII alphanumeric names.
Empty file text is valid. This is an in-memory model, not host filesystem I/O.

**Expected trace.** `write("/a//b/../c","x") -> null`;
`read("/a/c") -> "x"`; `read("/a/b") -> null`;
`read("/../../x")` raises `invalid_argument`.

**Twist A: direct-child listing.** `list(directory) -> list[str]` canonicalizes
a directory path (root allowed) and returns sorted direct file basenames.
With `/a/c`, `/a/d/e`, and `/x`, `list("/a") -> ["c"]`,
`list("/") -> ["x"]`; listing an empty virtual directory gives `[]`.

**Twist B: atomic subtree relocation.** Add
`move_tree(source,destination) -> int`, operating on files strictly below the
source directory prefix and preserving suffixes. Reject source/destination
equality or ancestry in either direction as `invalid_argument`; destination
file collisions with unmoved files raise `runtime_error`, leaving all files
unchanged. `/a/c` and `/ab/c` with `move_tree("/a","/z") -> 1` yields
`read("/z/c")` equal to old `/a/c`, while `/ab/c` is untouched.

**Pitfalls and invariants.** Prefixes respect component boundaries; canonical
aliases identify the same file; a failed move changes nothing.
Separate path validation from data lookup. Do not touch real files or introduce
host-dependent drive letters, permissions, or symbolic-link semantics.

## 10. `workflow` — prerequisite work queue

**First task.** `Solution()` accepts jobs with nonempty unique IDs.
`add(id,dependencies) -> void` requires distinct already-existing dependency
IDs; unknown dependencies raise `out_of_range`, malformed or duplicate IDs
raise `invalid_argument`. Because dependencies must already exist, additions
cannot introduce a cycle. `ready() -> list[str]` returns lexical order of
unfinished jobs whose dependencies are complete. `finish(id) -> bool` raises
`out_of_range` for unknown IDs; returns false when already finished or not
ready; otherwise marks complete and returns true.

**Expected trace.** Add `a` with `[]`, `b` with `["a"]`, and `c` with `[]`.
`ready() -> ["a","c"]`; `finish("b") -> false`;
`finish("a") -> true`; `ready() -> ["b","c"]`;
`finish("a") -> false`.

**Twist A: worker claims.** Add `claim(worker) -> optional[str]`, assigning
the lexical-first ready unclaimed job to a nonempty worker. Each worker has
at most one claim; a repeated claim returns its existing job.
Claimed jobs are omitted from `ready`. Finishing a claimed ready job releases
the claim; it still checks dependency completion. With independent jobs `a,b`,
`claim("w") -> "a"`, `claim("w") -> "a"`, `claim("v") -> "b"`,
`ready() -> []`. Define release behavior explicitly.

**Twist B: invalidation after rework.** `invalidate(id) -> list[str]` returns
sorted previously finished jobs reset to unfinished: the target and every
finished transitive dependent. Unknown ID raises `out_of_range`. Release any
claims in the affected dependency closure, even on jobs not yet finished.
With a completed chain `a->b->c`, `invalidate("b") -> ["b","c"]`;
`ready() -> ["b"]`. Repeating invalidation returns `[]`.

**Pitfalls and invariants.** Dependencies are sets rather than counters
decremented twice; finished jobs never appear ready. Rework must propagate
transitively, and no worker owns two jobs. Test diamonds, independent jobs,
repeated finish/invalidate, and claims affected by rework.

## Turning a palette into a validated pack

1. **Choose semantics before tests.** Fix error precedence, ordering, tie rules,
   boundaries, time behavior, mutation/aliasing, and numeric limits. Keep later
   extensions private and avoid silently changing earlier behavior.
2. **Make every expectation explicit.** A case is constructor arguments plus
   ordered calls, each carrying one literal `expect` or named `raises`.
   Inout parameters need `after` values. Public and hidden arrays must both
   be nonempty in every part. Do not infer expected answers from reference output.
3. **Translate invariants to observations.** A conservation test should query
   before and after rejection; a rollback test should inspect all potentially
   changed state; an ordering test should vary insertion order. Prose alone
   is not executable coverage.
4. **Use the typed contract.** Encode records with supported maps/lists or
   positional parameters, not undocumented custom structs. Lists preserve
   order; map order is not semantic. Check int64 endpoints, bool-versus-int
   confusion, optional null, empty containers, and C++ reference parameters.
5. **Cross-check without a circular oracle.** Hand-derive small public and
   hidden examples; optionally compare against an independent bounded model
   or metamorphic property. Then run both references where runtimes exist.
   Report an unavailable compiler honestly rather than installing one.
6. **Fail before the clock.** The selected reference must pass every explicit
   fixture during preparation. A pack defect is not candidate evidence.
   Maintain useful nonspoiling failure questions and three progressively
   stronger authored hints per stage.
7. **Record exposure honestly.** Generated does not imply unseen, seed does
   not imply global uniqueness, and local practice metrics do not predict hiring.

The exact JSON schema and language mapping are documented in the private
[authoring guide](../.claude/skills/interview-lab/authoring.md).
