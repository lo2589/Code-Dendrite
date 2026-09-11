import tempfile
import unittest
from pathlib import Path

from index.api.anchors import _finalize_anchor_graph, generate_all_anchors, load_anchors
from parse.codeGenome import scan_project
from parse.codeGenome.cpp_extractor import CppExtractor
from base.codeGenome.identity import canonical_file_id, symbol_anchor_id
from base.codeGenome.types import AnchorIndex, CodeAnchor


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class AnchorIdentityTests(unittest.TestCase):
    def test_bare_register_class_connects_constructor_and_typed_method(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            _write(
                tmp_path / "app.py",
                "def register(cls):\n"
                "    return cls\n\n"
                "@register\n"
                "class Trainer:\n"
                "    def __init__(self):\n"
                "        self.ready = True\n"
                "    def train(self):\n"
                "        return self.ready\n\n"
                "def run():\n"
                "    trainer = Trainer()\n"
                "    return trainer.train()\n",
            )

            generate_all_anchors(str(tmp_path))
            anchors = load_anchors(str(tmp_path))

            trainer = anchors["app.py::Trainer"]
            assert trainer.registered_as == "Trainer"
            assert "app.py::Trainer.__init__" in trainer.callees
            assert set(anchors["app.py::run"].callees) == {
                "app.py::Trainer",
                "app.py::Trainer.train",
            }

    def test_module_entry_resolves_registry_subscript_calls(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            _write(
                tmp_path / "registry.py",
                "class Registry:\n"
                "    def __call__(self, key):\n"
                "        return lambda fn: fn\n"
                "    def __getitem__(self, key):\n"
                "        raise KeyError(key)\n"
                "manager = Registry()\n",
            )
            _write(
                tmp_path / "runtime.py",
                "from registry import manager\n\n"
                "@manager('runtime.build')\n"
                "def build_runtime():\n"
                "    return object()\n",
            )
            _write(
                tmp_path / "main.py",
                "from registry import manager\n"
                "import runtime\n\n"
                "if __name__ == '__main__':\n"
                "    manager['runtime.build']()\n",
            )

            generate_all_anchors(str(tmp_path))
            anchors = load_anchors(str(tmp_path))

            entry_id = "main.py::__main__"
            target_id = "runtime.py::build_runtime"
            self.assertIn(entry_id, anchors)
            self.assertEqual(anchors[entry_id].symbol_type, "entrypoint")
            self.assertEqual(anchors[entry_id].callees, [target_id])
            self.assertIn(entry_id, anchors[target_id].callers)

    def test_registry_fstring_expands_to_static_route_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            _write(
                tmp_path / "app.py",
                "def dataset(key):\n"
                "    return lambda fn: fn\n\n"
                "@dataset('input.type.real_user')\n"
                "def real_user():\n"
                "    return 'real'\n\n"
                "@dataset('input.type.json')\n"
                "def json_input():\n"
                "    return 'json'\n\n"
                "def choose(kind):\n"
                "    return dataset[f'input.type.{kind}']\n",
            )

            generate_all_anchors(str(tmp_path))
            anchors = load_anchors(str(tmp_path))

            choose = anchors["app.py::choose"]
            self.assertEqual(set(choose.callees), {
                "app.py::real_user",
                "app.py::json_input",
            })
            self.assertEqual(
                {site["registry_template"] for site in choose.call_sites},
                {"input.type.*"},
            )

    def test_registry_template_keeps_all_keys_from_stacked_decorators(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            _write(
                tmp_path / "app.py",
                "def provider(key):\n"
                "    return lambda fn: fn\n\n"
                "@provider('chat')\n"
                "@provider('chat.normal')\n"
                "def chat():\n"
                "    return 'ok'\n\n"
                "@provider('chat.no_stream')\n"
                "def chat_no_stream():\n"
                "    return 'ok'\n\n"
                "def choose(kind):\n"
                "    return provider[f'chat.{kind}']\n",
            )

            generate_all_anchors(str(tmp_path))
            anchors = load_anchors(str(tmp_path))
            choose = anchors["app.py::choose"]

            assert set(choose.callees) == {
                "app.py::chat",
                "app.py::chat_no_stream",
            }
            assert {site["registry_key"] for site in choose.call_sites} == {
                "chat.normal",
                "chat.no_stream",
            }

    def test_registry_template_records_config_field_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            _write(
                tmp_path / "app.py",
                "def provider(key):\n"
                "    return lambda fn: fn\n\n"
                "@provider('cfg.ollama')\n"
                "def ollama():\n"
                "    return 'ok'\n\n"
                "def choose(cfg):\n"
                "    return provider[f'cfg.{cfg.provider.type}']\n",
            )

            generate_all_anchors(str(tmp_path))
            choose = load_anchors(str(tmp_path))["app.py::choose"]

            assert choose.call_sites[0]["config_paths"] == ["provider.type"]
            assert choose.call_sites[0]["registry_key"] == "cfg.ollama"

    def test_module_import_alias_attribute_call_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            _write(
                tmp_path / "code" / "manager" / "runtime.py",
                "def build_runtime():\n"
                "    return object()\n",
            )
            _write(
                tmp_path / "code" / "saver" / "turn_control.py",
                "def launch():\n"
                "    from ..manager import runtime as runtime_module\n"
                "    return runtime_module.build_runtime()\n",
            )

            generate_all_anchors(str(tmp_path))
            anchors = load_anchors(str(tmp_path))

            launch = anchors["code/saver/turn_control.py::launch"]
            target_id = "code/manager/runtime.py::build_runtime"
            self.assertEqual(launch.callees, [target_id])
            self.assertEqual(anchors[target_id].callers, [launch.id])

    def test_attribute_calls_are_not_promoted_to_unrelated_functions(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            _write(
                tmp_path / "app.py",
                "def parse_args():\n"
                "    return 'local'\n\n"
                "class Runner:\n"
                "    def helper(self):\n"
                "        return 1\n\n"
                "    def run(self, parser):\n"
                "        parser.parse_args()\n"
                "        return self.helper()\n\n"
                "def direct():\n"
                "    return parse_args()\n",
            )

            generate_all_anchors(str(tmp_path))
            anchors = load_anchors(str(tmp_path))

            run = anchors["app.py::Runner.run"]
            self.assertIn("app.py::Runner.helper", run.callees)
            self.assertNotIn("app.py::parse_args", run.callees)
            self.assertEqual(
                anchors["app.py::parse_args"].callers,
                ["app.py::direct"],
            )

            before = list(run.callees)
            _finalize_anchor_graph(anchors)
            self.assertEqual(run.callees, before)
            self.assertIn("app.py::Runner.helper", run.callees)

    def test_file_identity_is_path_based_and_lossless(self) -> None:
        self.assertEqual(canonical_file_id(".hidden.py"), ".hidden.py")
        self.assertNotEqual(
            symbol_anchor_id("a/b.py", "main"),
            symbol_anchor_id("a.b.py", "main"),
        )

    def test_duplicate_python_filenames_keep_distinct_canonical_ids(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            _write(
                tmp_path / "app" / "cli.py",
                "def main():\n"
                "    value = 1\n"
                "    return value\n",
            )
            _write(
                tmp_path / "backup" / "cli.py",
                "def main():\n"
                "    return 2\n",
            )

            query = scan_project(str(tmp_path))
            functions = {
                anchor.id: anchor
                for anchor in query.find_functions("main")
            }

            self.assertEqual(
                set(functions),
                {
                    "app/cli.py::main",
                    "backup/cli.py::main",
                },
            )
            self.assertEqual(functions["app/cli.py::main"].line_end, 3)
            self.assertEqual(functions["backup/cli.py::main"].line_end, 2)

            generate_all_anchors(str(tmp_path))
            public = load_anchors(str(tmp_path))
            self.assertEqual(public["app/cli.py::main"].line_end, 3)
            self.assertEqual(public["backup/cli.py::main"].line_end, 2)
            self.assertTrue(public["app/cli.py::main"].hash)
            self.assertTrue(public["backup/cli.py::main"].hash)

    def test_python_config_module_keeps_real_functions(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            _write(
                tmp_path / "load_config.py",
                "def load_config():\n"
                "    value = {'enabled': True}\n"
                "    return value\n",
            )

            query = scan_project(str(tmp_path))
            functions = {
                anchor.id: anchor
                for anchor in query.find_functions("load_config")
            }

            self.assertIn("load_config.py::load_config", functions)
            self.assertEqual(functions["load_config.py::load_config"].line_end, 3)

    def test_duplicate_cpp_filenames_keep_distinct_canonical_ids(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            _write(tmp_path / "src" / "main.cpp", "int run() { return 1; }\n")
            _write(tmp_path / "backup" / "main.cpp", "int run() { return 2; }\n")

            index = CppExtractor(project_root=str(tmp_path)).extract_directory(
                str(tmp_path)
            )

            self.assertIn("src/main.cpp::run", index.anchors)
            self.assertIn("backup/main.cpp::run", index.anchors)

    def test_anchor_index_rejects_cross_file_id_collisions(self) -> None:
        index = AnchorIndex()
        first = CodeAnchor(
            id="app/cli.py::main",
            language="py",
            category="functions",
            file="app/cli.py",
            line_start=1,
            line_end=2,
            name="main",
            code="def main(): pass",
            hash="first",
        )
        second = CodeAnchor(
            id="app/cli.py::main",
            language="py",
            category="functions",
            file="backup/cli.py",
            line_start=1,
            line_end=2,
            name="main",
            code="def main(): pass",
            hash="second",
        )

        index.add(first)
        with self.assertRaisesRegex(ValueError, "anchor ID collision"):
            index.add(second)


if __name__ == "__main__":
    unittest.main()
