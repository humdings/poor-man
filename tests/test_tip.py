"""The tip footer keeps the Nostr npub and the Lightning address."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NPUB = "npub17z7t6hf6e3xru2lkc79lmkddljnswkn5xz86gppqt7amzvre90kqlew3u8"
LN = "ivoryfireant9@primal.net"
LEAD = "Stack sats? Tip the printer-watcher."


class TipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        cls.script = (ROOT / "js" / "app.js").read_text(encoding="utf-8")
        cls.svg = (ROOT / "img" / "lightning.svg").read_text(encoding="utf-8")
        cls.workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")

    def test_page_and_readme_lock_the_npub_and_the_address(self):
        for text in (self.page, self.readme):
            self.assertIn(NPUB, text)
            self.assertIn(f"https://njump.me/{NPUB}", text)
            self.assertIn(LN, text)
            self.assertIn(LEAD, text)
        self.assertIn("Zap me on Nostr", self.page)
        self.assertIn('src="img/lightning.svg"', self.page)
        self.assertIn(f'data-address="{LN}"', self.page)

    def test_qr_is_a_local_svg_for_the_lightning_address(self):
        self.assertIn(f"<title>lightning:{LN}</title>", self.svg)
        self.assertIn("<svg", self.svg)
        urls = re.findall(r"https?://[^\s\"'<]+", self.svg)
        self.assertEqual(urls, ["http://www.w3.org/2000/svg"])
        self.assertIn("img _site/", self.workflow)

    def test_share_text_does_not_carry_the_tip(self):
        start = self.script.index("function shareSentence()")
        end = self.script.index("function paintShare()")
        sentence = self.script[start:end]
        self.assertNotIn(NPUB, sentence)
        self.assertNotIn(LN, sentence)
        self.assertNotIn("njump.me", sentence)
        self.assertNotIn("printer-watcher", sentence)
        self.assertNotIn(NPUB, self.script)
        self.assertNotIn("njump.me", self.script)


if __name__ == "__main__":
    unittest.main()
