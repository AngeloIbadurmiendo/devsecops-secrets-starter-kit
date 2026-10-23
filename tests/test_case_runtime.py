import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "install_case_runtime", Path(__file__).resolve().parents[1]
    / "scripts/install_case_runtime.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class CaseRuntimeTests(unittest.TestCase):
    def prepare(self, root):
        source, target = root / "source", root / "target"
        for name in module.RUNTIME_FILES:
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"# fixture runtime\n")
        baseline = target / ".feria/manifest.json"
        baseline.parent.mkdir(parents=True)
        baseline.write_bytes(json.dumps({"generator_version": "0.7.2"}).encode())
        return source, target, baseline

    def test_additive_install_preserves_baseline_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target, baseline = self.prepare(Path(directory))
            before = baseline.read_bytes()
            first = module.install_runtime(source, target, "synthetic-revision")
            second = module.install_runtime(source, target, "synthetic-revision")
            self.assertEqual(first, second)
            self.assertEqual(before, baseline.read_bytes())
            self.assertEqual(len(first["files"]), 9)

    def test_conflict_does_not_install_other_files(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target, _ = self.prepare(Path(directory))
            collision = target / module.RUNTIME_FILES[-1]
            collision.parent.mkdir(parents=True)
            collision.write_bytes(b"# user code\n")
            with self.assertRaises(ValueError):
                module.install_runtime(source, target, "synthetic-revision")
            self.assertFalse((target / module.RUNTIME_FILES[0]).exists())
            self.assertEqual(collision.read_bytes(), b"# user code\n")


if __name__ == "__main__":
    unittest.main()
