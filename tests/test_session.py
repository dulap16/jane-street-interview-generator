import json
from unittest.mock import patch

from interview_lab.session import tick
from interview_lab.storage import LabError, atomic_json, file_lock
from tests.helpers import SessionCase, passed_suite


class LifecycleTests(SessionCase):
    def test_candidate_compile_and_execution_share_remaining_budget(self):
        self.start(duration_minutes=0.1)
        self.solve()
        self.now += 5
        self.lab.test("practice")
        self.assertEqual(self.mock_runner.call_args.kwargs["timeout"], 1)
        self.assertEqual(self.mock_runner.call_args.kwargs["total_timeout"], 1)

    def test_family_config_must_match_authored_pack(self):
        with self.assertRaises(LabError):
            self.prepare(family="graph")

    def test_exact_deadline_rejects_advancement(self):
        self.start(duration_minutes=1)
        self.solve()
        self.lab.test("practice", done=True)
        self.now += 60
        with self.assertRaises(LabError):
            self.lab.reveal("practice")
        self.assertEqual(self.lab.store.load("practice")["part"], 1)

    def test_snapshot_limit_preserves_code_and_records_gap(self):
        self.start()
        self.solve()
        with patch("interview_lab.session.MAX_SNAPSHOTS", 1):
            self.lab.observe("practice")
            self.lab.observe("practice")
        state = self.lab.store.load("practice")
        self.assertEqual(sum(e["kind"] == "observation_gap" for e in state["events"]), 1)
        self.assertIn("def reset", self.lab.read_source(state))
        self.lab.end("practice")

    def test_hint_policy_levels_are_enforced_and_counted(self):
        self.start(hint_policy="standard")
        self.lab.hint("practice", 1)
        self.lab.hint("practice", 2)
        with self.assertRaises(LabError):
            self.lab.hint("practice", 3)
        with self.lab.store.transaction("practice") as state:
            state["config"]["hint_policy"] = "strict"
        with self.assertRaises(LabError):
            self.lab.hint("practice", 1)
        self.assertEqual(sum(e["kind"] == "hint" for e in self.lab.store.load("practice")["events"]), 2)

    def test_edit_during_run_prevents_gate(self):
        self.start()
        self.solve()
        def editing(*args, **kwargs):
            path = self.lab.source_path(self.lab.store.load("practice"))
            path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            return passed_suite(*args, **kwargs)
        self.mock_runner.side_effect = editing
        result = self.lab.test("practice", done=True)
        self.assertFalse(result["unchanged"])
        self.assertFalse(result["gate_passed"])
        with self.assertRaises(LabError):
            self.lab.reveal("practice")

    def test_custom_public_cases_never_grant_advancement(self):
        self.start()
        self.solve()
        path = self.root / "my cases.json"
        path.write_text(json.dumps([{"id": "my-case", "constructor": [], "commands": [
            {"method": "add", "args": [4], "expect": 4}]}]), encoding="utf-8")
        result = self.lab.test("practice", cases_path=path)
        self.assertIsNone(result["gate_passed"])
        self.assertEqual(result["public"]["total"], 1)
        with self.assertRaises(LabError):
            self.lab.test("practice", gate=True, cases_path=path)
        with self.assertRaises(LabError):
            self.lab.reveal("practice")

    def test_runtime_infrastructure_is_not_wrong_answer(self):
        self.start()
        self.solve()
        self.mock_runner.side_effect = lambda *a, **k: {
            "status": "infrastructure_error", "passed": 0, "total": 1,
            "cases": [], "diagnostics": "Execution backend unavailable."}
        result = self.lab.test("practice", done=True)
        self.assertIn("not a candidate failure", result["problem"])
        self.assertFalse(self.lab.store.load("practice")["trustworthy"])

    def test_file_lock_contention_has_explicit_error(self):
        self.prepare()
        path = self.lab.store.session("practice") / ".lock"
        with file_lock(path):
            with self.assertRaises(LabError):
                with file_lock(path, timeout=0.01):
                    self.fail("Second lock unexpectedly acquired")

    def test_end_survives_missing_candidate_file_with_observation_gap(self):
        self.start()
        self.lab.source_path(self.lab.store.load("practice")).unlink()
        self.assertEqual(self.lab.end("practice")["phase"], "ended")
        self.assertTrue(any(e["kind"] == "observation_gap" for e in self.lab.store.load("practice")["events"]))

    def test_ready_has_no_clock_or_solution(self):
        self.prepare()
        self.now += 800
        self.assertEqual(self.lab.status("practice")["elapsed_seconds"], 0)
        self.assertFalse(self.lab.source_path(self.lab.store.load("practice")).exists())
        with self.assertRaises(LabError):
            self.lab.show("practice")

    def test_prepare_checks_every_stage_before_start(self):
        self.prepare()
        self.assertEqual(self.mock_runner.call_count, 2)
        self.assertEqual(len(self.mock_runner.call_args.args[3]), 4)

    def test_bad_reference_does_not_create_ready_state(self):
        self.mock_runner.return_value = None
        self.mock_runner.side_effect = lambda *a, **k: {"status": "wrong_answer", "diagnostics": "HIDDEN_SECRET"}
        with self.assertRaises(LabError) as caught:
            self.prepare()
        self.assertNotIn("HIDDEN_SECRET", str(caught.exception))
        self.assertFalse((self.lab.store.session("practice") / "state.json").exists())

    def test_start_shows_only_revealed_interface(self):
        self.start()
        visible = json.dumps(self.lab.show("practice"))
        self.assertNotIn("FUTURE_SECRET", visible)
        self.assertNotIn("hidden-add", visible)
        self.assertNotIn("reset", visible)
        source = self.lab.read_source(self.lab.store.load("practice"))
        self.assertNotIn("reset", source)

    def test_advance_requires_done_and_pass_same_source(self):
        self.start()
        with self.assertRaises(LabError):
            self.lab.reveal("practice")
        self.solve()
        self.lab.test("practice", gate=True)
        with self.assertRaises(LabError):
            self.lab.reveal("practice")
        self.lab.test("practice", done=True)
        state = self.lab.store.load("practice")
        self.lab.source_path(state).write_text(self.lab.read_source(state) + "\n", encoding="utf-8")
        with self.assertRaises(LabError):
            self.lab.reveal("practice")
        self.lab.test("practice", gate=True)
        with self.assertRaises(LabError):
            self.lab.reveal("practice")
        self.lab.test("practice", done=True)
        self.assertEqual(self.lab.reveal("practice")["part"], 2)

    def test_complete_lifecycle_and_reference_release(self):
        self.start()
        with self.assertRaises(LabError):
            self.lab.reference("practice")
        self.solve()
        self.lab.test("practice", done=True)
        self.lab.reveal("practice")
        self.lab.test("practice", done=True)
        ended = self.lab.reveal("practice")
        self.assertEqual(ended["end_reason"], "completed")
        self.assertIn("reset", self.lab.reference("practice")["references"]["python"])
        with self.assertRaises(LabError):
            self.lab.test("practice")
        with self.assertRaises(LabError):
            self.lab.resume("practice")

    def test_interview_expiry_persists_on_rejected_test(self):
        self.start(duration_minutes=1)
        calls = self.mock_runner.call_count
        self.now += 61
        with self.assertRaises(LabError):
            self.lab.test("practice")
        self.assertEqual(self.mock_runner.call_count, calls)
        state = self.lab.store.load("practice")
        self.assertEqual(state["phase"], "ended")
        self.assertEqual(state["end_reason"], "expired")
        self.assertEqual(state["elapsed"], 60)

    def test_expiry_during_public_test_skips_hidden(self):
        self.start(duration_minutes=1)
        self.solve()
        def delayed(*args, **kwargs):
            self.now += 61
            return passed_suite(*args, **kwargs)
        self.mock_runner.side_effect = delayed
        before = self.mock_runner.call_count
        result = self.lab.test("practice", done=True)
        self.assertFalse(result["gate_passed"])
        self.assertFalse(result["timely"])
        self.assertEqual(self.mock_runner.call_count - before, 1)

    def test_pause_resume_uses_injected_clock(self):
        self.start(mode="study", duration_minutes=1)
        self.now += 10
        self.lab.pause("practice")
        self.now += 800
        self.assertEqual(self.lab.status("practice")["elapsed_seconds"], 10)
        with self.assertRaises(LabError):
            self.lab.test("practice")
        self.lab.resume("practice")
        self.now += 15
        self.assertEqual(self.lab.status("practice")["elapsed_seconds"], 25)

    def test_interview_cannot_pause_and_resume_does_not_reset_clock(self):
        self.start(duration_minutes=1)
        self.now += 20
        with self.assertRaises(LabError):
            self.lab.pause("practice")
        self.assertEqual(self.lab.resume("practice")["elapsed_seconds"], 20)

    def test_backward_clock_ends_and_marks_untrustworthy(self):
        self.start()
        self.now -= 3
        value = self.lab.status("practice")
        self.assertEqual(value["end_reason"], "clock_regression")
        self.assertFalse(value["trustworthy"])

    def test_changed_private_files_invalidate(self):
        self.start()
        path = self.lab.store.session("practice") / "private" / "problem" / "reference.py"
        path.write_text("# modified", encoding="utf-8")
        with self.assertRaises(LabError):
            self.lab.test("practice")
        self.assertFalse(self.lab.store.load("practice")["trustworthy"])

    def test_hidden_failure_redacts_all_diagnostics(self):
        self.start()
        self.solve()
        def result(language, source, interface, cases, work_dir, **kwargs):
            value = passed_suite(language, source, interface, cases, work_dir, **kwargs)
            if "hidden" in str(work_dir):
                value.update(status="wrong_answer", diagnostics="PRIVATE_EXPECTED_772", cases=[{"secret": "PRIVATE_EXPECTED_772"}])
            return value
        self.mock_runner.side_effect = result
        output = json.dumps(self.lab.test("practice", done=True))
        self.assertNotIn("PRIVATE_EXPECTED_772", output)
        self.assertIn("Which signs", output)
        state = json.dumps(self.lab.store.load("practice"))
        self.assertNotIn("PRIVATE_EXPECTED_772", state)

    def test_config_invalid_version_fails_before_reference(self):
        with self.assertRaises(LabError):
            self.prepare(python_version="3.11")
        self.assertEqual(self.mock_runner.call_count, 0)

    def test_checkpoints_and_snapshot_dedup(self):
        self.start(duration_minutes=3, checkpoints=[2, 1], comment_narration=True)
        self.solve()
        path = self.lab.source_path(self.lab.store.load("practice"))
        with path.open("a", encoding="utf-8") as file:
            file.write("\n# THINK: I will check negative inputs.\n")
        self.now += 61
        first = self.lab.observe("practice")
        second = self.lab.observe("practice")
        self.assertEqual(first["alerts"], ["2 minutes remaining"])
        self.assertEqual(second["alerts"], [])
        notes = [e for e in self.lab.store.load("practice")["events"] if e["kind"] == "narration"]
        self.assertEqual(len(notes), 1)
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.lab.observe("practice")
        self.assertEqual(len([e for e in self.lab.store.load("practice")["events"] if e["kind"] == "narration"]), 1)

    def test_corrupt_state_explicit_backup_recovery(self):
        self.start()
        self.now += 10
        self.lab.status("practice")
        (self.lab.store.session("practice") / "state.json").write_text("{broken", encoding="utf-8")
        with self.assertRaises(LabError):
            self.lab.status("practice")
        recovered = self.lab.recover("practice")
        self.assertFalse(recovered["trustworthy"])
        self.assertIsNone(self.lab.store.load("practice")["gate"])

    def test_invalid_ids_and_no_overwrite(self):
        for name in ("../bad", "A", "con", "one/two", "one\\two", ""):
            with self.assertRaises(LabError):
                self.lab.prepare(self.packpath, name)
        self.prepare()
        with self.assertRaises(LabError):
            self.prepare()

    def test_lock_released_after_exception(self):
        self.prepare()
        with self.assertRaises(RuntimeError):
            with self.lab.store.transaction("practice") as state:
                state["trustworthy"] = False
                raise RuntimeError("test interruption")
        self.assertFalse(self.lab.store.load("practice")["trustworthy"])
