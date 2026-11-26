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
      sumY += y;
      sumTY += i * y;
    }
    var denom = n * sumT2 - sumT * sumT;
    if (denom === 0) return null;
    return (n * sumTY - sumT * sumY) / denom;
  }

  function growth(method, levels, startI, endI, levelStart, level, nDays) {
    if (method === "trailing") return (level - levelStart) / nDays;
    if (method === "cagr") {
      if (levelStart <= 0 || level <= 0) return null;
      return level * (Math.pow(level / levelStart, 1 / nDays) - 1);
    }
    if (method === "regression") return regressionSlope(levels, startI, endI);
    throw new Error("unknown averaging method " + method);
  }

  function classify(g, mcap) {
    if (g == null || mcap == null || mcap <= 0) return ["insufficient", null];
    if (g <= 0) return ["contracting", null];
    var days = mcap / g;
    if (!isFinite(days) || days <= 0) return ["insufficient", null];
    return ["expanding", days];
  }

  function computeBailout(money, btc, opts) {
    money = normalize(money || []);
    btc = normalize(btc || []);
    if (!money.length || !btc.length) return { points: [] };
    var months = monthsOf(Number(opts.amount), opts.unit);
    var method = opts.method;
    var m0 = money[0][0];
    var b0 = btc[0][0];
    var end = money[money.length - 1][0] > btc[btc.length - 1][0]
      ? money[money.length - 1][0]
      : btc[btc.length - 1][0];
    var evalStart = m0 > b0 ? m0 : b0;
    if (evalStart > end) return { points: [] };
    var mLevels = forwardFill(money, m0, end);
    var cLevels = forwardFill(btc, b0, end);
    var points = [];
    for (var day = evalStart; day <= end; day = addDays(day, 1)) {
      var level = mLevels[daysBetween(m0, day)];
      var mcap = cLevels[daysBetween(b0, day)];
      var start = shiftMonths(day, -months);
      var nDays = daysBetween(start, day);
      if (start < m0 || nDays <= 0 || level == null || mcap == null) {
        points.push(point(day, "insufficient", null, null, level, null, mcap));
        continue;
      }
      var startI = daysBetween(m0, start);
      var levelStart = mLevels[startI];
      var endI = daysBetween(m0, day);
      var g = growth(method, mLevels, startI, endI, levelStart, level, nDays);
      var classified = classify(g, mcap);
      points.push(point(day, classified[0], classified[1], g, level, levelStart, mcap));
    }
    return { points: points };
  }

  function point(day, state, days, g, level, levelStart, mcap) {
    return {
      date: day,
      state: state,
      days: days,
      growthPerDay: g,
      level: level,
      levelStart: levelStart,
      mcap: mcap,
    };
  }

  function toChartData(points) {
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

  return {
    shiftMonths: shiftMonths,
    regressionSlope: regressionSlope,
    computeBailout: computeBailout,
    toChartData: toChartData,
  };
});
