/* Every card once, and the Morgan / Saylor / IOU trio stays adjacent, in order. */
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const Quotes = require("../js/quotes.js");

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");
const openAt = html.indexOf('<div class="quote-set" id="quote-set">');
if (openAt < 0) fail("quote-set missing");
const setHtml = balanced(html, openAt);
const units = topLevel(setHtml.slice(setHtml.indexOf(">") + 1, setHtml.lastIndexOf("</div>")));
if (units.length < 3) fail("too few units");

const flat = units.flat();
const trio = units.find((unit) => Array.isArray(unit));
if (!trio) fail("trio missing from the page");
if (trio.length !== 3) fail("trio length " + trio.length);
if (!trio[0].includes("Money is gold, and nothing else.")) fail("trio does not open with Morgan");
if (!trio[1].includes("Fiat monetized political credit.")) fail("Saylor is not second");
if (!trio[2].includes("That's as good as money, sir. Those are I.O.U.'s.")) fail("IOU is not third");

const seenOrders = new Set();
for (let seed = 1; seed <= 40; seed++) {
  const set = fakeSet(units);
  Quotes.shuffleQuoteStrip(set, mulberry32(seed));
  const order = flatten(set);
  if (order.length !== flat.length) fail("length changed at seed " + seed);
  const counts = new Map();
  for (const text of order) counts.set(text, (counts.get(text) || 0) + 1);
  for (const text of flat) {
    if (counts.get(text) !== 1) fail("card not present once at seed " + seed);
  }
  const morgan = order.findIndex((text) => text.includes("Money is gold, and nothing else."));
  if (morgan < 0) fail("Morgan missing at seed " + seed);
  if (!order[morgan + 1].includes("Fiat monetized political credit.")) {
    fail("Saylor left the trio at seed " + seed);
  }
  if (!order[morgan + 2].includes("That's as good as money, sir. Those are I.O.U.'s.")) {
    fail("IOU left the trio at seed " + seed);
  }
  const trioNode = set.children.find((node) => node.trio);
  if (!trioNode) fail("trio node split at seed " + seed);
  if (trioNode.children.map((kid) => kid.text).join("\n") !== trio.join("\n")) {
    fail("trio reordered internally at seed " + seed);
  }
  seenOrders.add(order.join("\n"));
}
if (seenOrders.size < 2) fail("shuffle did not change the order");
console.log("ok " + flat.length + " cards, " + seenOrders.size + " orders");

function fail(message) {
  console.error(message);
  process.exit(1);
}

function balanced(source, openAt) {
  let depth = 0;
  let i = openAt;
  while (i < source.length) {
    if (source.startsWith("<div", i)) {
      depth += 1;
      i += 4;
      continue;
    }
    if (source.startsWith("</div>", i)) {
      depth -= 1;
      i += 6;
      if (depth === 0) return source.slice(openAt, i);
      continue;
    }
    i += 1;
  }
  fail("unbalanced quote-set");
}

function topLevel(inner) {
  const units = [];
  let i = 0;
  while (i < inner.length) {
    const fig = inner.indexOf("<figure", i);
    const div = inner.indexOf("<div", i);
    if (fig < 0 && div < 0) break;
    if (div >= 0 && (fig < 0 || div < fig)) {
      const block = balanced(inner, div);
      units.push(quotesIn(block));
      i = div + block.length;
    } else {
      const end = inner.indexOf("</figure>", fig);
      units.push(quotesIn(inner.slice(fig, end + 9))[0]);
      i = end + 9;
    }
  }
  return units;
}

function quotesIn(block) {
  return [...block.matchAll(/<blockquote><p>([\s\S]*?)<\/p><\/blockquote>/g)].map((match) => match[1]);
}

function fakeSet(units) {
  const children = units.map((unit) => {
    if (Array.isArray(unit)) {
      return { trio: true, children: unit.map((text) => ({ text: text, children: [] })) };
    }
    return { text: unit, children: [] };
  });
  return {
    children: children,
    appendChild(node) {
      const at = children.indexOf(node);
      if (at >= 0) children.splice(at, 1);
      children.push(node);
      return node;
    },
  };
}

function flatten(set) {
  const out = [];
  for (const child of set.children) {
    if (child.trio) {
      for (const kid of child.children) out.push(kid.text);
    } else out.push(child.text);
  }
  return out;
}

function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
