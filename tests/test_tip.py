"""The tip footer keeps the Nostr npub, the Lightning address, and the on-chain address."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NPUB = "npub17z7t6hf6e3xru2lkc79lmkddljnswkn5xz86gppqt7amzvre90kqlew3u8"
LN = "ivoryfireant9@primal.net"
BTC = "bc1qyut5d3gmlf2lnuntl7aqx3l89sjd6m0ewzs845"
LEAD = "Stack sats? Tip the printer-watcher."
CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
BECH32_CONST = 1


def _polymod(values):
    generators = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for value in values:
        top = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ value
        for i in range(5):
            if (top >> i) & 1:
                chk ^= generators[i]
    return chk


def _hrp_expand(hrp):
    return [ord(char) >> 5 for char in hrp] + [0] + [ord(char) & 31 for char in hrp]


def _convertbits(data, from_bits, to_bits, pad):
    acc = 0
    bits = 0
    out = []
    max_value = (1 << to_bits) - 1
    max_acc = (1 << (from_bits + to_bits - 1)) - 1
    for value in data:
        if value < 0 or value >> from_bits:
            return None
        acc = ((acc << from_bits) | value) & max_acc
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            out.append((acc >> bits) & max_value)
    if pad:
        if bits:
            out.append((acc << (to_bits - bits)) & max_value)
    elif bits >= from_bits or ((acc << (to_bits - bits)) & max_value):
        return None
    return out


def decode_segwit(address):
    """BIP173 bech32. Witness version 0 only; v1 and later use bech32m."""
    if address.lower() != address and address.upper() != address:
        return None
    address = address.lower()
    split = address.rfind("1")
    if split < 1 or split + 7 > len(address):
        return None
    hrp, coded = address[:split], address[split + 1 :]
    if any(char not in CHARSET for char in coded):
        return None
    data = [CHARSET.find(char) for char in coded]
    if _polymod(_hrp_expand(hrp) + data) != BECH32_CONST:
        return None
    if hrp != "bc" or not data or data[0] != 0:
        return None
    program = _convertbits(data[1:-6], 5, 8, False)
    if program is None or len(program) not in (20, 32):
        return None
    return hrp, data[0], bytes(program)


class TipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        cls.script = (ROOT / "js" / "app.js").read_text(encoding="utf-8")
        cls.svg = (ROOT / "img" / "lightning.svg").read_text(encoding="utf-8")
        cls.onchain = (ROOT / "img" / "onchain.svg").read_text(encoding="utf-8")
        cls.workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")

    def test_page_and_readme_lock_the_npub_and_the_address(self):
        for text in (self.page, self.readme):
            self.assertIn(NPUB, text)
            self.assertIn(f"https://njump.me/{NPUB}", text)
            self.assertIn(LN, text)
            self.assertIn(BTC, text)
            self.assertIn(LEAD, text)
        self.assertIn("Zap me on Nostr", self.page)
        self.assertIn('src="img/lightning.svg"', self.page)
        self.assertIn(f'data-address="{LN}"', self.page)
        self.assertIn(f'data-address="{BTC}"', self.page)
        self.assertIn('src="img/onchain.svg"', self.page)

    def test_qr_is_a_local_svg_for_the_lightning_address(self):
        self.assertIn(f"<title>lightning:{LN}</title>", self.svg)
        self.assertIn("<svg", self.svg)
        urls = re.findall(r"https?://[^\s\"'<]+", self.svg)
        self.assertEqual(urls, ["http://www.w3.org/2000/svg"])
        self.assertIn("img _site/", self.workflow)

    def test_onchain_address_is_valid_bech32(self):
        decoded = decode_segwit(BTC)
        self.assertIsNotNone(decoded)
        hrp, version, program = decoded
        self.assertEqual(hrp, "bc")
        self.assertEqual(version, 0)
        self.assertEqual(len(program), 20)
        # BIP173 vector, so a broken checksum routine cannot pass by accident.
        spec = decode_segwit("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")
        self.assertIsNotNone(spec)
        self.assertEqual(len(spec[2]), 20)
        self.assertIsNone(decode_segwit("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t5"))
        self.assertIsNone(decode_segwit(BTC[:-1] + ("4" if BTC[-1] != "4" else "5")))
        self.assertIsNone(decode_segwit("BC1" + BTC[3:8] + BTC[8:].upper()))

    def test_onchain_qr_is_a_local_svg(self):
        self.assertIn(f"<title>bitcoin:{BTC}</title>", self.onchain)
        self.assertIn("<svg", self.onchain)
        urls = re.findall(r"https?://[^\s\"'<]+", self.onchain)
        self.assertEqual(urls, ["http://www.w3.org/2000/svg"])

    def test_share_text_does_not_carry_the_tip(self):
        start = self.script.index("function shareSentence()")
        end = self.script.index("function paintShare()")
        sentence = self.script[start:end]
        self.assertNotIn(NPUB, sentence)
        self.assertNotIn(LN, sentence)
        self.assertNotIn(BTC, sentence)
        self.assertNotIn("njump.me", sentence)
        self.assertNotIn("printer-watcher", sentence)
        self.assertNotIn(NPUB, self.script)
        self.assertNotIn(BTC, self.script)
        self.assertNotIn("njump.me", self.script)


if __name__ == "__main__":
    unittest.main()
