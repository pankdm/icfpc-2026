const { boot } = require('/Users/visenbaev/icfpc26/sim/harness.js');
const L = require('/Users/visenbaev/icfpc26/tools/lib.js');
function run(w, name, rows, input, exp) {
  const s = w.newSession(); let j;
  try { j = JSON.parse(w.load(s, rows, input, exp, '')); }
  catch (e) { console.log(name.padEnd(24), 'EXC', e.message); w.closeSession(s); return; }
  if (j.type === 'error') { console.log(name.padEnd(24), 'LOAD-ERR:', j.message); w.closeSession(s); return; }
  let n = j;
  for (let k = 0; k < 100 && !n.halted && !n.outputSettled; k++) {
    const nn = JSON.parse(w.stepN(s, 200, false));
    if (nn.type === 'error') { n = nn; break; }
    if (nn.step === n.step) { n = nn; break; }
    n = nn;
  }
  console.log(name.padEnd(24), 'out=' + JSON.stringify(n.output || []),
    'halt=' + n.halted, 'r=' + (n.reason || (n.fatal && n.fatal.reason) || '-'));
  w.closeSession(s);
}
(async () => {
  const w = await boot();
  // E: arrowhead embedded in I bottom wall -> pipe is I-bottom 'v' + one cell -> seq wall.
  // I rows0-2, 'v' in bottom wall row2 col1, pipe cell row3, seq wall row4.
  run(w, 'E arrow-in-Ibot', [
    '+-+    ',
    '|I|    ',
    '+v+    ',
    ' v     ',
    '+-----+',
    '|@rs  |',
    '+-----+',
    ' v     ',
    ' v     ',
    '+-+    ',
    '|O|    ',
    '+-+    '], '5', '5');
  // F: arrowheads in BOTH the I bottom wall and seq top wall (pipe = 2 wall cells, 0 gap rows)
  run(w, 'F arrows-both-walls', [
    '+-+    ',
    '|I|    ',
    '+v+    ',   // I bottom wall row2 with v
    '+v+---+',   // seq top wall row3 with v  (rooms abut, 1 row apart)
    '|@rs  |',
    '+-----+'], '5', '5');
  // G: seq top wall 'v' + 1 pipe cell + I bottom wall 'v' (2 pipe cells total incl wall arrows)
  run(w, 'G wallarrow+1', [
    '+-+    ',
    '|I|    ',
    '+v+    ',
    ' v     ',   // 1 free pipe cell
    '+v+---+',   // seq wall with v
    '|@rs  |',
    '+-----+'], '5', '5');
  // H: baseline minimal vertical (I room, 2 free pipe cells, seq) for reference
  run(w, 'H baseline-2free', [
    '+-+    ',
    '|I|    ',
    '+-+    ',
    ' v     ',
    ' v     ',
    '+-----+',
    '|@rs  |',
    '+-----+'], '5', '5');
  process.exit(0);
})();
