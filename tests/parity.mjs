import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const Pmb = require("../js/metric.js");

const input = JSON.parse(process.argv[2]);
const out = Pmb.computeBailout(input.money, input.btc, {
  amount: input.amount,
  unit: input.unit,
  method: input.method,
});
if (!out.points.length) {
  console.log(JSON.stringify({ date: null, state: "insufficient", days: null }));
  process.exit(0);
}
const last = out.points[out.points.length - 1];
console.log(
  JSON.stringify({
    date: last.date,
    state: last.state,
    days: last.days,
  })
);
