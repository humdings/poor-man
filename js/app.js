/* Page state, URL, headline, and the assumption panel. Charts live in charts.js. */
(function () {
  var MEASURES = ["m2", "base", "currency", "debt", "fed"];
  var METHODS = ["trailing", "regression", "cagr"];
  var data = null;
  var state = readState();

  var els = {
    kicker: document.getElementById("kicker"),
    days: document.getElementById("days"),
    daysUnit: document.getElementById("days-unit"),
    sentence: document.getElementById("sentence"),
    pace: document.getElementById("pace"),
    asof: document.getElementById("asof"),
    strip: document.getElementById("strip"),
    assumptions: document.getElementById("assumption-list"),
    share: document.getElementById("share"),
    amount: document.getElementById("custom-amount"),
    unit: document.getElementById("custom-unit"),
    log: document.getElementById("log-scale"),
    moneyTitle: document.getElementById("money-title"),
    legend: document.getElementById("legend-money"),
    btcNote: document.getElementById("btc-note"),
    empty: document.getElementById("empty-bailout"),
    sources: document.getElementById("sources"),
    generated: document.getElementById("generated"),
  };

  function readState() {
    var q = new URLSearchParams(location.search);
    var measure = q.get("measure");
    if (MEASURES.indexOf(measure) < 0) measure = "m2";
    var unit = q.get("unit") === "y" ? "y" : "m";
    var amount = parseInt(q.get("window"), 10);
    if (!isFinite(amount)) amount = 12;
    amount = clamp(amount, unit);
    var method = q.get("method");
    if (METHODS.indexOf(method) < 0) method = "trailing";
    var log = q.get("log") === "0" ? false : true;
    return { measure: measure, amount: amount, unit: unit, method: method, log: log };
  }

  function clamp(amount, unit) {
    if (unit === "y") return Math.min(50, Math.max(1, amount));
    return Math.min(600, Math.max(1, amount));
  }

  function writeState() {
    var q = new URLSearchParams();
    q.set("measure", state.measure);
    q.set("window", String(state.amount));
    q.set("unit", state.unit);
    q.set("method", state.method);
    q.set("log", state.log ? "1" : "0");
    history.replaceState(null, "", "?" + q.toString());
  }

  function unitName() {
    return state.unit === "y" ? "year" : "month";
  }

  function windowLabel() {
    var n = state.amount;
    if (state.unit === "y") return n + (n === 1 ? " year" : " years");
    return n + (n === 1 ? " month" : " months");
  }

  function windowAdjective() {
    return state.amount + (state.unit === "y" ? "-year" : "-month");
  }

  function methodName() {
    if (state.method === "regression") return "linear regression";
    if (state.method === "cagr") return "CAGR pace";
    return "trailing change";
  }

  function methodDetail() {
    if (state.method === "regression") {
      return "Linear regression. Growth per day is the slope of the daily forward-filled level across the window. Flat days between prints are part of the fit.";
    }
    if (state.method === "cagr") {
      return "CAGR pace. The compound rate from the start of the window to today, converted to dollars per day at today's level.";
    }
    return "Simple trailing change, the default. Growth per day is (level today − level at the start of the window) ÷ days in the window.";
  }

  function formatDays(n) {
    if (n >= 1000) return Math.round(n).toLocaleString("en-US");
    return n.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  }

  function formatUSD(n) {
    var abs = Math.abs(n);
    var sign = n < 0 ? "−" : "";
    var body;
    if (abs >= 1e12) body = (abs / 1e12).toFixed(2) + " trillion";
    else if (abs >= 1e9) body = (abs / 1e9).toFixed(2) + " billion";
    else if (abs >= 1e6) body = (abs / 1e6).toFixed(2) + " million";
    else body = Math.round(abs).toLocaleString("en-US");
    return sign + "$" + body;
  }

  function measureById(id) {
    return data.measures.filter(function (m) { return m.id === id; })[0];
  }

  function btcPairs() {
    return data.btc.points.map(function (row) { return [row[0], row[1]]; });
  }

  function run(measure) {
    return Pmb.computeBailout(measure.points, btcPairs(), {
      amount: state.amount,
      unit: unitName(),
      method: state.method,
    });
  }

  function sentence(measure, latest) {
    var label = windowLabel();
    var name = measure.name;
    if (!latest || latest.state === "insufficient") {
      return name + " does not cover a full " + label + " before this date, so there is no day count.";
    }
    if (latest.state === "contracting") {
      return name + " did not grow over the trailing " + label + ", using a " + methodName() + ", so the bailout clock is paused. A pace that is not positive is a gap, not a day count.";
    }
    var pace = formatUSD(latest.growthPerDay) + " a day";
    var adj = windowAdjective();
    if (state.method === "trailing") {
      return "At the current pace, the trailing " + adj + " change in " + name + " is about " + pace + ", so the stock grows by one bitcoin market cap every " + formatDays(latest.days) + " days.";
    }
    if (state.method === "regression") {
      return "At the current pace, a " + adj + " linear regression on " + name + " rises about " + pace + ", so the stock grows by one bitcoin market cap every " + formatDays(latest.days) + " days.";
    }
    return "At the current pace, the " + adj + " compound growth of " + name + ", applied at today's level, is about " + pace + ", so the stock grows by one bitcoin market cap every " + formatDays(latest.days) + " days.";
  }

  function paintHeadline(measure, result) {
    var latest = result.points.length ? result.points[result.points.length - 1] : null;
    els.kicker.textContent = measure.name + " · " + windowLabel() + " " + methodName();
    els.days.classList.remove("contracting", "insufficient");
    if (!latest || latest.state === "insufficient") {
      els.days.textContent = "Not enough history";
      els.days.classList.add("insufficient");
      els.daysUnit.hidden = true;
    } else if (latest.state === "contracting") {
      els.days.textContent = "Contracting";
      els.days.classList.add("contracting");
      els.daysUnit.hidden = true;
    } else {
      els.days.textContent = formatDays(latest.days);
      els.daysUnit.hidden = false;
    }
    els.sentence.textContent = sentence(measure, latest);
    if (latest && latest.state === "expanding") {
      els.pace.textContent = "Bitcoin market cap on this date: " + formatUSD(latest.mcap) + ". Level in effect: " + formatUSD(latest.level) + ".";
    } else if (latest && latest.mcap) {
      els.pace.textContent = "Bitcoin market cap on this date: " + formatUSD(latest.mcap) + ".";
    } else {
      els.pace.textContent = "";
    }
    var moneyEnd = measure.end;
    var btcEnd = data.btc.end;
    var headlineDate = latest ? latest.date : "—";
    var carried = [];
    if (latest && moneyEnd < headlineDate) carried.push(measure.short + " last print " + moneyEnd + ", carried forward");
    else carried.push(measure.short + " through " + moneyEnd);
    if (latest && btcEnd < headlineDate) carried.push("bitcoin market cap last print " + btcEnd + ", carried forward");
    else carried.push("bitcoin market cap through " + btcEnd);
    els.asof.textContent = "Headline date " + headlineDate + ". " + carried.join(". ") + ".";
    document.title = (latest && latest.state === "expanding"
      ? formatDays(latest.days) + " days · "
      : "") + "Poor Man's Bailout";

    var plotted = Pmb.toChartData(result.points);
    var hasLine = plotted.some(function (row) { return row.value != null; });
    els.empty.hidden = hasLine;
    els.empty.textContent = hasLine ? "" : "Nothing to plot for this window. The pace is undefined over the whole overlap with bitcoin.";
    return { latest: latest, plotted: plotted };
  }

  function paintStrip(cache) {
    els.strip.innerHTML = "";
    data.measures.filter(function (m) { return m.group === "primary"; }).forEach(function (measure) {
      var result = cache[measure.id];
      var latest = result.points.length ? result.points[result.points.length - 1] : null;
      var li = document.createElement("li");
      var button = document.createElement("button");
      button.type = "button";
      if (measure.id === state.measure) button.className = "on";
      var strong = document.createElement("strong");
      strong.textContent = measure.short;
      button.appendChild(strong);
      var label = document.createElement("span");
      if (!latest || latest.state === "insufficient") label.textContent = "no full window";
      else if (latest.state === "contracting") {
        label.textContent = "contracting";
        label.className = "bad";
      } else label.textContent = formatDays(latest.days) + " days";
      button.appendChild(label);
      button.addEventListener("click", function () {
        state.measure = measure.id;
        render();
      });
      li.appendChild(button);
      els.strip.appendChild(li);
    });
  }

  function addAssumption(term, detail) {
    var dt = document.createElement("dt");
    dt.textContent = term;
    var dd = document.createElement("dd");
    dd.textContent = detail;
    els.assumptions.appendChild(dt);
    els.assumptions.appendChild(dd);
  }

  function paintAssumptions(measure) {
    els.assumptions.innerHTML = "";
    addAssumption("Series", measure.name + " · " + measure.fred_id + " · " + measure.frequency + " · " + measure.seasonal);
    addAssumption("Window", windowLabel() + ", ending on the headline date.");
    addAssumption("Averaging", methodDetail());
    addAssumption("Contraction", "Not plotted. Zero or negative growth is a gap. The day count is never negative and never infinite.");
    addAssumption("Alignment", "Money levels step forward daily. Bitcoin market cap is the print on that date, or the latest print on or before it. The headline date is the later of the two last prints.");
    addAssumption("Units", measure.published_units + ", stored in dollars" + (measure.multiplier > 1 ? " (× " + measure.multiplier.toLocaleString("en-US") + ")." : "."));
  }

  function paintSources() {
    els.sources.innerHTML = "";
    var btc = data.btc;
    els.sources.appendChild(sourceBlock(
      "Bitcoin market cap",
      btc.start + " → " + btc.end + " · " + btc.count.toLocaleString("en-US") + " days",
      btc.retrieval,
      btc.source_url,
      btc.source_name
    ));
    data.measures.forEach(function (measure) {
      els.sources.appendChild(sourceBlock(
        measure.name + " (" + measure.fred_id + ")",
        measure.start + " → " + measure.end + " · " + measure.count.toLocaleString("en-US") + " prints",
        measure.retrieval,
        measure.fred_url,
        "FRED " + measure.fred_id
      ));
    });
    els.generated.textContent = "Snapshot generated " + data.generated_at + ". The page reads this file only.";
  }

  function sourceBlock(title, range, retrieval, href, linkText) {
    var block = document.createElement("div");
    block.className = "source-block";
    var h = document.createElement("h3");
    h.textContent = title;
    var meta = document.createElement("p");
    meta.textContent = range;
    var note = document.createElement("p");
    note.textContent = retrieval + " ";
    var a = document.createElement("a");
    a.href = href;
    a.textContent = linkText;
    note.appendChild(a);
    block.appendChild(h);
    block.appendChild(meta);
    block.appendChild(note);
    return block;
  }

  function syncControls() {
    document.querySelectorAll("[data-measure]").forEach(function (button) {
      button.setAttribute("aria-pressed", button.getAttribute("data-measure") === state.measure ? "true" : "false");
    });
    document.querySelectorAll("[data-window]").forEach(function (button) {
      var on = Number(button.getAttribute("data-window")) === state.amount && button.getAttribute("data-unit") === state.unit;
      button.setAttribute("aria-pressed", on ? "true" : "false");
    });
    document.querySelectorAll("[data-method]").forEach(function (button) {
      button.setAttribute("aria-pressed", button.getAttribute("data-method") === state.method ? "true" : "false");
    });
    els.amount.value = String(state.amount);
    els.unit.value = state.unit;
    els.amount.max = state.unit === "y" ? "50" : "600";
    els.log.checked = state.log;
  }

  function render() {
    state.amount = clamp(state.amount, state.unit);
    writeState();
    syncControls();
    var measure = measureById(state.measure);
    var cache = {};
    data.measures.forEach(function (item) {
      if (item.group === "primary" || item.id === state.measure) cache[item.id] = run(item);
    });
    var painted = paintHeadline(measure, cache[state.measure]);
    paintStrip(cache);
    paintAssumptions(measure);
    els.moneyTitle.textContent = measure.name;
    els.legend.textContent = measure.short;
    var price = data.btc.points[data.btc.points.length - 1][2];
    els.btcNote.textContent = "Log scale. Latest price " + (price != null ? "$" + Number(price).toLocaleString("en-US", { maximumFractionDigits: 2 }) : "unavailable") + ".";
    PmbCharts.render({
      bailout: painted.plotted,
      money: measure.points,
      btc: btcPairs(),
      log: state.log,
    });
  }

  function bind() {
    document.querySelectorAll("[data-measure]").forEach(function (button) {
      button.addEventListener("click", function () {
        state.measure = button.getAttribute("data-measure");
        render();
      });
    });
    document.querySelectorAll("[data-window]").forEach(function (button) {
      button.addEventListener("click", function () {
        state.amount = Number(button.getAttribute("data-window"));
        state.unit = button.getAttribute("data-unit");
        render();
      });
    });
    document.querySelectorAll("[data-method]").forEach(function (button) {
      button.addEventListener("click", function () {
        state.method = button.getAttribute("data-method");
        render();
      });
    });
    function fromCustom() {
      var amount = parseInt(els.amount.value, 10);
      if (!isFinite(amount)) return;
      state.amount = amount;
      state.unit = els.unit.value === "y" ? "y" : "m";
      render();
    }
    els.amount.addEventListener("change", fromCustom);
    els.unit.addEventListener("change", fromCustom);
    els.log.addEventListener("change", function () {
      state.log = els.log.checked;
      writeState();
      PmbCharts.setLog(state.log);
    });
    els.share.addEventListener("click", function () {
      var url = location.href;
      function done(label) {
        els.share.textContent = label;
        setTimeout(function () { els.share.textContent = "Copy link"; }, 1400);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(function () { done("Copied"); }, function () { done("Copy the address bar"); });
      } else {
        done("Copy the address bar");
      }
    });
  }

  function fail(message) {
    els.days.textContent = "Unavailable";
    els.days.classList.add("insufficient");
    els.daysUnit.hidden = true;
    els.sentence.textContent = message;
  }

  fetch("data/series.json")
    .then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    })
    .then(function (doc) {
      data = doc;
      bind();
      paintSources();
      render();
    })
    .catch(function () {
      fail("The data snapshot did not load. From a local checkout, serve the repo root (python3 -m http.server) and open the site from there.");
    });
})();
