// ponytail: node-Selbstcheck statt Test-Framework — nur die Datumsarithmetik in app.js ist testwürdig.
function shiftDate(dateStr, days) {
  const d = new Date(dateStr + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

const cases = [
  ["2026-07-18", 1, "2026-07-19"],
  ["2026-07-31", 1, "2026-08-01"],
  ["2026-08-01", -1, "2026-07-31"],
  ["2026-12-31", 1, "2027-01-01"],
  ["2028-02-28", 1, "2028-02-29"],
];

let ok = true;
for (const [d, n, expected] of cases) {
  const got = shiftDate(d, n);
  if (got !== expected) {
    console.log(`FAIL: shiftDate(${d}, ${n}) = ${got}, expected ${expected}`);
    ok = false;
  }
}
console.log(ok ? "PASS" : "FAIL");
process.exit(ok ? 0 : 1);
