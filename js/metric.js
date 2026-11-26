/* Poor Man's Bailout day count. Mirrors scripts/metric.py.
   Levels are dollars. Dates are ISO calendar days, UTC, no time zone. */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.Pmb = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function fmt(year, month, day) {
    return year + "-" + pad(month) + "-" + pad(day);
  }

  function parts(iso) {
    var bits = iso.split("-");
    return [Number(bits[0]), Number(bits[1]), Number(bits[2])];
  }

  function utc(iso) {
    var p = parts(iso);
    return Date.UTC(p[0], p[1] - 1, p[2]);
  }

  function fromUtc(ms) {
    var dt = new Date(ms);
    return fmt(dt.getUTCFullYear(), dt.getUTCMonth() + 1, dt.getUTCDate());
  }

  function daysBetween(a, b) {
    return Math.round((utc(b) - utc(a)) / 86400000);
  }

  function addDays(iso, n) {
    return fromUtc(utc(iso) + n * 86400000);
  }

  function shiftMonths(iso, months) {
    var p = parts(iso);
    var monthIndex = p[0] * 12 + (p[1] - 1) + months;
    var year = Math.floor(monthIndex / 12);
    var month0 = monthIndex - year * 12;
    var dim = new Date(Date.UTC(year, month0 + 1, 0)).getUTCDate();
    return fmt(year, month0 + 1, Math.min(p[2], dim));
  }

  function monthsOf(amount, unit) {
    if (!(amount > 0)) throw new Error("window must be positive");
    if (unit === "month" || unit === "months" || unit === "m") return amount;
    if (unit === "year" || unit === "years" || unit === "y") return amount * 12;
    throw new Error("unknown window unit " + unit);
  }

  function normalize(points) {
    var map = Object.create(null);
    for (var i = 0; i < points.length; i++) {
      var row = points[i];
      if (row[1] == null || row[1] === "") continue;
      map[row[0]] = Number(row[1]);
    }
    return Object.keys(map)
      .sort()
      .map(function (d) {
        return [d, map[d]];
      });
  }

  function forwardFill(points, start, end) {
    var n = daysBetween(start, end) + 1;
    var out = new Array(n);
    var cursor = 0;
    var current = null;
    for (var i = 0; i < n; i++) {
      var day = addDays(start, i);
      while (cursor < points.length && points[cursor][0] <= day) {
        current = points[cursor][1];
        cursor++;
      }
      out[i] = current;
    }
    return out;
  }

  function regressionSlope(values, start, end) {
    if (end == null) end = values.length - 1;
    if (start == null) start = 0;
    var n = end - start + 1;
    if (n < 2) return null;
    var sumT = ((n - 1) * n) / 2;
    var sumT2 = ((n - 1) * n * (2 * n - 1)) / 6;
    var sumY = 0;
    var sumTY = 0;
    for (var i = 0; i < n; i++) {
      var y = values[start + i];
      if (y == null) return null;
      sumY += y;
      sumTY += i * y;
    }
    var denom = n * sumT2 - sumT * sumT;
    if (denom === 0) return null;
    return (n * sumTY - sumT * sumY) / denom;
  }

  function normalizeBtc(points) {
    var map = Object.create(null);
    points = points || [];
    for (var i = 0; i < points.length; i++) {
      var row = points[i];
      if (row[1] == null || row[1] === "") continue;
      var price = row.length > 2 && row[2] != null && row[2] !== "" ? Number(row[2]) : null;
      map[row[0]] = [Number(row[1]), price];
    }
    var keys = Object.keys(map).sort();
    var caps = [];
    var prices = [];
    for (var k = 0; k < keys.length; k++) {
      caps.push([keys[k], map[keys[k]][0]]);
      if (map[keys[k]][1] != null && isFinite(map[keys[k]][1])) prices.push([keys[k], map[keys[k]][1]]);
    }
    return { caps: caps, prices: prices };
  }

  function at(levels, origin, day) {
    if (!levels.length || !origin || day < origin) return [null, null];
    var idx = daysBetween(origin, day);
    if (idx < 0 || idx >= levels.length) return [null, null];
    return [levels[idx], idx];
  }

  function positive(value) {
    return typeof value === "number" && isFinite(value) && value > 0;
  }

  function logSlope(values, start, end) {
    if (start == null || end == null || start < 0) return null;
    var n = end - start + 1;
    if (n < 2) return null;
    var logs = [];
    for (var i = start; i <= end; i++) {
      var value = values[i];
      if (value == null || value <= 0) return null;
      logs.push(Math.log(value));
    }
    return regressionSlope(logs, 0, logs.length - 1);
  }

  function growth(method, levels, startI, endI, levelStart, level, nDays) {
    if (level == null || levelStart == null || !(nDays > 0)) return null;
    if (method === "trailing") return (level - levelStart) / nDays;
    if (method === "cagr") {
      if (levelStart <= 0 || level <= 0) return null;
      return level * (Math.pow(level / levelStart, 1 / nDays) - 1);
    }
    if (method === "regression") return regressionSlope(levels, startI, endI);
    throw new Error("unknown averaging method " + method);
  }

  function proportionalRate(method, levels, startI, endI, levelStart, level, nDays) {
    if (!(nDays > 0) || levelStart == null || level == null) return null;
    if (method === "trailing" || method === "none") {
      if (levelStart <= 0) return null;
      return (level - levelStart) / (nDays * levelStart);
    }
    if (method === "cagr") {
      if (levelStart <= 0 || level <= 0) return null;
      return Math.pow(level / levelStart, 1 / nDays) - 1;
    }
    if (method === "regression") return logSlope(levels, startI, endI);
    throw new Error("unknown averaging method " + method);
  }

  function excessGrowth(method, g, level, levelStart, rate) {
    if (g == null || rate == null || level == null || levelStart == null) return null;
    var base = method === "trailing" || method === "none" ? levelStart : level;
    return g - base * rate;
  }

  function classify(g, mcap) {
    if (g == null || mcap == null || mcap <= 0) return ["insufficient", null];
    if (g <= 0) return ["contracting", null];
    var days = mcap / g;
    if (!isFinite(days) || days <= 0) return ["insufficient", null];
    return ["expanding", days];
  }

  function computeBailout(money, btc, opts) {
    opts = opts || {};
    money = normalize(money || []);
    var parsed = normalizeBtc(btc || []);
    var caps = parsed.caps;
    var prices = parsed.prices;
    var normalizing = opts.deflator != null;
    var deflator = normalizing ? normalize(opts.deflator || []) : [];
    if (!money.length || !caps.length) return { points: [] };
    var smooth = Number(opts.amount) > 0;
    var method = opts.method;
    if (smooth) {
      if (method !== "trailing" && method !== "cagr" && method !== "regression") {
        throw new Error("unknown averaging method " + method);
      }
    } else {
      method = "none";
    }
    var m0 = money[0][0];
    var b0 = caps[0][0];
    var moneyEnd = money[money.length - 1][0];
    var capEnd = caps[caps.length - 1][0];
    var end = moneyEnd > capEnd ? moneyEnd : capEnd;
    var evalStart = m0 > b0 ? m0 : b0;
    if (evalStart > end) return { points: [] };
    var mLevels = forwardFill(money, m0, end);
    var cLevels = forwardFill(caps, b0, end);
    var p0 = prices.length ? prices[0][0] : null;
    var pLevels = prices.length ? forwardFill(prices, p0, end) : [];
    var d0 = deflator.length ? deflator[0][0] : null;
    var dLevels = deflator.length ? forwardFill(deflator, d0, end) : [];
    var points = [];
    var printIndex = -1;
    for (var day = evalStart; day <= end; day = addDays(day, 1)) {
      while (printIndex + 1 < money.length && money[printIndex + 1][0] <= day) printIndex++;
      var level = mLevels[daysBetween(m0, day)];
      var mcap = cLevels[daysBetween(b0, day)];
      var priceHit = at(pLevels, p0, day);
      var price = priceHit[0];
      var supply = positive(price) && positive(mcap) ? mcap / price : null;
      var start = null;
      var growthEnd = null;
      var nDays = 0;
      if (smooth) {
        start = shiftMonths(day, -monthsOf(Number(opts.amount), opts.unit));
        growthEnd = day;
        nDays = daysBetween(start, day);
      } else if (printIndex >= 1) {
        growthEnd = money[printIndex][0];
        start = money[printIndex - 1][0];
        nDays = daysBetween(start, growthEnd);
      }
      var refDate = start != null && start >= evalStart ? start : null;
      if (start == null || start < m0 || !(nDays > 0) || level == null || mcap == null) {
        points.push(point(day, "insufficient", null, null, null, level, null, mcap, price, supply, refDate));
        continue;
      }
      var startI = daysBetween(m0, start);
      var endI = daysBetween(m0, growthEnd);
      var levelStart = mLevels[startI];
      var levelEnd = mLevels[endI];
      var growthMethod = method === "none" ? "trailing" : method;
      var raw = growth(growthMethod, mLevels, startI, endI, levelStart, levelEnd, nDays);
      var g = raw;
      if (normalizing) {
        var dStartHit = at(dLevels, d0, start);
        var dEndHit = at(dLevels, d0, growthEnd);
        var rate = proportionalRate(growthMethod, dLevels, dStartHit[1], dEndHit[1], dStartHit[0], dEndHit[0], nDays);
        g = excessGrowth(method, raw, levelEnd, levelStart, rate);
      }
      var classified = classify(g, mcap);
      points.push(point(day, classified[0], classified[1], g, raw, level, levelStart, mcap, price, supply, refDate));
    }
    return { points: annotateCounters(points) };
  }

  function point(day, state, days, g, raw, level, levelStart, mcap, price, supply, refDate) {
    return {
      date: day,
      state: state,
      days: days,
      growthPerDay: g,
      growthUnadjusted: raw,
      level: level,
      levelStart: levelStart,
      mcap: mcap,
      price: price,
      supply: supply,
      refDate: refDate,
      fixedPriceDays: null,
      fixedUnitsDays: null,
    };
  }

  function annotateCounters(points) {
    var byDate = Object.create(null);
    for (var i = 0; i < points.length; i++) byDate[points[i].date] = points[i];
    for (var j = 0; j < points.length; j++) {
      var row = points[j];
      row.fixedPriceDays = null;
      row.fixedUnitsDays = null;
      var ref = row.refDate ? byDate[row.refDate] : null;
      if (!ref || !positive(row.growthPerDay)) continue;
      if (positive(ref.price) && positive(row.supply)) {
        row.fixedPriceDays = (ref.price * row.supply) / row.growthPerDay;
      }
      if (positive(row.price) && positive(ref.supply)) {
        row.fixedUnitsDays = (row.price * ref.supply) / row.growthPerDay;
      }
    }
    return points;
  }

  function decompose(start, end) {
    if (!start || !end) return null;
    var g0 = start.growthPerDay;
    var g1 = end.growthPerDay;
    var p0 = start.price;
    var p1 = end.price;
    var s0 = start.supply;
    var s1 = end.supply;
    if (!positive(g0) || !positive(g1) || !positive(p0) || !positive(p1) || !positive(s0) || !positive(s1)) {
      return null;
    }
    var daysStart = (p0 * s0) / g0;
    var afterMoney = (p0 * s0) / g1;
    var afterPrice = (p1 * s0) / g1;
    var daysEnd = (p1 * s1) / g1;
    return {
      daysStart: daysStart,
      daysEnd: daysEnd,
      fromMoney: afterMoney - daysStart,
      fromPrice: afterPrice - afterMoney,
      fromSupply: daysEnd - afterPrice,
      fixedPriceDays: (p0 * s1) / g1,
      fixedUnitsDays: (p1 * s0) / g1,
      change: daysEnd - daysStart,
    };
  }

  function daysChart(points) {
    var rows = [];
    var gapOpen = false;
    for (var i = 0; i < points.length; i++) {
      var p = points[i];
      var expanding = p.state === "expanding" && p.days != null && p.days > 0 && isFinite(p.days);
      if (expanding) {
        rows.push({ time: p.date, value: p.days });
        gapOpen = false;
        continue;
      }
      if (rows.length && !gapOpen) {
        rows.push({ time: p.date });
        gapOpen = true;
      }
    }
    if (points.length && points[points.length - 1].state !== "expanding" && rows.length) {
      if (rows[rows.length - 1].time !== points[points.length - 1].date) {
        rows.push({ time: points[points.length - 1].date });
      }
    }
    return rows;
  }

  function seriesChart(points, key, positiveOnly) {
    var rows = [];
    var gapOpen = false;
    var lastOk = false;
    for (var i = 0; i < points.length; i++) {
      var value = points[i][key];
      var ok = positiveOnly ? positive(value) : typeof value === "number" && isFinite(value);
      if (ok) {
        rows.push({ time: points[i].date, value: value });
        gapOpen = false;
        lastOk = true;
        continue;
      }
      lastOk = false;
      if (rows.length && !gapOpen) {
        rows.push({ time: points[i].date });
        gapOpen = true;
      }
    }
    if (points.length && !lastOk && rows.length && rows[rows.length - 1].time !== points[points.length - 1].date) {
      rows.push({ time: points[points.length - 1].date });
    }
    return rows;
  }

  function halfLifeYears(rate) {
    if (typeof rate !== "number" || !isFinite(rate) || rate <= 0) return null;
    var growth = Math.log(1 + rate);
    if (!(growth > 0) || !isFinite(growth)) return null;
    return Math.log(2) / growth;
  }

  var PERRY_SPAN_YEARS = 26.5;
  var PERRY_CUMULATIVE = [
    ["overall", "Overall inflation", 0.964, "baseline"],
    ["hospital", "Hospital Services", 2.911, "preset"],
    ["tuition", "College Tuition and Fees", 1.998, "preset"],
    ["textbooks", "College Textbooks", 1.819, "preset"],
    ["daycare", "Day Care and Preschool", 1.624, "preset"],
    ["medical", "Medical Care Services", 1.505, "preset"],
    ["wages", "Average Hourly Wages", 1.357, "reference"],
    ["housing", "Housing", 1.153, "preset"],
    ["food", "Food and Beverages", 1.085, "preset"],
  ];

  function annualizedFromCumulative(change, years) {
    if (typeof change !== "number" || !isFinite(change) || change <= -1) return null;
    var span = years == null ? PERRY_SPAN_YEARS : years;
    if (typeof span !== "number" || !isFinite(span) || span <= 0) return null;
    var rate = Math.pow(1 + change, 1 / span) - 1;
    return isFinite(rate) ? rate : null;
  }

  function perryTable() {
    var overall = annualizedFromCumulative(0.964);
    return PERRY_CUMULATIVE.map(function (row) {
      var rate = annualizedFromCumulative(row[2]);
      return {
        key: row[0],
        name: row[1],
        cumulative: row[2],
        annualized: rate,
        gap: rate == null || overall == null ? null : rate - overall,
        role: row[3],
      };
    });
  }

  function halfLifeWithGap(rate, gap) {
    if (typeof rate !== "number" || typeof gap !== "number") return null;
    if (!isFinite(rate) || !isFinite(gap)) return null;
    return halfLifeYears(rate + gap);
  }

  function effectiveGap(gap, honest) {
    if (!honest) return 0;
    if (typeof gap !== "number" || !isFinite(gap)) return 0;
    return gap;
  }

  function trailingCpiHalfLife(points) {
    var series = normalize(points);
    var levels = Object.create(null);
    for (var i = 0; i < series.length; i++) levels[series[i][0]] = series[i][1];
    var out = [];
    var started = false;
    for (var j = 0; j < series.length; j++) {
      var day = series[j][0];
      var level = series[j][1];
      var prior = levels[shiftMonths(day, -12)];
      if (prior == null || prior <= 0 || !(level > 0)) {
        if (started) out.push({ date: day, rate: null, years: null });
        continue;
      }
      var rate = level / prior - 1;
      out.push({ date: day, rate: rate, years: halfLifeYears(rate) });
      started = true;
    }
    return out;
  }

  function toChartData(points, key) {
    if (!key || key === "days") return daysChart(points);
    return seriesChart(points, key, key !== "growthPerDay");
  }

  return {
    shiftMonths: shiftMonths,
    regressionSlope: regressionSlope,
    computeBailout: computeBailout,
    decompose: decompose,
    toChartData: toChartData,
    halfLifeYears: halfLifeYears,
    trailingCpiHalfLife: trailingCpiHalfLife,
    annualizedFromCumulative: annualizedFromCumulative,
    perryTable: perryTable,
    halfLifeWithGap: halfLifeWithGap,
    effectiveGap: effectiveGap,
    perrySpanYears: PERRY_SPAN_YEARS,
  };
});
