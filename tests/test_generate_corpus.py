from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_corpus.py"
SPEC = importlib.util.spec_from_file_location("generate_corpus", SCRIPT)
assert SPEC and SPEC.loader
generate_corpus = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = generate_corpus
SPEC.loader.exec_module(generate_corpus)


class GenerateCorpusTests(unittest.TestCase):
    def test_fragment_is_deterministic(self) -> None:
        first = generate_corpus.deterministic_fragment("seed", "case", 48)
        second = generate_corpus.deterministic_fragment("seed", "case", 48)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 48)

    def test_manifest_contains_no_raw_credential_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "corpus"
            manifest = generate_corpus.generate_corpus(output)
            serialized = json.dumps(manifest)
            self.assertNotIn("ghp_", serialized)
            self.assertNotIn("AKIA", serialized)
            self.assertNotIn("AIzaSy", serialized)
            self.assertNotIn("sk_live_", serialized)

    def test_expected_case_distribution_and_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "corpus"
            manifest = generate_corpus.generate_corpus(output)
            positives = [case for case in manifest["cases"] if case["classification"] == "positive"]
            benign = [case for case in manifest["cases"] if case["classification"] == "benign"]
            self.assertEqual(len(positives), 4)
            self.assertEqual(len(benign), 4)
            for case in manifest["cases"]:
                self.assertTrue((output / case["file"]).is_file())

    def test_non_empty_output_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "corpus"
            output.mkdir()
            (output / "existing.txt").write_text("keep\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                generate_corpus.generate_corpus(output)


if __name__ == "__main__":
    unittest.main()

