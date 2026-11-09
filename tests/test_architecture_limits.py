"""Size limits for production modules (ratchet).

A module over MAX_LINES must be listed in OVERSIZED with its current size. The
size may only shrink; new oversized modules are not allowed. When a file is
split, remove it from OVERSIZED (see docs/architecture-god-files-solid.md).
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ("api", "application", "domain", "infrastructure", "core", "features")
MAX_LINES = 400

OVERSIZED = {}


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


class ModuleSizeLimits(unittest.TestCase):
    def modules(self):
        for package in PACKAGES:
            for path in sorted((ROOT / package).rglob("*.py")):
                yield path.relative_to(ROOT).as_posix(), path

    def test_no_new_oversized_modules(self):
        too_big = [
            f"{rel}: {line_count(path)} строк"
            for rel, path in self.modules()
            if line_count(path) > MAX_LINES and rel not in OVERSIZED
        ]
        self.assertEqual(
            [], too_big, f"модуль длиннее {MAX_LINES} строк — разделите его"
        )

    def test_oversized_modules_do_not_grow(self):
        grown = []
        for rel, limit in OVERSIZED.items():
            path = ROOT / rel
            self.assertTrue(path.exists(), f"{rel} удалён: уберите из OVERSIZED")
            size = line_count(path)
            if size > limit:
                grown.append(f"{rel}: {size} > {limit}")
            elif size <= MAX_LINES:
                grown.append(f"{rel}: {size} строк, уберите из OVERSIZED")
        self.assertEqual([], grown)


if __name__ == "__main__":
    unittest.main()
