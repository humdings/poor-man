/* Page state, URL, headline, and the assumption panel. Charts live in charts.js. */
(function () {
  var MEASURES = ["m2", "base", "currency", "debt", "fed"];
  var METHODS = ["trailing", "regression", "cagr"];
  var data = null;
  var shareHalfYears = null;
  var teaseTimer = null;
  var state = readState();

  var els = {
    kicker: document.getElementById("kicker"),
    days: document.getElementById("days"),
    daysUnit: document.getElementById("days-unit"),
    sentence: document.getElementById("sentence"),
    pace: document.getElementById("pace"),
    asof: document.getElementById("asof"),
    split: document.getElementById("split"),
    strip: document.getElementById("strip"),
    assumptions: document.getElementById("assumption-list"),
    share: document.getElementById("share"),
    shareX: document.getElementById("share-x"),
    shareHalf: document.getElementById("share-half"),
    shareHalfX: document.getElementById("share-half-x"),
    amount: document.getElementById("custom-amount"),
    unit: document.getElementById("custom-unit"),
    log: document.getElementById("log-scale"),
    normalize: document.getElementById("normalize"),
    normSeries: document.getElementById("norm-series"),
    moneyTitle: document.getElementById("money-title"),
    legend: document.getElementById("legend-money"),
    bsGap: document.getElementById("bs-gap"),
    bsGapNum: document.getElementById("bs-gap-num"),
    bsPresets: document.getElementById("bs-presets"),
    bsTable: document.getElementById("bs-table"),
    bsTease: document.getElementById("bs-tease"),
    bsReveal: document.getElementById("bs-reveal"),
    honest: document.getElementById("honest"),
    btcNote: document.getElementById("btc-note"),
    paceNote: document.getElementById("pace-note"),
    empty: document.getElementById("empty-bailout"),
    sources: document.getElementById("sources"),
    generated: document.getElementById("generated"),
  };

  function readState() {
    var q = new URLSearchParams(location.search);
    var measure = q.get("measure");
    if (MEASURES.indexOf(measure) < 0) measure = "m2";
    var unit = q.get("unit") === "y" ? "y" : "m";
    var rawWindow = q.get("window");
    var amount = parseInt(rawWindow, 10);
    if (rawWindow === "0") amount = 0;
    else if (!isFinite(amount)) amount = 12;
    if (amount !== 0) amount = clamp(amount, unit);
    var method = q.get("method");
    if (METHODS.indexOf(method) < 0) method = "trailing";
    var log = q.get("log") === "0" ? false : true;
    var norm = q.get("norm");
    if (norm !== "gdp" && norm !== "cpi") norm = "0";
    var gap = parseFloat(q.get("gap"));
    if (!isFinite(gap)) gap = 0;
    if (gap < -5) gap = -5;
    if (gap > 15) gap = 15;
    var honest = q.get("honest") === "1";
    return { measure: measure, amount: amount, unit: unit, method: method, log: log, norm: norm, gap: gap, honest: honest };
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
    q.set("norm", state.norm);
    q.set("gap", String(Math.round(state.gap * 1000000) / 1000000));
    q.set("honest", state.honest ? "1" : "0");
    history.replaceState(null, "", "?" + q.toString());
  }

  function smoothed() {
    return state.amount > 0;
  }

  function unitName() {
    return state.unit === "y" ? "year" : "month";
  }

  function windowLabel() {
    if (!smoothed()) return "no smoothing";
    var n = state.amount;
    if (state.unit === "y") return n + (n === 1 ? " year" : " years");
    return n + (n === 1 ? " month" : " months");
  }

  function windowAdjective() {
    if (!smoothed()) return "print-to-print";
    return state.amount + (state.unit === "y" ? "-year" : "-month");
  }

  function methodName() {
    if (!smoothed()) return "print-to-print change";
    if (state.method === "regression") return "linear regression";
    if (state.method === "cagr") return "CAGR pace";
    return "trailing change";
  }

  function normName() {
    if (state.norm === "gdp") return "nominal GDP";
    if (state.norm === "cpi") return "CPI";
    return "";
  }

  function methodDetail() {
    if (!smoothed()) {
      return "No smoothing. The pace is the change from the previous print to the print in effect, divided by the days between those prints, and held until the next print. A decrease stays a decrease.";
    }
    if (state.method === "regression") {
      return "Linear regression over " + windowLabel() + ". Growth per day is the slope of the daily forward-filled level across the window. Flat days between prints are part of the fit.";
    }
    if (state.method === "cagr") {
      return "CAGR pace over " + windowLabel() + ". The compound rate from the start of the window to today, converted to dollars per day at today's level.";
    }
    return "Simple trailing change over " + windowLabel() + ", the default smooth. Growth per day is (level today − level at the start of the window) ÷ days in the window.";
  }

  function normDetail() {
    if (state.norm === "0") {
      return "Off. The pace is the monetary expansion itself, not growth in excess of GDP or CPI.";
    }
    var which = state.norm === "gdp"
      ? "Nominal GDP, FRED GDP, quarterly, seasonally adjusted annual rate. Only the ratio of levels is used, so the annual rate cancels."
      : "CPI, FRED CPIAUCSL, the monthly seasonally adjusted index.";
    var formula = !smoothed() || state.method === "trailing"
      ? "Excess pace = money's trailing change minus the starting money level times the deflator's percentage change over the same dates."
      : state.method === "cagr"
        ? "Excess pace = today's level times (money's compound daily rate − the deflator's)."
        : "Excess pace = the dollar slope of money minus today's level times the deflator's log-slope.";
    return "On. Money growth in excess of " + which + " " + formula + " A flat deflator leaves the pace unchanged. Matching percentage growth pauses the trailing and CAGR day counts.";
  }

  function formatDays(n) {
    var abs = Math.abs(n);
    if (abs >= 1000) return Math.round(abs).toLocaleString("en-US");
    return abs.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  }

  function signedDays(n) {
    if (n > 0) return "+" + formatDays(n);
    if (n < 0) return "−" + formatDays(n);
    return formatDays(0);
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

  function deflatorPoints() {
    if (state.norm !== "gdp" && state.norm !== "cpi") return null;
    var series = data.deflators && data.deflators[state.norm];
    return series ? series.points : [];
  }

  function run(measure) {
    return Pmb.computeBailout(measure.points, data.btc.points, {
      amount: state.amount,
      unit: unitName(),
      method: state.method,
      deflator: state.norm === "0" ? null : deflatorPoints(),
    });
  }

  function sentence(measure, latest) {
    var name = measure.name;
    var excess = state.norm === "0" ? "" : " in excess of " + normName();
    if (!latest || latest.state === "insufficient") {
      if (state.norm !== "0") {
        return name + " does not have a full " + windowLabel() + " covered by " + normName() + ", so there is no excess day count.";
      }
      if (!smoothed()) {
        return name + " has no earlier print to compare, so there is no unsmoothed day count yet.";
      }
      return name + " does not cover a full " + windowLabel() + " before this date, so there is no day count.";
    }
    if (latest.state === "contracting") {
      if (!smoothed()) {
        return "With no smoothing, the latest print of " + name + " was a decrease" + excess + ", so the bailout clock is paused. The decrease is shown as it is.";
      }
      return name + " did not expand over the trailing " + windowLabel() + excess + ", using a " + methodName() + ", so the bailout clock is paused. A pace that is not positive is a gap, not a day count.";
    }
    var pace = formatUSD(latest.growthPerDay) + " a day";
    var adj = windowAdjective();
    var tail = "so it expands by one bitcoin market cap every " + formatDays(latest.days) + " days.";
    if (!smoothed()) {
      return "With no smoothing, the latest print-to-print change in " + name + excess + " is about " + pace + ", " + tail;
    }
    if (state.method === "trailing") {
      return "At the current pace, the trailing " + adj + " change in " + name + excess + " is about " + pace + ", " + tail;
    }
    if (state.method === "regression") {
      return "At the current pace, a " + adj + " linear regression on " + name + excess + " rises about " + pace + ", " + tail;
    }
    return "At the current pace, the " + adj + " compound growth of " + name + excess + ", applied at today's level, is about " + pace + ", " + tail;
  }

  function paintHeadline(measure, result) {
    var latest = result.points.length ? result.points[result.points.length - 1] : null;
    var normBit = state.norm === "0" ? "" : " · excess of " + normName();
    els.kicker.textContent = measure.name + " · " + windowLabel() + " " + (smoothed() ? methodName() : "") + normBit;
    els.kicker.textContent = els.kicker.textContent.replace(/\s+/g, " ").trim();
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
      var line = "Bitcoin market cap on this date: " + formatUSD(latest.mcap) + ". Level in effect: " + formatUSD(latest.level) + ".";
      if (state.norm !== "0" && latest.growthUnadjusted != null) {
        line += " Unadjusted pace " + formatUSD(latest.growthUnadjusted) + " a day.";
      }
      els.pace.textContent = line;
    } else if (latest && latest.growthPerDay != null) {
      els.pace.textContent = "Pace " + formatUSD(latest.growthPerDay) + " a day." + (latest.mcap ? " Bitcoin market cap on this date: " + formatUSD(latest.mcap) + "." : "");
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
    if (els.paceNote) {
      els.paceNote.textContent = smoothed()
        ? "Dollars per day from the " + windowLabel() + " " + methodName() + (state.norm === "0" ? "" : ", in excess of " + normName()) + ". Decreases are drawn. The day count above is blank when this line is not positive."
        : "Dollars per day with no smoothing" + (state.norm === "0" ? "" : ", in excess of " + normName()) + ". Each step is the change between one print and the next, held until the following print, so a decrease shows as a decrease. The day count above is blank when this line is not positive.";
    }
    return { latest: latest, plotted: plotted };
  }

  function card(label, value, detail, tone) {
    var article = document.createElement("article");
    var p = document.createElement("p");
    p.className = "label";
    p.textContent = label;
    var strong = document.createElement("strong");
    if (tone) strong.className = tone;
    strong.textContent = value;
    var small = document.createElement("p");
    small.className = "detail";
    small.textContent = detail;
    article.appendChild(p);
    article.appendChild(strong);
    article.appendChild(small);
    return article;
  }

  function toneOf(n) {
    if (n > 0) return "up";
    if (n < 0) return "down";
    return "";
  }

  function paintSplit(result) {
    els.split.innerHTML = "";
    var frame = document.createElement("p");
    frame.className = "frame";
    frame.textContent = "A longer bailout at a high price is the point: it is a higher valuation relative to monetary expansion.";
    var latest = result.points.length ? result.points[result.points.length - 1] : null;
    var ref = null;
    if (latest && latest.refDate) {
      for (var i = 0; i < result.points.length; i++) {
        if (result.points[i].date === latest.refDate) {
          ref = result.points[i];
          break;
        }
      }
    }
    var split = ref ? Pmb.decompose(ref, latest) : null;
    if (!split) {
      var empty = document.createElement("p");
      empty.className = "split-empty";
      if (latest && latest.state === "contracting") {
        empty.textContent = smoothed()
          ? "The averaged pace is not positive, so there is no day count to split into price and money growth."
          : "With no smoothing the latest print is a decrease, so there is no day count to split. The decrease is the print itself.";
      } else if (!latest || !latest.refDate) {
        empty.textContent = smoothed()
          ? "The price-versus-money split starts once a full window sits inside the bitcoin history."
          : "The price-versus-money split starts once two money prints sit inside the bitcoin history.";
      } else {
        empty.textContent = "The split needs an expanding pace, and a bitcoin price, both today and on " + latest.refDate + ".";
      }
      els.split.appendChild(empty);
      els.split.appendChild(frame);
      return null;
    }
    var since = smoothed() ? "Since the window opened on " + latest.refDate : "Since the previous print on " + latest.refDate;
    els.split.appendChild(card("Change in days", signedDays(split.change), since, toneOf(split.change)));
    els.split.appendChild(card("From money growth", signedDays(split.fromMoney), "Pace changed, bitcoin held", toneOf(split.fromMoney)));
    els.split.appendChild(card("From bitcoin price", signedDays(split.fromPrice), "Price changed, coins held", toneOf(split.fromPrice)));
    els.split.appendChild(card("From new coins", signedDays(split.fromSupply), "Coins outstanding", toneOf(split.fromSupply)));
    els.split.appendChild(card("Fixed bitcoin price", formatDays(split.fixedPriceDays) + " days", "Price held at " + latest.refDate, ""));
    els.split.appendChild(card("Fixed bitcoin units", formatDays(split.fixedUnitsDays) + " days", "Coin count held at " + latest.refDate, ""));
    els.split.appendChild(frame);
    return split;
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

  function paintAssumptions(measure, split, latest) {
    els.assumptions.innerHTML = "";
    addAssumption("Axiom", "Money spends the same, so expansion in any form counts as expansion. Public debt is included: debt spends the same as cash, and one person's debt is another's asset.");
    addAssumption("Series", measure.name + ", a monetary expansion measure · " + measure.fred_id + " · " + measure.frequency + " · " + measure.seasonal);
    addAssumption("Smoothing", methodDetail());
    addAssumption("Normalization", normDetail());
    addAssumption("Contraction", "Not plotted as a day count. Zero or negative growth is a gap there, and a decrease on the pace chart. The day count is never negative and never infinite.");
    var moved = "Needs an expanding pace at both ends of the comparison.";
    if (split && latest && latest.refDate) {
      moved = "Since " + latest.refDate + ": money growth " + signedDays(split.fromMoney) + " days, bitcoin price " + signedDays(split.fromPrice) + " days, new coins " + signedDays(split.fromSupply) + " days. At the " + latest.refDate + " price the bailout would be " + formatDays(split.fixedPriceDays) + " days.";
    } else if (latest && latest.state === "contracting" && !smoothed()) {
      moved = "No smoothing, and the latest print decreased, so there is no day count to attribute.";
    }
    addAssumption("What moved", moved);
    addAssumption("Alignment", "Money, bitcoin, and the deflator step forward daily. Bitcoin's market cap and price are the print on that date, or the latest print on or before it. The headline date is the later of the money and bitcoin last prints.");
    addAssumption("Units", measure.published_units + ", stored in dollars" + (measure.multiplier > 1 ? " (× " + measure.multiplier.toLocaleString("en-US") + ")." : "."));
  }

  function paintSources() {
    els.sources.innerHTML = "";
    var btc = data.btc;
    els.sources.appendChild(sourceBlock(
      "Bitcoin market cap and price",
      btc.start + " → " + btc.end + " · " + btc.count.toLocaleString("en-US") + " days",
      btc.retrieval,
      btc.source_url,
      btc.source_name
    ));
    data.measures.forEach(function (measure) {
      var note = measure.retrieval;
      if (measure.id === "debt" && note.indexOf("spends the same") < 0) {
        note += " Counted as monetary expansion: debt spends the same as cash, and one person's debt is another's asset.";
      }
      els.sources.appendChild(sourceBlock(
        measure.name + " (" + measure.fred_id + ")",
        measure.start + " → " + measure.end + " · " + measure.count.toLocaleString("en-US") + " prints",
        note,
        measure.fred_url,
        "FRED " + measure.fred_id
      ));
    });
    if (data.deflators) {
      ["gdp", "cpi"].forEach(function (key) {
        var series = data.deflators[key];
        if (!series) return;
        els.sources.appendChild(sourceBlock(
          series.name + " (" + series.fred_id + ")",
          series.start + " → " + series.end + " · " + series.count.toLocaleString("en-US") + " prints",
          series.retrieval,
          series.fred_url,
          "FRED " + series.fred_id
        ));
      });
    }
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
      var amount = Number(button.getAttribute("data-window"));
      var on = amount === 0 ? state.amount === 0 : state.amount === amount && button.getAttribute("data-unit") === state.unit;
      button.setAttribute("aria-pressed", on ? "true" : "false");
    });
    document.querySelectorAll("[data-method]").forEach(function (button) {
      var on = smoothed() && button.getAttribute("data-method") === state.method;
      button.disabled = !smoothed();
      button.setAttribute("aria-pressed", on ? "true" : "false");
    });
    if (smoothed()) {
      els.amount.value = String(state.amount);
      els.unit.value = state.unit;
      els.amount.max = state.unit === "y" ? "50" : "600";
    }
    els.log.checked = state.log;
    var canNorm = !!(data.deflators && data.deflators.gdp && data.deflators.cpi);
    els.normalize.disabled = !canNorm;
    els.normalize.checked = canNorm && state.norm !== "0";
    els.normSeries.value = state.norm === "cpi" ? "cpi" : "gdp";
    els.normSeries.disabled = !canNorm || state.norm === "0";
    if (!canNorm) state.norm = "0";
    if (els.honest) els.honest.checked = !!state.honest;
    if (els.bsGap && document.activeElement !== els.bsGap) els.bsGap.value = String(state.gap);
    if (els.bsGapNum && document.activeElement !== els.bsGapNum) {
      els.bsGapNum.value = String(Math.round(state.gap * 10000) / 10000);
    }
    if (els.bsReveal) els.bsReveal.hidden = !state.honest;
  }

  function yearsLabel(value) {
    return value.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  }

  function clampGap(raw) {
    var n = Number(raw);
    if (!isFinite(n)) return null;
    if (n < -5) return -5;
    if (n > 15) return 15;
    return n;
  }

  function ppLabel(gap) {
    return (gap * 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function pctLabel(rate, digits) {
    return (rate * 100).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits }) + "%";
  }

  var PRESET_LABEL = {
    hospital: "Hospital",
    tuition: "Tuition",
    textbooks: "Textbooks",
    daycare: "Day care",
    medical: "Medical",
    housing: "Housing",
    food: "Food",
  };

  function paintBullshit() {
    var rows = Pmb.perryTable();
    if (els.bsPresets && !els.bsPresets.dataset.filled) {
      var buttons = '<button type="button" class="bs-preset" data-gap="0">None</button>';
      rows.forEach(function (row) {
        if (row.role !== "preset") return;
        buttons += '<button type="button" class="bs-preset" data-gap="' + row.gap * 100 + '">' +
          PRESET_LABEL[row.key] + "<strong>" + ppLabel(row.gap) + "</strong></button>";
      });
      els.bsPresets.innerHTML = buttons;
      els.bsPresets.dataset.filled = "1";
      els.bsPresets.addEventListener("click", function (event) {
        var button = event.target.closest("button");
        if (!button || !els.bsPresets.contains(button)) return;
        var next = clampGap(button.getAttribute("data-gap"));
        if (next == null) return;
        state.gap = next;
        els.bsGap.value = String(state.gap);
        els.bsGapNum.value = String(Math.round(state.gap * 10000) / 10000);
        tease();
        render();
      });
    }
    if (els.bsPresets) {
      els.bsPresets.querySelectorAll("button").forEach(function (button) {
        var gap = Number(button.getAttribute("data-gap"));
        button.setAttribute("aria-pressed", Math.abs(gap - state.gap) < 1e-6 ? "true" : "false");
      });
    }
    if (els.bsTable && !els.bsTable.dataset.filled) {
      var html = '<span class="bs-h">Category</span><span class="bs-h">Change</span><span class="bs-h">Annual</span><span class="bs-h">Gap</span>';
      rows.forEach(function (row) {
        var name = row.name + (row.role === "reference" ? " (reference)" : "");
        var cls = row.role === "reference" ? " is-ref" : "";
        html += '<span class="' + cls.trim() + '">' + name + "</span>";
        html += '<span class="bs-num' + cls + '">+' + (row.cumulative * 100).toFixed(1) + "%</span>";
        html += '<span class="bs-num' + cls + '">' + pctLabel(row.annualized, 2) + "</span>";
        html += '<span class="bs-num' + cls + '">' + ppLabel(row.gap) + "</span>";
      });
      els.bsTable.innerHTML = html;
      els.bsTable.dataset.filled = "1";
    }
    var wages = null;
    rows.forEach(function (row) { if (row.key === "wages") wages = row; });
    return wages;
  }

  function paintHalfLife() {
    var table = document.getElementById("half-table");
    var latest = document.getElementById("half-latest");
    var cpi = data.deflators && data.deflators.cpi;
    if (table && !table.dataset.filled) {
      var html = "";
      for (var pct = 1; pct <= 10; pct++) {
        var steady = Pmb.halfLifeYears(pct / 100);
        html += '<div class="half-cell' + (pct === 2 ? " is-mark" : "") + '"><span>' + pct + '%</span><strong>' + yearsLabel(steady) + '</strong></div>';
      }
      table.innerHTML = html;
      table.dataset.filled = "1";
    }
    var wages = paintBullshit();
    if (!cpi || !cpi.points) {
      shareHalfYears = null;
      if (latest) latest.textContent = "CPI is not in this snapshot.";
      return { official: [], gap: [], wages: [] };
    }
    var series = Pmb.trailingCpiHalfLife(cpi.points);
    var gapDecimal = Pmb.effectiveGap(state.gap / 100, state.honest);
    var adjusted = series.map(function (row) {
      return {
        date: row.date,
        years: row.rate == null ? null : Pmb.halfLifeWithGap(row.rate, gapDecimal),
      };
    });
    var wageYears = wages ? Pmb.halfLifeYears(wages.annualized) : null;
    var wageSeries = series.map(function (row) {
      return { date: row.date, years: wageYears };
    });
    var last = null;
    for (var i = series.length - 1; i >= 0; i--) {
      if (series[i].years != null) { last = series[i]; break; }
    }
    shareHalfYears = last ? last.years : null;
    if (latest) {
      if (!last) latest.textContent = "The trailing 12-month CPI rate is not positive.";
      else {
        var pct = (last.rate * 100).toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
        var line = "Latest print " + last.date + ": " + pct + "% over the prior twelve months, " +
          yearsLabel(last.years) + " years";
        if (!state.honest) {
          latest.textContent = line + ".";
        } else {
          var adjustedYears = Pmb.halfLifeWithGap(last.rate, gapDecimal);
          line += " at official CPI. At CPI plus " + ppLabel(state.gap / 100) + " percentage points, ";
          line += adjustedYears != null ? yearsLabel(adjustedYears) + " years." : "the rate is not positive, so that half-life is a gap.";
          line += " The gap is an illustrative assumption, not measured real inflation.";
          latest.textContent = line;
        }
      }
    }
    return {
      official: Pmb.toChartData(series, "years"),
      gap: Pmb.toChartData(adjusted, "years"),
      wages: Pmb.toChartData(wageSeries, "years"),
    };
  }

  function shareSentence() {
    var line = els.daysUnit.hidden
      ? "The Poor Man's Bailout clock is paused."
      : "The Poor Man's Bailout: the money printer makes a whole bitcoin market cap every " + els.days.textContent.trim() + " days.";
    if (shareHalfYears != null) line += " Your dollar's half-life: " + yearsLabel(shareHalfYears) + " years.";
    return line;
  }

  function paintShare() {
    var text = shareSentence();
    var href = "https://twitter.com/intent/tweet?text=" + encodeURIComponent(text) + "&url=" + encodeURIComponent(location.href);
    els.shareX.href = href;
    els.shareHalfX.href = href;
  }

  function copyLink(button) {
    var url = location.href;
    function done(label) {
      button.textContent = label;
      setTimeout(function () { button.textContent = "Copy link"; }, 1400);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(function () { done("Copied"); }, function () { done("Copy the address bar"); });
    } else {
      done("Copy the address bar");
    }
  }

  function render() {
    if (state.amount !== 0) state.amount = clamp(state.amount, state.unit);
    writeState();
    syncControls();
    var measure = measureById(state.measure);
    var cache = {};
    data.measures.forEach(function (item) {
      if (item.group === "primary" || item.id === state.measure) cache[item.id] = run(item);
    });
    var result = cache[state.measure];
    var painted = paintHeadline(measure, result);
    var split = paintSplit(result);
    paintStrip(cache);
    paintAssumptions(measure, split, painted.latest);
    els.moneyTitle.textContent = measure.name;
    els.legend.textContent = measure.short;
    var price = data.btc.points[data.btc.points.length - 1][2];
    els.btcNote.textContent = "Log scale. Latest price " + (price != null ? "$" + Number(price).toLocaleString("en-US", { maximumFractionDigits: 2 }) : "unavailable") + ".";
    var half = paintHalfLife();
    PmbCharts.render({
      bailout: painted.plotted,
      fixedPrice: Pmb.toChartData(result.points, "fixedPriceDays"),
      fixedUnits: Pmb.toChartData(result.points, "fixedUnitsDays"),
      pace: Pmb.toChartData(result.points, "growthPerDay"),
      money: measure.points,
      btc: btcPairs(),
      halfLife: half.official,
      halfLifeGap: half.gap,
      halfLifeWages: half.wages,
      log: state.log,
    });
    paintShare();
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
        var amount = Number(button.getAttribute("data-window"));
        if (amount === 0) state.amount = 0;
        else {
          state.amount = amount;
          state.unit = button.getAttribute("data-unit");
        }
        render();
      });
    });
    document.querySelectorAll("[data-method]").forEach(function (button) {
      button.addEventListener("click", function () {
        if (!smoothed()) return;
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
    els.normalize.addEventListener("change", function () {
      state.norm = els.normalize.checked ? els.normSeries.value : "0";
      render();
    });
    els.normSeries.addEventListener("change", function () {
      if (!els.normalize.checked) return;
      state.norm = els.normSeries.value === "cpi" ? "cpi" : "gdp";
      render();
    });
    els.share.addEventListener("click", function () { copyLink(els.share); });
    els.shareHalf.addEventListener("click", function () { copyLink(els.shareHalf); });
    function applyGap(raw, fromSlider) {
      var next = clampGap(raw);
      if (next == null) return;
      state.gap = next;
      if (fromSlider) els.bsGapNum.value = String(Math.round(state.gap * 100) / 100);
      else els.bsGap.value = String(state.gap);
      tease();
      render();
    }
    els.bsGap.addEventListener("input", function () { applyGap(els.bsGap.value, true); });
    els.bsGapNum.addEventListener("input", function () { applyGap(els.bsGapNum.value, false); });
    els.honest.addEventListener("change", function () {
      state.honest = els.honest.checked;
      if (state.honest && els.bsTease) els.bsTease.textContent = "";
      render();
    });
  }

  function tease() {
    if (!els.bsTease || state.honest) return;
    els.bsTease.textContent = "Adjusting...";
    clearTimeout(teaseTimer);
    teaseTimer = setTimeout(function () {
      if (!els.bsTease || state.honest) return;
      els.bsTease.textContent = shareHalfYears != null ? yearsLabel(shareHalfYears) + " years" : "";
    }, 700);
  }

  function fail(message) {
    els.days.textContent = "Unavailable";
    els.days.classList.add("insufficient");
    els.daysUnit.hidden = true;
    els.sentence.textContent = message;
  }

  document.querySelectorAll(".tip-copy").forEach(function (button) {
    button.addEventListener("click", function () {
      var address = button.getAttribute("data-address") || "";
      function done(label) {
        button.textContent = label;
        setTimeout(function () { button.textContent = "Copy"; }, 1400);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(address).then(function () { done("Copied"); }, function () { done("Copy the address"); });
      } else {
        done("Copy the address");
      }
    });
  });

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
