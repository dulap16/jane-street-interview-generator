import copy
import math
import unittest
from unittest import mock

from interview_lab import schema


def _method(name="read", params=None, returns="int", since=1):
    return {"name": name, "params": params or [], "returns": returns, "since": since}


def _case(id_="basic", method="read", args=None, expect=1):
    return {"id": id_, "constructor": [], "commands": [{"method": method, "args": args or [], "expect": expect}]}


def _pack():
    return {
        "schema": 1,
        "id": "typed-demo",
        "title": "Typed demo",
        "family": "cache",
        "origin": {"kind": "demo", "seed": "0"},
        "interface": {"constructor": [], "methods": [_method()]},
        "parts": [{
            "title": "First", "prompt": "Implement read.",
            "public": [_case("public-1")], "hidden": [_case("hidden-1")],
            "invariants": ["One instance per case."],
            "hints": ["Hint one.", "Hint two.", "Hint three."],
            "failure_question": "Which invariant failed?",
        }],
        "references": {"python": "reference.py", "cpp": "reference.cpp"},
    }


class PackSchemaTests(unittest.TestCase):
    def test_valid_pack_and_no_mutation(self):
        pack = _pack()
        original = copy.deepcopy(pack)
        self.assertIsNone(schema.validate_pack(pack))
        self.assertEqual(pack, original)

    def test_exact_keys_everywhere(self):
        targets = (
            lambda p: p,
            lambda p: p["origin"],
            lambda p: p["references"],
            lambda p: p["interface"],
            lambda p: p["interface"]["methods"][0],
            lambda p: p["parts"][0],
            lambda p: p["parts"][0]["public"][0],
            lambda p: p["parts"][0]["public"][0]["commands"][0],
        )
        for target in targets:
            with self.subTest(target=target):
                pack = _pack()
                target(pack)["typo"] = 1
                with self.assertRaisesRegex(schema.SchemaError, "unknown keys"):
                    schema.validate_pack(pack)

    def test_missing_pack_key(self):
        pack = _pack()
        del pack["references"]
        with self.assertRaisesRegex(schema.SchemaError, "pack: missing keys: references"):
            schema.validate_pack(pack)

    def test_bad_schema_family_origin(self):
        for key, value in (("schema", True), ("schema", 2), ("family", "other"), ("id", "Upper")):
            pack = _pack()
            pack[key] = value
            with self.subTest(key=key), self.assertRaises(schema.SchemaError):
                schema.validate_pack(pack)
        pack = _pack()
        pack["origin"]["kind"] = "remote"
        with self.assertRaises(schema.SchemaError):
            schema.validate_pack(pack)

    def test_reference_paths_and_reserved_names(self):
        for name in ("../reference.py", r"..\reference.py", "/reference.py", r"C:\reference.py",
                     "CON.py", "con.more.py", "nul.py", "COM1.py", "LPT9.py", ".hidden.py",
                     "reference.py:stream", "ref..py", "ref.py.", "reference.cpp"):
            pack = _pack()
            pack["references"]["python"] = name
            with self.subTest(name=name), self.assertRaisesRegex(schema.SchemaError, "references.python"):
                schema.validate_pack(pack)
        pack = _pack()
        pack["references"]["python"] = "other-reference_2.py"
        schema.validate_pack(pack)

    def test_unsafe_identifiers(self):
        for name in ("class", "def", "auto", "co_await", "self", "Solution", "_hidden",
                     "has__reserved", "9bad", "a-b", "naïve", "x" * 65):
            pack = _pack()
            pack["interface"]["methods"][0]["name"] = name
            with self.subTest(name=name), self.assertRaisesRegex(schema.SchemaError, "identifier"):
                schema.validate_pack(pack)

    def test_duplicate_method_and_parameters(self):
        pack = _pack()
        pack["interface"]["methods"].append(_method())
        with self.assertRaisesRegex(schema.SchemaError, "duplicate method"):
            schema.validate_pack(pack)
        interface = {"constructor": [], "methods": [_method(params=[
            {"name": "value", "type": "int"}, {"name": "value", "type": "str"},
        ])]}
        with self.assertRaisesRegex(schema.SchemaError, "duplicate parameter"):
            schema.validate_interface(interface)

    def test_constructor_inout_is_rejected(self):
        pack = _pack()
        pack["interface"]["constructor"] = [{"name": "values", "type": {"list": "int"}, "mode": "inout"}]
        with self.assertRaisesRegex(schema.SchemaError, "constructor parameters cannot be inout"):
            schema.validate_pack(pack)

    def test_invalid_modes_and_parameter_keys(self):
        for extra in ({"mode": "out"}, {"mode": True}, {"extra": 3}):
            interface = {"constructor": [], "methods": [_method(params=[{"name": "value", "type": "int", **extra}])]}
            with self.subTest(extra=extra), self.assertRaises(schema.SchemaError):
                schema.validate_interface(interface)

    def test_nonempty_parts_cases_and_explanations(self):
        for field, value in (
            ("public", []), ("hidden", []), ("invariants", []), ("invariants", [" "]),
            ("hints", ["one", "two"]), ("hints", ["one", "two", ""]),
            ("failure_question", ""), ("prompt", " "), ("title", ""),
        ):
            pack = _pack()
            pack["parts"][0][field] = value
            with self.subTest(field=field), self.assertRaises(schema.SchemaError):
                schema.validate_pack(pack)

    def test_duplicate_case_ids_across_visibility(self):
        pack = _pack()
        pack["parts"][0]["hidden"][0]["id"] = "public-1"
        with self.assertRaisesRegex(schema.SchemaError, "duplicate case id"):
            schema.validate_pack(pack)

    def test_since_and_cumulative_interfaces(self):
        pack = _pack()
        pack["interface"]["methods"].append(_method("later", since=2))
        part2 = copy.deepcopy(pack["parts"][0])
        part2["public"] = [_case("public-2", "later")]
        part2["hidden"] = [_case("hidden-2", "read")]
        pack["parts"].append(part2)
        schema.validate_pack(pack)
        self.assertEqual([m["name"] for m in schema.interface_for(pack, 1)["methods"]], ["read"])
        cumulative = schema.interface_for(pack, 2)
        self.assertEqual(set(cumulative), {"constructor", "methods"})
        self.assertEqual(set(cumulative["methods"][0]), {"name", "params", "returns", "since"})
        self.assertEqual([m["name"] for m in cumulative["methods"]], ["read", "later"])
        cumulative["methods"][0]["name"] = "changed"
        self.assertEqual(pack["interface"]["methods"][0]["name"], "read")
        for invalid in (0, 3, True, "1"):
            with self.subTest(part=invalid), self.assertRaises(schema.SchemaError):
                schema.interface_for(pack, invalid)
        pack["parts"][0]["public"][0]["commands"][0]["method"] = "later"
        with self.assertRaisesRegex(schema.SchemaError, "not available"):
            schema.validate_pack(pack)

    def test_invalid_since(self):
        for since in (0, 2, True, 1.0, "1"):
            pack = _pack()
            pack["interface"]["methods"][0]["since"] = since
            with self.subTest(since=since), self.assertRaisesRegex(schema.SchemaError, "since"):
                schema.validate_pack(pack)

    def test_unexercised_method(self):
        pack = _pack()
        pack["interface"]["methods"].append(_method("unused"))
        with self.assertRaisesRegex(schema.SchemaError, "never exercised: unused"):
            schema.validate_pack(pack)


class TypedValueTests(unittest.TestCase):
    def test_primitives_and_unicode_scalar_strings(self):
        for value, descriptor in (
            (-(1 << 63), "int"), ((1 << 63) - 1, "int"), (False, "bool"),
            (True, "bool"), ("nul:\0 quotes:\" slash:\\ \n 中文 🧪", "str"), (None, "void"),
        ):
            with self.subTest(value=value):
                schema.validate_value(value, descriptor)

    def test_no_coercions_nonfinite_or_surrogates(self):
        for value, descriptor in (
            (True, "int"), (False, "int"), (1.0, "int"), (1 << 63, "int"),
            (-(1 << 63) - 1, "int"), (1, "bool"), (0, "bool"), ("1", "int"),
            (math.nan, "int"), (math.inf, "int"), (b"text", "str"),
            ("\ud800", "str"), ("\udfff", "str"), (1, "void"), ((1, 2), {"list": "int"}),
        ):
            with self.subTest(value=repr(value)), self.assertRaises(schema.SchemaError):
                schema.validate_value(value, descriptor)

    def test_nested_collections_optional_map(self):
        descriptor = {"map": {"list": {"optional": "str"}}}
        schema.validate_type(descriptor)
        schema.validate_value({"é\0": ["🦉", None, ""]}, descriptor)
        schema.validate_value({}, descriptor)
        schema.validate_value(None, {"optional": {"map": "int"}})
        schema.validate_value([{}, {"a": True}], {"list": {"map": "bool"}})
        for value in ({1: []}, {"x": [1]}, {"x": ["\ud800"]}, {"\udfff": []}):
            with self.subTest(value=repr(value)), self.assertRaises(schema.SchemaError):
                schema.validate_value(value, descriptor)

    def test_unknown_types_and_void_only_at_return(self):
        for descriptor in ("float", "integer", {}, {"list": "void"}, {"optional": "void"},
                           {"map": "void"}, {"set": "int"}, {"list": "int", "map": "str"}, 1, None):
            with self.subTest(descriptor=descriptor), self.assertRaises(schema.SchemaError):
                schema.validate_type(descriptor, allow_void=True)
        with self.assertRaises(schema.SchemaError):
            schema.validate_type("void")
        schema.validate_type("void", allow_void=True)

    def test_depth_cycles_and_collection_bounds(self):
        descriptor = "int"
        for _ in range(schema.MAX_TYPE_DEPTH + 1):
            descriptor = {"list": descriptor}
        with self.assertRaisesRegex(schema.SchemaError, "nesting"):
            schema.validate_type(descriptor)
        cyclic = {}
        cyclic["list"] = cyclic
        with self.assertRaises(schema.SchemaError):
            schema.validate_type(cyclic)
        with self.assertRaises(schema.SchemaError):
            schema.validate_value([0] * (schema.MAX_COLLECTION + 1), {"list": "int"})
        with self.assertRaises(schema.SchemaError):
            schema.validate_value("x" * (schema.MAX_STRING_BYTES + 1), "str")

    def test_language_type_names(self):
        descriptor = {"map": {"list": {"optional": "int"}}}
        self.assertEqual(schema.cpp_type(descriptor), "std::map<std::string, std::vector<std::optional<std::int64_t>>>")
        self.assertEqual(schema.python_type(descriptor), "dict[str, list[int | None]]")
        self.assertEqual(schema.cpp_type("void"), "void")
        self.assertEqual(schema.python_type("void"), "None")

    def test_shared_node_and_serialized_size_bounds(self):
        descriptor = {"list": "str"}
        interface = {"constructor": [], "methods": [_method(returns=descriptor)]}
        cases = [_case(expect=["a", "b", "c"])]
        with mock.patch.object(schema, "MAX_VALUE_NODES", 3):
            with self.assertRaisesRegex(schema.SchemaError, "node budget"):
                schema.validate_cases(interface, cases)
        with mock.patch.object(schema, "MAX_PACK_BYTES", 64):
            with self.assertRaisesRegex(schema.SchemaError, "serialized JSON"):
                schema.validate_cases(interface, cases)
        with mock.patch.object(schema, "MAX_TOTAL_COMMANDS", 1):
            cases = [_case("one"), _case("two")]
            with self.assertRaisesRegex(schema.SchemaError, "total command count"):
                schema.validate_cases({"constructor": [], "methods": [_method()]}, cases)


class CaseSchemaTests(unittest.TestCase):
    def setUp(self):
        self.interface = {"constructor": [], "methods": [_method(
            "update", [{"name": "values", "type": {"list": "int"}, "mode": "inout"}], "void",
        )]}
        self.case = _case(method="update", args=[[1]], expect=None)

    def test_mutation_expectation_on_success_and_exception(self):
        self.case["commands"][0]["after"] = {"values": [1, 2]}
        schema.validate_cases(self.interface, [self.case])
        del self.case["commands"][0]["expect"]
        self.case["commands"][0]["raises"] = "invalid_argument"
        schema.validate_cases(self.interface, [self.case])

    def test_explicit_exactly_one_expectation(self):
        command = self.case["commands"][0]
        del command["expect"]
        with self.assertRaisesRegex(schema.SchemaError, "exactly one"):
            schema.validate_cases(self.interface, [self.case])
        command.update(expect=None, raises="runtime_error")
        with self.assertRaisesRegex(schema.SchemaError, "exactly one"):
            schema.validate_cases(self.interface, [self.case])

    def test_after_only_for_inout_names_and_types(self):
        for after in ({"wrong": []}, {"values": [True]}, [], {"values": None}):
            self.case["commands"][0]["after"] = after
            with self.subTest(after=after), self.assertRaises(schema.SchemaError):
                schema.validate_cases(self.interface, [self.case])
        self.case["commands"][0]["after"] = {"values": [1]}
        self.interface["methods"][0]["params"][0]["mode"] = "in"
        with self.assertRaises(schema.SchemaError):
            schema.validate_cases(self.interface, [self.case])

    def test_unknown_exception_arity_method_and_case_id(self):
        for patch in ({"raises": "ValueError"}, {"args": []}, {"method": "missing"}):
            case = copy.deepcopy(self.case)
            case["commands"][0].update(patch)
            if "raises" in patch:
                del case["commands"][0]["expect"]
            with self.subTest(patch=patch), self.assertRaises(schema.SchemaError):
                schema.validate_cases(self.interface, [case])
        for id_ in ("", "a_b", "-one", "one-", "one--two", "x" * 65, "Ü"):
            self.case["id"] = id_
            with self.subTest(id=id_), self.assertRaises(schema.SchemaError):
                schema.validate_cases(self.interface, [self.case])

    def test_suite_limits_and_duplicates(self):
        with self.assertRaisesRegex(schema.SchemaError, "duplicate"):
            schema.validate_cases(self.interface, [self.case, copy.deepcopy(self.case)])
        with self.assertRaises(schema.SchemaError):
            schema.validate_cases(self.interface, [])
        self.case["commands"] *= schema.MAX_COMMANDS + 1
        with self.assertRaises(schema.SchemaError):
            schema.validate_cases(self.interface, [self.case])


if __name__ == "__main__":
    unittest.main()
