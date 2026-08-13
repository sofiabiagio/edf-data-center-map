from pathlib import Path
import hashlib
import json
import sys
import unittest


CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from build_phase_zero_map import (  # noqa: E402
    SUBSTATION_MANIFEST_PATH,
    SUBSTATION_SNAPSHOT_PATH,
    load_substation_snapshot,
)


class SubstationSnapshotTests(unittest.TestCase):
    def test_snapshot_matches_manifest_and_is_complete(self):
        manifest = json.loads(SUBSTATION_MANIFEST_PATH.read_text(encoding="utf-8"))
        digest = hashlib.sha256(SUBSTATION_SNAPSHOT_PATH.read_bytes()).hexdigest()
        self.assertEqual(digest, manifest["sha256"])
        self.assertEqual(len(load_substation_snapshot()), manifest["feature_count"])
        self.assertGreaterEqual(manifest["feature_count"], 4_000)
        self.assertTrue(manifest["source_url"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
