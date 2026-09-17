"""Standalone demo checks: no interview_lab imports or external dependencies."""

import copy
import importlib.util
import itertools
import json
from pathlib import Path
import random
import shutil
import subprocess
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demos" / "ledger"
PACK = json.loads((DEMO / "pack.json").read_text(encoding="utf-8"))
SPEC = importlib.util.spec_from_file_location("ledger_reference", DEMO / "reference.py")
REFERENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REFERENCE)
Solution = REFERENCE.Solution
ERRORS = {
    "invalid_argument": ValueError,
    "out_of_range": (KeyError, IndexError),
    "runtime_error": RuntimeError,
}


def assert_typed_equal(test, actual, expected):
    """Do not let Python's True == 1 hide a reference result-type mistake."""
    test.assertIs(type(actual), type(expected))
    if isinstance(expected, dict):
        test.assertEqual(set(actual), set(expected))
        for key, value in expected.items():
            assert_typed_equal(test, actual[key], value)
    elif isinstance(expected, list):
        test.assertEqual(len(actual), len(expected))
        for left, right in zip(actual, expected):
            assert_typed_equal(test, left, right)
    else:
        test.assertEqual(actual, expected)


def cpp_type(type_spec):
    if isinstance(type_spec, str):
        return {
            "int": "std::int64_t",
            "bool": "bool",
            "str": "std::string",
            "void": "void",
        }[type_spec]
    kind, value = next(iter(type_spec.items()))
    nested = cpp_type(value)
    return {
        "list": f"std::vector<{nested}>",
        "optional": f"std::optional<{nested}>",
        "map": f"std::map<std::string, {nested}>",
    }[kind]


def cpp_literal(value, type_spec):
    target = cpp_type(type_spec)
    if type_spec == "str":
        encoded = "".join(f"\\{byte:03o}" for byte in value.encode("utf-8"))
        return f'std::string("{encoded}", {len(value.encode("utf-8"))})'
    if type_spec == "bool":
        return "true" if value else "false"
    if type_spec == "int":
        if value == -(2**63):
            return "std::numeric_limits<std::int64_t>::min()"
        return f"std::int64_t{{{value}LL}}"
    kind, nested = next(iter(type_spec.items()))
    if kind == "optional":
        return target + "{}" if value is None else target + "{" + cpp_literal(value, nested) + "}"
    if kind == "list":
        return target + "{" + ", ".join(cpp_literal(item, nested) for item in value) + "}"
    entries = (
        "{" + cpp_literal(key, "str") + ", " + cpp_literal(item, nested) + "}"
        for key, item in value.items()
    )
    return target + "{" + ", ".join(entries) + "}"


class DemoContractTests(unittest.TestCase):
    def test_pack_is_three_part_familiar_demo(self):
        self.assertEqual(PACK["schema"], 1)
        self.assertEqual(PACK["origin"]["kind"], "demo")
        self.assertEqual(PACK["family"], "simulation")
        self.assertEqual(len(PACK["parts"]), 3)
        self.assertEqual(PACK["references"], {"python": "reference.py", "cpp": "reference.cpp"})
        ids = []
        methods = {method["name"]: method for method in PACK["interface"]["methods"]}
        for number, part in enumerate(PACK["parts"], start=1):
            self.assertTrue(part["public"])
            self.assertTrue(part["hidden"])
            self.assertTrue(all(part["invariants"]))
            self.assertEqual(len(part["hints"]), 3)
            self.assertTrue(all(part["hints"]))
            self.assertTrue(part["failure_question"])
            for case in part["public"] + part["hidden"]:
                ids.append(case["id"])
                self.assertTrue(case["commands"])
                for command in case["commands"]:
                    self.assertLessEqual(methods[command["method"]]["since"], number)
                    self.assertNotEqual("expect" in command, "raises" in command)
                    self.assertEqual(
                        len(command["args"]), len(methods[command["method"]]["params"])
                    )
        self.assertEqual(len(ids), len(set(ids)))

    def test_first_prompt_does_not_disclose_later_methods(self):
        first = PACK["parts"][0]
        visible_text = first["title"] + " " + first["prompt"] + " " + " ".join(first["hints"])
        for method in PACK["interface"]["methods"]:
            if method["since"] > 1:
                self.assertNotRegex(visible_text, rf"\b{method['name']}\s*\(")

    def test_negative_constructor_rejected(self):
        with self.assertRaises(ValueError):
            Solution({"a": -1})

    def test_constructor_and_allocation_are_defensive(self):
        capacities = {"a": 5}
        solution = Solution(capacities)
        capacities["a"] = 999
        self.assertTrue(solution.reserve("x", "a", 3))
        self.assertEqual(solution.remaining("a"), 2)
        allocation = solution.allocation("x")
        allocation["a"] = 500
        allocation["other"] = 1
        self.assertEqual(solution.allocation("x"), {"a": 3})
        self.assertTrue(solution.cancel("x"))
        self.assertEqual(solution.remaining("a"), 5)

    def test_batch_does_not_modify_arguments(self):
        solution = Solution({"a": 5})
        solution.reserve("x", "a", 3)
        batches = [
            (["x"], ["u", "v"], ["a", "a"], [3, 3]),
            (["x"], ["u", "v"], ["a", "a"], [2, 3]),
            (["u", "u"], [], [], []),
        ]
        for args in batches:
            original = copy.deepcopy(args)
            try:
                solution.replace(*args)
            except ValueError:
                pass
            self.assertEqual(args, original)

    def test_batch_order_independence(self):
        for additions in (
            [("u", "a", 4), ("v", "b", 2), ("w", "b", 1)],
            [("u", "a", 4), ("v", "a", 1), ("w", "b", 1)],
        ):
            observations = []
            for cancellations in itertools.permutations(["x", "y"]):
                for ordered in itertools.permutations(additions):
                    solution = Solution({"a": 4, "b": 3})
                    solution.reserve("x", "a", 4)
                    solution.reserve("y", "b", 2)
                    new_ids, bays, units = map(list, zip(*ordered))
                    accepted = solution.replace(list(cancellations), new_ids, bays, units)
                    observations.append(
                        (
                            accepted,
                            solution.remaining("a"),
                            solution.remaining("b"),
                            [solution.allocation(key) for key in ["x", "y", "u", "v", "w"]],
                        )
                    )
            self.assertTrue(all(value == observations[0] for value in observations))

    def test_randomized_state_conservation_and_atomicity(self):
        rng = random.Random(87231)
        capacities = {"a": 9, "b": 7, "zero": 0}
        solution = Solution(capacities)
        model = {}
        ids = [f"r{index}" for index in range(12)]
        for _ in range(500):
            operation = rng.choice(["reserve", "cancel", "replace"])
            if operation == "reserve":
                key = rng.choice(ids)
                bay = rng.choice(list(capacities))
                amount = rng.randint(1, 12)
                free = capacities[bay] - sum(
                    size for place, size in model.values() if place == bay
                )
                if key in model:
                    with self.assertRaises(ValueError):
                        solution.reserve(key, bay, amount)
                else:
                    accepted = amount <= free
                    self.assertEqual(solution.reserve(key, bay, amount), accepted)
                    if accepted:
                        model[key] = (bay, amount)
            elif operation == "cancel":
                key = rng.choice(ids)
                self.assertEqual(solution.cancel(key), key in model)
                model.pop(key, None)
            else:
                cancellations = rng.sample(list(model), rng.randint(0, len(model)))
                allowed = [key for key in ids if key not in model or key in cancellations]
                additions = rng.sample(allowed, rng.randint(0, min(4, len(allowed))))
                bays = [rng.choice(list(capacities)) for _ in additions]
                amounts = [rng.randint(1, 12) for _ in additions]
                proposed = {key: value for key, value in model.items() if key not in cancellations}
                proposed.update(zip(additions, zip(bays, amounts)))
                accepted = all(
                    sum(size for place, size in proposed.values() if place == bay) <= capacity
                    for bay, capacity in capacities.items()
                )
                self.assertEqual(
                    solution.replace(cancellations, additions, bays, amounts), accepted
                )
                if accepted:
                    model = proposed
            for bay, capacity in capacities.items():
                used = sum(size for place, size in model.values() if place == bay)
                self.assertEqual(solution.remaining(bay), capacity - used)
                self.assertGreaterEqual(solution.remaining(bay), 0)
            for key in ids:
                expected = None if key not in model else {model[key][0]: model[key][1]}
                self.assertEqual(solution.allocation(key), expected)


def fixture_test(case):
    def run(self):
        constructor_args = copy.deepcopy(case["constructor"])
        solution = Solution(*constructor_args)
        self.assertEqual(constructor_args, case["constructor"])
        for index, command in enumerate(case["commands"]):
            with self.subTest(command=index, method=command["method"]):
                args = copy.deepcopy(command["args"])
                method = getattr(solution, command["method"])
                if "raises" in command:
                    with self.assertRaises(ERRORS[command["raises"]]):
                        method(*args)
                else:
                    assert_typed_equal(self, method(*args), command["expect"])
                self.assertEqual(args, command["args"])
    return run


class DemoFixtureTests(unittest.TestCase):
    pass


for _part in PACK["parts"]:
    for _case in _part["public"] + _part["hidden"]:
        setattr(
            DemoFixtureTests,
            "test_" + _case["id"].replace("-", "_"),
            fixture_test(_case),
        )


class DemoCppTests(unittest.TestCase):
    def test_cpp_reference_against_all_explicit_fixtures(self):
        compiler = next(
            (path for name in ("g++", "clang++", "cl") if (path := shutil.which(name))),
            None,
        )
        if compiler is None:
            self.skipTest("No existing C++ compiler on PATH; no toolchain is installed by tests")
        build = ROOT / "tests" / (".demo-build-" + uuid.uuid4().hex)
        build.mkdir()
        try:
            shutil.copyfile(DEMO / "reference.cpp", build / "reference.cpp")
            lines = [
                '#include "reference.cpp"',
                "#include <limits>",
                "#include <iostream>",
                "int main() {",
                "try {",
            ]
            methods = {method["name"]: method for method in PACK["interface"]["methods"]}
            for part in PACK["parts"]:
                for case in part["public"] + part["hidden"]:
                    constructor = ", ".join(
                        cpp_literal(value, parameter["type"])
                        for value, parameter in zip(
                            case["constructor"], PACK["interface"]["constructor"]
                        )
                    )
                    lines += ["{", f"Solution solution({constructor});"]
                    for index, command in enumerate(case["commands"]):
                        definition = methods[command["method"]]
                        arguments = ", ".join(
                            cpp_literal(value, parameter["type"])
                            for value, parameter in zip(command["args"], definition["params"])
                        )
                        call = f"solution.{command['method']}({arguments})"
                        label = cpp_literal(f"{case['id']} command {index}", "str")
                        if "raises" in command:
                            lines += [
                                "{ bool caught = false;",
                                f"try {{ (void){call}; }}",
                                f"catch (const std::{command['raises']}&) {{ caught = true; }}",
                                f"if (!caught) throw std::runtime_error({label});",
                                "}",
                            ]
                        else:
                            expected = cpp_literal(command["expect"], definition["returns"])
                            lines.append(
                                f"if ({call} != {expected}) throw std::runtime_error({label});"
                            )
                    lines.append("}")
            lines += [
                "} catch (const std::exception& error) {",
                "std::cerr << error.what(); return 1;",
                "}",
                "return 0;",
                "}",
            ]
            harness = build / "harness.cpp"
            executable = build / "demo-tests.exe"
            harness.write_text("\n".join(lines), encoding="utf-8")
            if Path(compiler).stem.lower() == "cl":
                command = [
                    compiler, "/nologo", "/std:c++17", "/EHsc", "/W4",
                    str(harness), "/Fe:" + str(executable), "/Fo:" + str(build) + "\\",
                ]
            else:
                command = [
                    compiler, "-std=c++17", "-Wall", "-Wextra", "-pedantic",
                    str(harness), "-o", str(executable),
                ]
            result = subprocess.run(
                command, cwd=build, capture_output=True, text=True, timeout=60
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run(
                [str(executable)], cwd=build, capture_output=True, text=True, timeout=30
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        finally:
            shutil.rmtree(build)


if __name__ == "__main__":
    unittest.main()
