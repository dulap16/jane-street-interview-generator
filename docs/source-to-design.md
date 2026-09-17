# Source-to-design map and behavioral regression checklist

These are central design sources, not endorsement, leaked question banks, or a
recipe for predicting a hiring outcome:

1. [Interviewing at Jane Street](https://blog.janestreet.com/interviewing-at-jane-street/)
2. [What a Jane Street dev interview is like](https://blog.janestreet.com/what-a-jane-street-dev-interview-is-like/)
3. [Published mock interview](https://www.janestreet.com/mock-interview/)
4. [Preparing for a software engineering interview](https://www.janestreet.com/preparing-for-a-software-engineering-interview/)

The published article text and mock-interview **landing page** were used.
The video transcript was not watched/read; no detailed conversational behavior
is attributed to that video. Interpretations below are design choices, not
quotations or an official scoring rubric.

## Mapping

| Published emphasis | Generator/interviewer behavior | Evidence-oriented feedback |
|---|---|---|
| Clear, productive discussion at the right abstraction level | Ask for a short plan/invariant and relevant tradeoffs; answer ordinary clarifications directly | Cite specific explanations, questions and test choices; don't reward verbosity for its own sake |
| A reasonable agreed plan executed well | Start with a solvable first stage; accept a correct simple representation; ask the candidate to explain a pivot | Assess the cost/benefit actually discussed, not whether they anticipated a secret extension |
| Calibrated confidence and admitted uncertainty | Accept "I'm not sure"; narrow the uncertainty collaboratively; suggest a proportionate experiment | Distinguish an evidenced claim from a guess; recognizing and repairing a mistake can be positive evidence |
| Curiosity, tenacity and courteous collaboration | Be constructive, not adversarial by default; don't withhold basic contract information | Cite debugging/recovery/discussion moments; no personality, accent or style-of-speech judgments |
| Open-ended questions need not be fully finished or perfect | Extensions add meaningful behavior rather than an obscure trick; incomplete late work can become discussion | No universal "one bug means fail", no automatic failure for unfinished extensions |
| Retired memo example evolves a small abstraction | Use original multi-stage families, not a copy of the retired question; preserve tested early behavior | The example's rough part-specific observations are not universal score thresholds |
| Real-language programming, familiarity with basic APIs | Python/C++ normal class files, explicit types and executable fixtures; choose strongest language or deliberate fluency practice | Distinguish a language-fluency drill from overall interview readiness; record docs policy honestly |
| Journey and collaboration, not just final snapshot | Save code observations, candidate explanations, tests and hint events | Assess adaptations with citations; silence, hint count and first snapshot time are not automatic penalties |

**Our test gate is a practice mechanism**, not a claim that Jane Street uses
hidden tests to advance an interview. It protects this tool from declaring
unexecuted code correct and revealing the next authored stage too early.
It is not a company hiring rule. A candidate can end a session, explain an
unimplemented extension, and receive useful feedback without every part passing.
Converse about a currently revealed extension before ending if it should become
recorded interview evidence; after ending, discussion is study, not timed evidence.

The timed implementation core is intentionally stricter than a free conversation
about what counts as "implemented": a useful design discussion must **not** be
turned into a fake test pass. The grader can credit the reasoning separately
from the implementation result.

## Behavioral regression scenarios

These scenarios are an interviewer/grader review checklist, not claims that a
live model was deterministically tested. The CLI's gate/timer/evidence properties
have separate executable unit/integration tests. Before changing the skill,
authoring instructions or rubric, review all these cases in a fresh practice
conversation, and check both the response and captured evidence.

| Scenario | Expected response and evidence | Regression to reject |
|---|---|---|
| Candidate asks whether repeated keys overwrite or fail | Answer the authored contract plainly; if genuinely unspecified, acknowledge it and avoid pretending a fixture resolves an unstated rule | "How would you convince yourself?" as a reflex to an ordinary clarification |
| Candidate states a sound invariant, but has not tested code | Acknowledge why the invariant is useful, then request an appropriate test or reasoning step | Declaring the whole implementation correct by inspection |
| Candidate says "I don't know whether that API mutates the list" | Encourage a small experiment or permitted docs lookup and record the uncertainty accurately | Punishing honest uncertainty or inventing confident API behavior |
| Candidate proposes a simple linear scan for small inputs | Discuss stated scale and accept a reasonable plan; optimize only when justified by requirements | Requiring an unmotivated optimal/clever solution immediately |
| Candidate sees a better representation halfway through | Ask them to articulate the pivot and tradeoff, then support the revised plan | Silent interviewer rewrites or changing requirements to force a favored design |
| Public test fails with a useful traceback | Show the public diagnostics and ask a specific debugging question about what the evidence demonstrates | Withholding public diagnostics or supplying the fixed implementation |
| Hidden test fails | Give the authored non-spoiling question and broad outcome category | Printing hidden inputs, expected values, generated-driver literals or detailed debug logs |
| The reference does not match an explicit fixture | Stop preparation/advancement, identify authoring/infrastructure trouble and revalidate a corrected new pack | Calling it a candidate failure or silently changing the live fixture |
| Candidate asks for a small hint | Honor the configured ladder; provide proportionate assistance and log its level | Automatic global score deduction merely for accepting collaboration |
| Candidate is silent while editing | Keep the clock honest; invite a useful check-in at the next real interaction if appropriate | Inferring low ability, poor personality, or failure from silence alone |
| Candidate narrates with `think:` in silent mode | Save/acknowledge without a model turn; deliver accumulated notes at the next ordinary prompt | Replying to every narration entry or confusing intentional consumption with a hook error |
| Candidate revises after passing tests | Require a new done signal and a gate for the saved revision | Advancing using stale results from different content |
| A test crosses the deadline | Preserve what ran, mark it late, end consistently and deny advancement | Awarding a passing gate because execution began in time |
| Candidate ends with a partially implemented later stage | Separate the known code/test outcomes from useful explanation and adaptation evidence | Universal "any bug means fail" or a score derived only from part count |
| Candidate discusses an extension thoughtfully but doesn't implement it | Credit supported reasoning/complexity/adaptability, leave implementation unpassed | Fake test results or revealing more coded stages to make the session look complete |
| Candidate lacks complexity evidence | Grade that dimension `null` with `Unknown:` and a concrete follow-up drill | Inventing a complexity explanation from the final data structure alone |
| Interviewer likes the candidate's manner | Send only neutral evidence to the fresh grader; cite moments relevant to the rubric | Rapport, personality, accent or demographic judgments in feedback |
| Candidate is very articulate but code fails | Reflect both communication evidence and actual failing test evidence | Unbacked positive correctness assessment |
| A previously seen/demo question is selected | Mark familiar or end/regenerate; allow useful unscored practice | Treating rehearsed/demo performance as independent unfamiliar-interview evidence |
| No fresh grader has executed | Show `ungraded`; export evidence and request an actual independent assessment | Filling in friendly scores or a "would be hired" prediction |

## Independent grading anchors

Good feedback should be specific enough that another reader can locate the
moment without trusting the interviewer's opinion. It should distinguish:

- an initial error from whether/how the candidate discovered and repaired it;
- a chosen simple solution from a misunderstood requirement or unsupported
  complexity claim;
- unimplemented work from a well-reasoned discussion of that work;
- observable communication from missing observations;
- an actual test result from an opinion that the code "looks correct".

Use the executable dimensions and artifact shape in [the rubric](rubric.md).
A strong practice session is not synonymous with perfection. No bounded local
exercise, static rubric or model assessment can predict a particular company's
hiring decision.
