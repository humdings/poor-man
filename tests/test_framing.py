"""The framing and the quotes stay verbatim, and the spurious line stays out."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "Bitcoin is more American than the Dollar!",
    "To a bitcoiner, debasement is a slow-motion bailout.",
    "A bailout used to need a vote. Now it just needs time.",
    "Fewer days means the printer is outrunning bitcoin; more days means bitcoin is outrunning the printer.",
    "banking establishments are more dangerous than standing armies",
    "swindling futurity on a large scale",
    "Bank-paper must be suppressed, and the circulating medium must be restored to the nation to whom it belongs.",
    "11 September 1813",
    "make any Thing but gold and silver Coin a Tender in Payment of Debts",
    "pestilent effects of paper money",
    "Paper money has had the effect in your State that it ever will have, to ruin commerce—oppress the honest, and open a door to every species of fraud and injustice.",
    "They always run out of other people's money.",
    "inflation is always and everywhere a monetary phenomenon in the sense that it is and can be produced only by a more rapid increase in the quantity of money than in output.",
    "https://founders.archives.gov/documents/Jefferson/03-10-02-0053",
    "https://founders.archives.gov/documents/Jefferson/03-06-02-0388",
    "https://www.archives.gov/founding-docs/constitution-transcript",
    "https://avalon.law.yale.edu/18th_century/fed44.asp",
    "https://founders.archives.gov/documents/Washington/04-04-02-0428",
    "https://www.margaretthatcher.org/document/102953",
    "https://miltonfriedman.hoover.org/internal/media/dispatcher/214480/full",
]

# The circulating line attributed to Jefferson about private banks and a
# sequence of inflation and deflation. Monticello marks it spurious.
FORBIDDEN = [
    "private banks",
    "homeless on the continent",
    "banking institutions are more dangerous to our liberties",
    "6 November 1813",
    "problem with socialism",
]


class FramingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_page_and_readme_carry_the_verified_lines(self):
        for text in REQUIRED:
            self.assertIn(text, self.page, text)
            self.assertIn(text, self.readme, text)

    def test_spurious_and_paraphrase_lines_stay_out(self):
        for text in FORBIDDEN:
            self.assertNotIn(text, self.page, text)
            self.assertNotIn(text, self.readme, text)

    def test_the_data_axiom_stays_with_the_formula(self):
        for text in (self.page, self.readme):
            self.assertIn(
                "Money spends the same, so expansion in any form counts as expansion.",
                text,
            )
