from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = {
    "indie_editorial_100.py": 100,
    "fashion_moodboard_80.py": 80,
    "album_cover_directions_40.py": 40,
    "character_silhouettes_64.py": 64,
    "package_concepts_50.py": 50,
    "interior_directions_48.py": 48,
    "product_hero_shots_24.py": 24,
    "marketplace_thumbnails_32.py": 32,
    "detail_closeups_20.py": 20,
    "color_variant_lineup_18.py": 18,
    "lifestyle_product_scenes_24.py": 24,
    "seasonal_campaign_banners_16.py": 16,
    "bundle_set_compositions_16.py": 16,
    "beauty_cosmetics_shots_24.py": 24,
    "food_beverage_shots_24.py": 24,
    "home_living_scenes_24.py": 24,
    "apparel_catalog_looks_28.py": 28,
}


class PackagedExampleTests(unittest.TestCase):
    def test_every_packaged_example_has_a_working_help_surface(self):
        for name in [*EXAMPLES, "batch_100_variations.py", "single_mpw_enhanced.py"]:
            with self.subTest(name=name):
                completed = subprocess.run(
                    [sys.executable, str(ROOT / "examples" / name), "--help"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn("--execute", completed.stdout)

    def test_presets_declare_distinct_counts_and_text_only_concepts(self):
        for name, count in EXAMPLES.items():
            with self.subTest(name=name):
                source = (ROOT / "examples" / name).read_text(encoding="utf-8")
                self.assertIn(f"count={count}", source)
                self.assertIn("prompt=", source)
                self.assertIn("style=", source)
                self.assertNotIn("--image", source)


if __name__ == "__main__":
    unittest.main()
