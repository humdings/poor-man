"""The share image and the tags that point at it.

The nightly job draws data/og.png from the snapshot: default M2 days, and
the latest positive trailing-CPI half-life. The page carries Open Graph
and Twitter card tags for that file, and the share buttons build a
sentence from the numbers on screen.
"""

import json
import sys
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from metric import half_life_years  # noqa: E402
from share_card import (  # noqa: E402
    HEIGHT,
    OUT,
    WIDTH,
    card_facts,
    format_card_number,
    write_share_card,
)

DATA = ROOT / "data" / "series.json"
PAGE = "https://humdings.github.io/poor-man/data/og.png"


@unittest.skipUnless(DATA.exists(), "snapshot not built yet")
class ShareCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(DATA.read_text(encoding="utf-8"))
        cls.facts = card_facts(cls.doc)

    def test_two_percent_and_seven_percent_round_like_the_page(self):
        self.assertEqual(format_card_number(half_life_years(0.02)), "35.0")
        self.assertEqual(format_card_number(half_life_years(0.07)), "10.2")

    def test_facts_are_the_default_m2_days_and_a_real_half_life(self):
        m2 = next(row for row in self.doc["headlines_default"] if row["id"] == "m2")
        self.assertEqual(self.facts["state"], "expanding")
        self.assertEqual(self.facts["days_label"], format_card_number(m2["days"]))
        self.assertGreater(m2["days"], 0)
        self.assertIsNotNone(self.facts["half_label"])
        self.assertEqual(self.facts["half_label"], format_card_number(self.facts["half_life"]))
        self.assertGreater(self.facts["half_life"], 5)
        self.assertLess(self.facts["half_life"], 80)

    def test_generation_writes_a_png_with_those_numbers(self):
        path = ROOT / "data" / "og-test.png"
        try:
            facts = write_share_card(self.doc, path)
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\x89PNG\r\n\x1a\n"))
            with Image.open(path) as image:
                self.assertEqual(image.format, "PNG")
                self.assertEqual(image.size, (WIDTH, HEIGHT))
                self.assertEqual(image.text["days"], facts["days_label"])
                self.assertEqual(image.text["half_life"], facts["half_label"])
                self.assertEqual(image.text["headline_date"], facts["date"])
            self.assertEqual(facts["days_label"], self.facts["days_label"])
            self.assertEqual(facts["half_label"], self.facts["half_label"])
        finally:
            path.unlink(missing_ok=True)

    def test_committed_card_matches_the_snapshot(self):
        self.assertTrue(OUT.exists(), "data/og.png is missing; the nightly job commits it beside series.json")
        with Image.open(OUT) as image:
            self.assertEqual(image.size, (WIDTH, HEIGHT))
            self.assertEqual(image.text["days"], self.facts["days_label"])
            self.assertEqual(image.text["half_life"], self.facts["half_label"])
            self.assertEqual(image.text["half_date"], self.facts["half_date"])

    def test_meta_tags_point_at_the_card(self):
        page = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn(f'<meta property="og:image" content="{PAGE}">', page)
        self.assertIn('<meta property="og:image:width" content="1200">', page)
        self.assertIn('<meta property="og:image:height" content="630">', page)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', page)
        self.assertIn(f'<meta name="twitter:image" content="{PAGE}">', page)
        self.assertIn('id="share"', page)
        self.assertIn('id="share-x"', page)
        self.assertIn('id="share-half"', page)
        self.assertIn('id="share-half-x"', page)

    def test_share_sentence_and_the_nightly_commit(self):
        script = (ROOT / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn(
            "The Poor Man's Bailout: the money printer makes a whole bitcoin market cap every ",
            script,
        )
        self.assertIn("Your dollar's half-life: ", script)
        self.assertIn("https://twitter.com/intent/tweet?text=", script)
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        self.assertIn("data/og.png", workflow)
        self.assertIn("pillow", workflow)


if __name__ == "__main__":
    unittest.main()
