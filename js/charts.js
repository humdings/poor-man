/* TradingView Lightweight Charts, dark, one instance per panel. */
(function () {
  var GOLD = "#e4b15a";
  var SAGE = "#9dbe8a";
  var UNITS = "#8eb4d4";
  var INK = "#b7b1a3";
  var GRID = "rgba(243, 239, 228, 0.06)";
  var BORDER = "rgba(243, 239, 228, 0.14)";
  var BG = "#171d16";

  var charts = {};

  function library() {
    return window.LightweightCharts || null;
  }

  function options(el) {
    return {
      width: el.clientWidth,
      height: el.clientHeight,
      layout: {
        background: { type: "solid", color: BG },
        textColor: INK,
        fontFamily: 'Outfit, "Segoe UI", sans-serif',
      },
      grid: { vertLines: { color: GRID }, horzLines: { color: GRID } },
      rightPriceScale: { borderColor: BORDER },
      leftPriceScale: { borderColor: BORDER, visible: false },
      timeScale: { borderColor: BORDER, fixLeftEdge: true, fixRightEdge: true },
      crosshair: { vertLine: { color: "rgba(228,177,90,0.35)" }, horzLine: { color: "rgba(228,177,90,0.35)" } },
      handleScroll: true,
      handleScale: true,
    };
  }

  function usd(value) {
    var abs = Math.abs(value);
    if (abs >= 1e12) return "$" + (value / 1e12).toFixed(2) + "T";
    if (abs >= 1e9) return "$" + (value / 1e9).toFixed(2) + "B";
    if (abs >= 1e6) return "$" + (value / 1e6).toFixed(2) + "M";
    return "$" + Math.round(value).toLocaleString("en-US");
  }

  function years(value) {
    if (Math.abs(value) >= 100) return Math.round(value).toLocaleString("en-US");
    return value.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  }

  function days(value) {
    if (value >= 1000) return Math.round(value).toLocaleString("en-US");
    return value.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  }

  function mount(id) {
    var el = document.getElementById(id);
    var LW = library();
    if (!LW || !el) return null;
    var chart = LW.createChart(el, options(el));
    var observer = new ResizeObserver(function () {
      chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
    });
    observer.observe(el);
    return chart;
  }

  function ensure() {
    if (!library() || charts.bailout) return charts.bailout;
    charts.bailout = mount("chart-bailout");
    charts.fixed = mount("chart-fixed");
    charts.pace = mount("chart-pace");
    charts.money = mount("chart-money");
    charts.btc = mount("chart-btc");
    charts.overlay = mount("chart-overlay");
    charts.halflife = mount("chart-halflife");
    if (!charts.bailout) return null;

    charts.bailoutSeries = charts.bailout.addLineSeries({
      color: GOLD,
      lineWidth: 2,
      priceFormat: { type: "custom", formatter: days, minMove: 0.1 },
      priceLineVisible: false,
      lastValueVisible: true,
    });
    var dayFormat = { type: "custom", formatter: days, minMove: 0.1 };
    charts.fixedActual = charts.fixed.addLineSeries({
      color: GOLD,
      lineWidth: 2,
      priceFormat: dayFormat,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    charts.fixedPrice = charts.fixed.addLineSeries({
      color: SAGE,
      lineWidth: 2,
      priceFormat: dayFormat,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    charts.fixedUnits = charts.fixed.addLineSeries({
      color: UNITS,
      lineWidth: 2,
      lineStyle: 2,
      priceFormat: dayFormat,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    charts.paceSeries = charts.pace.addLineSeries({
      color: GOLD,
      lineWidth: 2,
      priceFormat: { type: "custom", formatter: usd },
      priceLineVisible: false,
      lastValueVisible: true,
    });
    charts.paceSeries.createPriceLine({
      price: 0,
      color: BORDER,
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: false,
      title: "",
    });
    charts.moneySeries = charts.money.addAreaSeries({
      lineColor: SAGE,
      topColor: "rgba(157, 190, 138, 0.28)",
      bottomColor: "rgba(157, 190, 138, 0.02)",
      lineWidth: 2,
      priceFormat: { type: "custom", formatter: usd },
      priceLineVisible: false,
    });
    charts.money.priceScale("right").applyOptions({ mode: 1 });

    charts.btcSeries = charts.btc.addAreaSeries({
      lineColor: GOLD,
      topColor: "rgba(228, 177, 90, 0.28)",
      bottomColor: "rgba(228, 177, 90, 0.02)",
      lineWidth: 2,
      priceFormat: { type: "custom", formatter: usd },
      priceLineVisible: false,
    });
    charts.btc.priceScale("right").applyOptions({ mode: 1 });

    charts.overlay.priceScale("left").applyOptions({ visible: true, borderColor: BORDER, mode: 1 });
    charts.overlay.priceScale("right").applyOptions({ mode: 1 });
    charts.overlayMoney = charts.overlay.addLineSeries({
      color: SAGE,
      lineWidth: 2,
      priceScaleId: "left",
      priceFormat: { type: "custom", formatter: usd },
      priceLineVisible: false,
    });
    if (charts.halflife) {
      charts.halflifeSeries = charts.halflife.addLineSeries({
        color: GOLD,
        lineWidth: 2,
        priceFormat: { type: "custom", formatter: years, minMove: 0.1 },
        priceLineVisible: false,
        lastValueVisible: true,
      });
      charts.halflife.priceScale("right").applyOptions({ mode: 1 });
    }
    charts.overlayBtc = charts.overlay.addLineSeries({
      color: GOLD,
      lineWidth: 2,
      priceScaleId: "right",
      priceFormat: { type: "custom", formatter: usd },
      priceLineVisible: false,
    });
    return charts.bailout;
  }

  function monotonic(rows) {
    var out = [];
    var last = "";
    for (var i = 0; i < rows.length; i++) {
      if (!rows[i].time || rows[i].time <= last) continue;
      last = rows[i].time;
      out.push(rows[i]);
    }
    return out;
  }

  function levels(points) {
    return monotonic(points.map(function (row) {
      return { time: row[0], value: row[1] };
    }));
  }

  function render(spec) {
    if (!ensure()) {
      ["chart-bailout", "chart-fixed", "chart-pace", "chart-money", "chart-btc", "chart-overlay", "chart-halflife"].forEach(function (id) {
        var el = document.getElementById(id);
        if (el && !el.dataset.missing) {
          el.dataset.missing = "1";
          el.insertAdjacentHTML("beforebegin", '<p class="chart-empty">Charts did not load. The number above still uses the snapshot.</p>');
        }
      });
      return;
    }
    try {
      charts.bailoutSeries.setData(monotonic(spec.bailout));
      charts.fixedActual.setData(monotonic(spec.bailout));
      charts.fixedPrice.setData(monotonic(spec.fixedPrice || []));
      charts.fixedUnits.setData(monotonic(spec.fixedUnits || []));
      charts.paceSeries.setData(monotonic(spec.pace || []));
      charts.moneySeries.setData(levels(spec.money));
      charts.btcSeries.setData(levels(spec.btc));
      charts.overlayMoney.setData(levels(spec.money));
      charts.overlayBtc.setData(levels(spec.btc));
      if (charts.halflifeSeries) charts.halflifeSeries.setData(monotonic(spec.halfLife || []));
    } catch (err) {
      console.error(err);
    }
    charts.bailout.timeScale().fitContent();
    charts.fixed.timeScale().fitContent();
    charts.pace.timeScale().fitContent();
    charts.money.timeScale().fitContent();
    charts.btc.timeScale().fitContent();
    charts.overlay.timeScale().fitContent();
    if (charts.halflife) charts.halflife.timeScale().fitContent();
    setLog(spec.log);
  }

  function setLog(on) {
    if (!charts.bailout) return;
    charts.bailout.priceScale("right").applyOptions({ mode: on ? 1 : 0 });
    if (charts.fixed) charts.fixed.priceScale("right").applyOptions({ mode: on ? 1 : 0 });
  }

  window.PmbCharts = { render: render, setLog: setLog, available: library };
})();
