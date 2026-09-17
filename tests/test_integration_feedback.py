import copy
import json
from pathlib import Path

from interview_lab.feedback import (DIMENSIONS, evidence_payload, export_evidence,
                                    import_debrief, metrics, progress, select_family,
                                    validate_debrief)
from interview_lab.integration import hook, setup, statusline_text
from interview_lab.storage import LabError, digest
from tests.helpers import SessionCase


class HookTests(SessionCase):
    def payload(self, text, number="one"):
        return {"hook_event_name": "UserPromptSubmit", "session_id": "claude-session",
                "prompt_id": number, "prompt": text}

    def test_no_active_session_is_noop(self):
        self.assertEqual(hook(self.lab, self.payload("Hello")), {})

    def test_silent_think_consumed_and_delivered_once(self):
        self.start()
        output = hook(self.lab, self.payload("think: I should check zero and negative values."))
        self.assertEqual(output["decision"], "block")
        self.assertIn("Intentionally consumed", output["reason"])
        self.assertNotIn("hookSpecificOutput", output)
        repeated = hook(self.lab, self.payload("think: I should check zero and negative values."))
        self.assertEqual(repeated["decision"], "block")
        normal = hook(self.lab, self.payload("I am ready to test.", "two"))
        context = json.loads(normal["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(len(context["narration"]), 1)
        repeated_normal = hook(self.lab, self.payload("I am ready to test.", "two"))
        self.assertEqual(json.loads(repeated_normal["hookSpecificOutput"]["additionalContext"])["narration"], [])
        later = hook(self.lab, self.payload("What are the input constraints?", "three"))
        self.assertEqual(json.loads(later["hookSpecificOutput"]["additionalContext"])["narration"], [])
        events = self.lab.store.load("practice")["events"]
        self.assertEqual(sum(e["kind"] == "narration" for e in events), 1)
        self.assertEqual(sum(e["kind"] == "message" for e in events), 2)

    def test_reactive_think_reaches_model_context(self):
        self.start(narration="reactive")
        output = hook(self.lab, self.payload("think: I will test the boundary."))
        self.assertNotIn("decision", output)
        self.assertEqual(len(json.loads(output["hookSpecificOutput"]["additionalContext"])["narration"]), 1)

    def test_hook_injects_expiry_without_revealing(self):
        self.start(duration_minutes=1)
        self.now += 61
        output = json.dumps(hook(self.lab, self.payload("Next part please.")))
        self.assertIn("ended", output)
        self.assertNotIn("FUTURE_SECRET", output)

    def test_other_claude_session_needs_explicit_rebind(self):
        self.start()
        hook(self.lab, self.payload("Reasoning here."))
        second = self.payload("Another session", "other")
        second["session_id"] = "someone-else"
        self.assertEqual(hook(self.lab, second)["decision"], "block")
        self.lab.resume("practice")
        self.assertNotIn("decision", hook(self.lab, second))

    def test_subagents_and_invalid_input(self):
        self.start()
        value = self.payload("Not candidate evidence.")
        value["agent_id"] = "grader"
        self.assertEqual(hook(self.lab, value), {})
        with self.assertRaises(LabError):
            hook(self.lab, {"prompt": "test"})

    def test_setup_preview_merge_idempotence_and_conflict(self):
        preview = setup(self.lab, apply=False, statusline=True)
        self.assertFalse((self.root / ".claude" / "settings.json").exists())
        self.assertNotIn("refreshInterval", preview["settings"]["statusLine"])
        configured = setup(self.lab, apply=True, statusline=True)
        path = self.root / ".claude" / "settings.json"
        first = path.read_text(encoding="utf-8")
        setup(self.lab, apply=True, statusline=True)
        self.assertEqual(path.read_text(encoding="utf-8"), first)
        with self.assertRaises(LabError):
            setup(self.lab, apply=True, statusline=True, refresh_interval=1)
        self.assertEqual(path.read_text(encoding="utf-8"), first)
        self.assertFalse(configured["global_settings_modified"])

    def test_statusline_and_terminal_think(self):
        self.start()
        self.now += 10
        self.assertIn("44:50", statusline_text(self.lab))
        result = self.lab.communicate("practice", "I want to state an invariant.", narration=True)
        self.assertFalse(result["model_reply"])
        self.assertEqual(len(self.lab.context("practice")["narration"]), 1)
        self.assertEqual(self.lab.context("practice")["narration"], [])


def valid_grade(evidence):
    snapshots = [e for e in evidence["events"] if e["kind"] == "snapshot"]
    last = snapshots[-1]
    cite = {"event": last["id"], "quote": "class Solution:"}
    dimensions = {name: {"score": None, "assessment": "Unknown: insufficient evidence for a rating.",
                         "citations": []} for name in DIMENSIONS}
    dimensions["clarity"] = {"score": 3, "assessment": "The observed class has a direct representation.",
                             "citations": [cite]}
    return {"schema": 1, "session_id": evidence["session_id"], "evidence_digest": evidence["evidence_digest"],
            "grader": {"kind": "human", "name": "Unit test fixture, not a real assessment"},
            "dimensions": dimensions,
            "improvements": [{"action": f"Test fixture action {n}, not actual feedback.", "citations": [cite]}
                             for n in range(1, 4)],
            "final_review": {"assessment": "Test fixture review of final code.", "citations": [cite]},
            "replay": {"event": last["id"], "alternative": "Test fixture alternative."},
            "drill": {"family": "stream", "prompt": "Test fixture drill.", "reason": "Test fixture reasoning.",
                      "citations": [cite]}, "signal": "practice-only"}


class FeedbackTests(SessionCase):
    def evidence(self):
        state = self.lab.store.load("practice")
        payload = evidence_payload(state)
        payload["evidence_digest"] = digest(payload)
        return payload

    def test_no_grader_means_no_scores_or_progress(self):
        self.complete()
        self.assertEqual(progress(self.lab)["eligible_interviews"], 0)
        self.assertIsNone(self.lab.store.load("practice")["debrief"])

    def test_evidence_after_end_and_no_future_or_hidden(self):
        self.start()
        with self.assertRaises(LabError):
            export_evidence(self.lab, "practice")
        self.lab.communicate("practice", "A negative value should reduce the total.", narration=True)
        self.lab.end("practice")
        exported = export_evidence(self.lab, "practice")
        raw = (self.root / exported["path"]).read_text(encoding="utf-8")
        self.assertNotIn("FUTURE_SECRET", raw)
        self.assertNotIn("hidden-add", raw)
        self.assertNotIn("Which signs", raw)
        self.assertIn("A negative value", raw)
        self.assertIn("revealed_requirements", raw)

    def test_valid_cited_grade_and_progress(self):
        self.complete()
        evidence = self.evidence()
        grade = valid_grade(evidence)
        path = self.root / "grade.json"
        path.write_text(json.dumps(grade), encoding="utf-8")
        result = import_debrief(self.lab, "practice", path)
        self.assertTrue(result["scored_trend_eligible"])
        self.assertEqual(progress(self.lab)["eligible_interviews"], 1)
        self.assertEqual(select_family(self.lab, "weakest", "stable")["family"], "stream")

    def test_invalid_debriefs_are_rejected(self):
        self.complete()
        evidence = self.evidence()
        good = valid_grade(evidence)
        cases = []
        bad = copy.deepcopy(good)
        bad["dimensions"]["clarity"]["citations"][0]["quote"] = "This never appeared"
        cases.append(bad)
        bad = copy.deepcopy(good)
        bad["dimensions"]["clarity"]["score"] = True
        cases.append(bad)
        bad = copy.deepcopy(good)
        bad["dimensions"]["communication"] = copy.deepcopy(bad["dimensions"]["clarity"])
        cases.append(bad)
        bad = copy.deepcopy(good)
        bad["evidence_digest"] = "wrong"
        cases.append(bad)
        bad = copy.deepcopy(good)
        bad["signal"] = "would be hired"
        cases.append(bad)
        bad = copy.deepcopy(good)
        bad["dimensions"]["complexity"]["assessment"] = "Perfect performance without evidence."
        cases.append(bad)
        for index, grade in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(LabError):
                validate_debrief(grade, evidence)

    def test_study_and_familiar_excluded(self):
        self.start(mode="study")
        self.solve()
        self.lab.end("practice")
        grade = valid_grade(self.evidence())
        path = self.root / "grade.json"
        path.write_text(json.dumps(grade), encoding="utf-8")
        self.assertFalse(import_debrief(self.lab, "practice", path)["scored_trend_eligible"])
        self.assertEqual(progress(self.lab)["eligible_interviews"], 0)

    def test_metrics_observations_not_keystrokes(self):
        self.start()
        self.now += 10
        self.solve()
        self.lab.observe("practice")
        self.lab.communicate("practice", "Consider the empty state.", narration=True)
        self.now += 20
        self.lab.communicate("practice", "Now consider repeated operations.", narration=True)
        values = metrics(self.lab.store.load("practice"))
        self.assertEqual(values["first_observed_saved_edit_seconds"], 10)
        self.assertEqual(values["narration_intervals_seconds"], [20])
        self.assertEqual(values["snapshots_observed"], 2)

    def test_seeded_selection_without_invented_weakness(self):
        one = select_family(self.lab, "weakest", "repeatable")
        two = select_family(self.lab, "weakest", "repeatable")
        self.assertEqual(one, two)
        self.assertIn("No eligible", one["reason"])
