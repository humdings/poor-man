/* Shuffle the quote strip on each visit. A child that is itself a group
   (the Morgan, Saylor, IOU trio) moves as one unit and keeps its order. */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.PmbQuotes = api;
  if (typeof document !== "undefined") api.bootQuoteStrip();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function fisherYates(items, random) {
    var rand = random || Math.random;
    var arr = items.slice();
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(rand() * (i + 1));
      var tmp = arr[i];
      arr[i] = arr[j];
      arr[j] = tmp;
    }
    return arr;
  }

  function shuffleQuoteStrip(set, random) {
    var units = Array.prototype.slice.call(set.children);
    var shuffled = fisherYates(units, random);
    for (var i = 0; i < shuffled.length; i++) set.appendChild(shuffled[i]);
    return set;
  }

  function bootQuoteStrip() {
    var set = document.getElementById("quote-set");
    var track = document.getElementById("quote-track");
    var strip = document.getElementById("quote-strip");
    if (!set || !track || !strip) return;
    shuffleQuoteStrip(set);
    var clone = set.cloneNode(true);
    clone.removeAttribute("id");
    clone.setAttribute("aria-hidden", "true");
    track.appendChild(clone);
    track.classList.add("is-looping");
    strip.classList.add("is-looping");
  }

  return {
    fisherYates: fisherYates,
    shuffleQuoteStrip: shuffleQuoteStrip,
    bootQuoteStrip: bootQuoteStrip,
  };
});
