"""OpenAPI contract snapshot: refactoring must not change the public API.

The snapshot lives in ``tests/fixtures/openapi.json``. To accept an intentional
API change, regenerate it::

    UPDATE_OPENAPI_SNAPSHOT=1 python -m unittest tests.test_openapi_snapshot
"""

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SNAPSHOT = Path(__file__).parent / "fixtures" / "openapi.json"


def load_openapi() -> dict:
    """Build the real app schema without a database or developer secrets."""
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    os.environ.setdefault("JWT_SECRET", "snapshot-test-secret")
    os.environ.setdefault("APK_STORAGE_PATH", tempfile.mkdtemp(prefix="apk-"))
    sys.modules.pop("main", None)
    main = importlib.import_module("main")
    return json.loads(json.dumps(main.app.openapi()))


def dump(spec: dict) -> str:
    return json.dumps(spec, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


class OpenApiSnapshot(unittest.TestCase):
    def test_openapi_matches_snapshot(self):
        spec = load_openapi()
        if os.getenv("UPDATE_OPENAPI_SNAPSHOT") == "1":
            SNAPSHOT.write_text(dump(spec), encoding="utf-8")
        expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        self.assertEqual(
            expected,
            spec,
            "OpenAPI изменился. Если изменение намеренное, обновите снимок: "
            "UPDATE_OPENAPI_SNAPSHOT=1 python -m unittest tests.test_openapi_snapshot",
        )

    def test_snapshot_has_all_route_groups(self):
        paths = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["paths"]
        for prefix in (
            "/compute",
            "/optimize-cost",
            "/optimize-recipe",
            "/reference-proteins",
            "/products",
            "/saved",
            "/auth",
            "/users",
        ):
            self.assertTrue(
                any(path.startswith(prefix) or prefix in path for path in paths),
                f"в снимке нет маршрутов {prefix}",
            )


if __name__ == "__main__":
    unittest.main()
