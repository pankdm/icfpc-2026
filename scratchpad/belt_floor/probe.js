const { boot } = require('/Users/visenbaev/icfpc26/sim/harness.js');
(async () => {
  const w = await boot();
  const s = w.newSession();
  // tiny: Input -> main room does r s r s ... -> Output
  const rows = [
    "+--------+",
    "|@rsrsrsv|",
    "|  ^ < < |",
    "+--------+",
    " |      | ",
    " ^      v ",
    "+-+    +-+",
    "|I|    |O|",
    "+-+    +-+",
  ];
  let j = JSON.parse(w.load(s, rows, "5 6 7 8 9 10 11 12", "", ""));
  console.log("load:", JSON.stringify(j).slice(0,300));
  for (let i=0;i<8;i++){ j=JSON.parse(w.stepN(s,1,false)); }
  console.log("after8:", JSON.stringify(j).slice(0,600));
  w.closeSession(s);
})().catch(e=>{console.error(String(e).slice(0,500));process.exit(1)});
