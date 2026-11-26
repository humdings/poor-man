import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const Pmb = require("../js/metric.js");

const input = JSON.parse(process.argv[2]);
const out = Pmb.computeBailout(input.money, input.btc, {
  amount: input.amount,
  unit: input.unit,
  method: input.method,
  deflator: input.deflator == null ? null : input.deflator,
});
if (!out.points.length) {
  console.log(JSON.stringify({ date: null, state: "insufficient", days: null }));
  process.exit(0);
}
const last = out.points[out.points.length - 1];
let split = null;
if (last.refDate) {
  const ref = out.points.find((row) => row.date === last.refDate);
  const raw = ref ? Pmb.decompose(ref, last) : null;
  if (raw) {
    split = {
      from_money: raw.fromMoney,
      from_price: raw.fromPrice,
      from_supply: raw.fromSupply,
      fixed_price_days: raw.fixedPriceDays,
      fixed_units_days: raw.fixedUnitsDays,
      change: raw.change,
    };
  }
}
console.log(
  JSON.stringify({
    date: last.date,
    state: last.state,
    days: last.days,
    growth: last.growthPerDay,
    fixed_price_days: last.fixedPriceDays,
    fixed_units_days: last.fixedUnitsDays,
    split: split,
  })
);
