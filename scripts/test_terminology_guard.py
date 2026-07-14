import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = {".md", ".py", ".mjs", ".json", ".jsonl", ".yaml", ".yml"}
FORBIDDEN = [
    "Lu" + "na",
    "gemini" + "-lu" + "na",
    "gpt-5.6" + "-lu" + "na",
    "browser" + "_gpt",
    "browser" + "-gpt",
    "HEITUZ_BROWSER" + "_ADAPTER_SCRIPT",
    "HERMES" + "_IMAGE_",
    "HERMES" + "_GEMINI_",
    "send" + "_message",
    "Tele" + "gram",
]


class TerminologyGuardTests(unittest.TestCase):
    def test_public_source_has_no_legacy_runtime_vocabulary(self):
        failures = []
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            relative = path.relative_to(ROOT)
            if any(part.startswith(".") or part in {"node_modules", "__pycache__"} for part in relative.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for term in FORBIDDEN:
                if term.lower() in text:
                    failures.append(f"{path.relative_to(ROOT)}: {term}")
        self.assertEqual([], failures)


if __name__ == "__main__":
    unittest.main()
