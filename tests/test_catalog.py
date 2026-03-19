from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wt_model_viewer.catalog import build_model_families, split_variant_name
from wt_model_viewer.types import ModelIndexEntry


class CatalogTests(unittest.TestCase):
    def test_splits_known_variant_suffixes(self) -> None:
        self.assertEqual(split_variant_name("ztz_99a"), ("ztz_99a", "default", "default"))
        self.assertEqual(split_variant_name("ztz_99a_dmg"), ("ztz_99a", "dmg", "dmg"))
        self.assertEqual(split_variant_name("ztz_99a_xray"), ("ztz_99a", "xray", "xray"))

    def test_groups_known_variants_under_base_name(self) -> None:
        entries = [
            ModelIndexEntry("ztz_99a", "D:/packs/ground.grp", "content/base/res/ground.grp", 0),
            ModelIndexEntry("ztz_99a_dmg", "D:/packs/ground.grp", "content/base/res/ground.grp", 1),
            ModelIndexEntry("ztz_99a_xray", "D:/packs/ground.grp", "content/base/res/ground.grp", 2),
        ]

        families = build_model_families(entries)

        self.assertEqual(len(families), 1)
        family = families[0]
        self.assertEqual(family.base_name, "ztz_99a")
        self.assertEqual(family.variant_count, 3)
        self.assertEqual(family.default_variant().entry.name, "ztz_99a")
        self.assertEqual([variant.key for variant in family.variants], ["default", "dmg", "xray"])


if __name__ == "__main__":
    unittest.main()
