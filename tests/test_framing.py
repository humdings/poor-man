"""The framing and the quotes stay verbatim, and the spurious line stays out."""

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "One path among many.",
    "Bitcoin is a choice each person can make, or leave alone.",
    "not a destination anyone needs to reach.",
    "the price is volatile, custody is your own, and there is a real learning curve.",
    "Don't forget to enjoy the journey.",
    "To a bitcoiner, debasement is a slow-motion bailout.",
    "That is one way of seeing it, not a call to act.",
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
    "All warfare is based on deception.",
    "bad money drives out good money, but that good money cannot drive out bad money.",
    "By a continuing process of inflation, governments can confiscate, secretly and unobserved, an important part of the wealth of their citizens.",
    "The first panacea for a mismanaged nation is inflation of the currency; the second is war.",
    "September 1935",
    "Money is gold, and nothing else.",
    "Gold is money. Everything else is credit.",
    "Gold monetized physical scarcity. Fiat monetized political credit. Bitcoin monetizes digital scarcity.",
    "sound money, limits on power, no taxation without consent",
    "That is our view, not a line they wrote, and still one path among many.",
    "You can tell everybody to go fuck themselves.",
    "I lost it in a boating accident.",
    "Attributed to Voltaire",
    "Paper money eventually returns to its intrinsic value: zero.",
    "is the one form of taxation that can be imposed without legislation.",
    "Milton Friedman, AEI round table, 17 July 1974",
    "https://www.aei.org/wp-content/uploads/2016/03/AEIRoundTable05.pdf",
    "is a paraphrase.",
    "So I think we need a roundabout way.",
    "Bitcoin isn\u2019t strictly a monetary protocol.",
    "Bitcoin is proof that proof-of-work works.",
    "cyber power projection tactic for the digital age.",
    "That's not a knife. That's a knife.",
    "all forms of monetary entropy. They drain energy from the system.",
    "Good money conserves energy. Bad money dissipates it.",
    "https://www.michael.com/articles/what-is-money",
    "greed, for lack of a better word, is good.",
    "There is no spoon.",
    "Excuse me. I believe you have my stapler.",
    "be first, be smarter, or cheat.",
    "So you're telling me there's a chance.",
    "Are you not entertained?",
    "We landed on the moon!",
    "That's as good as money, sir. Those are I.O.U.'s.",
    "no private man shall be allowed to possess gold and silver",
    "not accepted among the rest of mankind",
    "the villain's view",
    "that which is an obstacle on the road helps us on this road.",
    "Marcus Aurelius, and all HODLers",
    "He that loveth silver shall not be satisfied with silver",
    "Ecclesiastes, and 2026 silver holders",
    "A false balance is abomination to the LORD: but a just weight is his delight.",
    "Thy silver is become dross, thy wine mixed with water:",
    "Divers weights, and divers measures, both of them are alike abomination to the LORD.",
    "making the ephah small, and the shekel great",
    "the bag of deceitful weights",
    "Ye shall have just balances, and a just ephah, and a just bath.",
    "This System of banks begotten, hatched and brooded by Duer, Robert and Governeur Morris",
    "There is no honest Money but Silver and Gold.",
    "paper is poverty, that it is only the ghost of money, and not money itself.",
    "foisting their own paper into circulation, and thus banishing our cash.",
    "a favorable crisis for crushing paper money",
    "cut off the pretext for a paper currency",
    "Paper money can in no case be necessary.",
    "wisely prohibited to the individual States, by the National Constitution.",
    "the Depreciation is quicker",
    "Gold and silver are the emissions of nature: paper is the emission of art.",
    "https://founders.archives.gov/documents/Adams/99-02-02-6198",
    "https://founders.archives.gov/documents/Adams/99-02-02-5585",
    "https://founders.archives.gov/documents/Jefferson/01-13-02-0120",
    "https://founders.archives.gov/documents/Jefferson/03-07-02-0083",
    "https://avalon.law.yale.edu/18th_century/debates_828.asp",
    "https://avalon.law.yale.edu/18th_century/debates_816.asp",
    "https://founders.archives.gov/documents/Hamilton/01-07-02-0229-0003",
    "https://founders.archives.gov/documents/Franklin/01-34-02-0156",
    "https://mises.org/mises-daily/thomas-paine-paper-money",
]

# The circulating line attributed to Jefferson about private banks and a
# sequence of inflation and deflation. Monticello marks it spurious.
FORBIDDEN = [
    "private banks",
    "homeless on the continent",
    "banking institutions are more dangerous to our liberties",
    "6 November 1813",
    "problem with socialism",
    "ship with no anchor",
    "I do not think it means what you think it means",
    "bigger boat",
    "good money again",
    "I thought you couldn't possibly be any dumber",
    "That's an IOU. It's as good as money",
    "totally redeem yourself",
    "Harry Dunne",
    "Aristotle",
    "Seneca",
    "The impediment to action advances action",
    "What stands in the way becomes the way",
    "The dollar holds.",
    "Bitcoin is more American than the Dollar",
    "A bailout used to need a vote",
    "where we need to go",
    "Quran",
    "quran.com",
    "little tax on tea",
    "colonial scrip",
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

    def test_the_friedman_card_quotes_the_aei_sentence(self):
        for text in (self.page, self.readme):
            self.assertNotIn("Attributed to Milton Friedman", text)
            self.assertNotIn("No source in his own words has been found", text)
        sentence = "It is the one form of taxation that can be imposed without legislation."
        card = self.page.split(sentence, 1)[0].rsplit("<figure", 1)[1] + sentence
        card += self.page.split(sentence, 1)[1].split("</figure>", 1)[0]
        quote = card.split("<blockquote>", 1)[1].split("</blockquote>", 1)[0]
        self.assertIn(sentence, quote)
        self.assertNotIn("Inflation is taxation without legislation", quote)
        self.assertIn("Inflation is taxation without legislation", card)
        self.assertIn("is a paraphrase.", card)
        self.assertNotIn("quote-flag", card)
        self.assertNotIn("flagged", card)

    def test_the_frogs_and_the_big_short_cards_are_gone(self):
        for text in (self.page, self.readme):
            self.assertNotIn("Mark Baum", text)
            self.assertNotIn("The Big Short", text)
            self.assertNotIn("Aristophanes", text)
            self.assertNotIn("The Frogs", text)
            self.assertNotIn("pinchbeck", text)

    def test_the_chance_card_headline_is_the_whitepaper(self):
        card = self.page.split("So you're telling me there's a chance.", 1)[0].rsplit("<figure", 1)[1]
        card += self.page.split("So you're telling me there's a chance.", 1)[1].split("</figure>", 1)[0]
        self.assertIn("Satoshi drops a whitepaper", card)
        self.assertIn("Lloyd Christmas", card)
        self.assertIn("Dumb and Dumber", card)
        self.assertNotIn("The dollar holds.", card)

    def test_the_page_scrolls_the_quotes(self):
        self.assertIn('class="quote-strip"', self.page)
        self.assertIn("quote-marquee", (ROOT / "css" / "styles.css").read_text(encoding="utf-8"))
        hero = self.page.split('<section class="hero">', 1)[1].split('<section class="split-section"', 1)[0]
        column = hero.split('<div class="hero-col">', 1)[1].split('<aside class="assumptions"', 1)[0]
        self.assertLess(column.index('id="share"'), column.index('id="quote-strip"'))
        self.assertIn("hero-col", hero)
        self.assertIn("hero-quotes", hero)

    def test_the_founders_comment_is_the_sites_own_view(self):
        section = self.page.split('id="quotes-title"', 1)[1].split('id="quote-strip"', 1)[0]
        self.assertIn("sound money, limits on power, no taxation without consent", section)
        self.assertIn("That is our view, not a line they wrote", section)
        self.assertNotIn("<blockquote", section)
        self.assertNotIn("<figure", section)
        strip = self.page.split('id="quote-set"', 1)[1].split("</div>", 1)[0]
        self.assertNotIn("sound money, limits on power", strip)

    def test_morgan_sits_immediately_before_the_saylor_line(self):
        sentence = "Gold monetized physical scarcity. Fiat monetized political credit. Bitcoin monetizes digital scarcity."
        for text in (self.page, self.readme):
            morgan = text.index("Money is gold, and nothing else.")
            paraphrase = text.index("Gold is money. Everything else is credit.")
            saylor = text.index(sentence)
            iou = text.index("That's as good as money, sir. Those are I.O.U.'s.")
            self.assertLess(morgan, paraphrase)
            self.assertLess(paraphrase, saylor)
            self.assertLess(saylor, iou)
            self.assertNotIn("Michael Saylor (paraphrase)", text)
            self.assertNotIn("Bitcoin is money, everything else is credit.", text)
            moon = text.index("We landed on the moon!")
            self.assertIn("Lloyd Christmas", text[moon:moon + 400])
            entropy = text.index("all forms of monetary entropy")
            self.assertNotEqual(entropy, saylor)
        trio = self.page.split('class="quote-trio"', 1)[1].split("</div>", 1)[0]
        self.assertLess(trio.index("Money is gold, and nothing else."), trio.index(sentence))
        self.assertLess(trio.index(sentence), trio.index("That's as good as money, sir. Those are I.O.U.'s."))
        self.assertNotIn("paraphrase", trio[trio.index(sentence):])
        self.assertIn("featured", trio)

    def test_shuffle_keeps_every_card_once_and_the_trio_in_order(self):
        css = (ROOT / "css" / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".quote-strip:hover .quote-track", css)
        self.assertIn("animation-play-state: paused", css)
        runner = ROOT / "tests" / "quote_shuffle.mjs"
        done = subprocess.run(
            ["node", str(runner)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stderr or done.stdout)
        self.assertIn("ok ", done.stdout)

    def test_the_data_axiom_stays_with_the_formula(self):
        for text in (self.page, self.readme):
            self.assertIn(
                "Money spends the same, so expansion in any form counts as expansion.",
                text,
            )
