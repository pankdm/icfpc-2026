// P4: how many little men can coexist? (`maxRunners` cap -- OPEN in the docs)
//
// A 4-tick fork loop in the bottom-left corner extrudes one clone every 4 ticks.
// Each clone walks north up column 2, then serpentines across the whole room and
// dies on an H. Clones all follow the same track at the same speed, so they never
// collide; live population grows until the track is saturated (~len/4) or the
// engine refuses to fork.
const { boot } = require('./harness.js');

function build(W, H) {
  const g = Array.from({ length: H }, () => Array(W).fill(' '));
  for (let x = 0; x < W; x++) { g[0][x] = '-'; g[H - 1][x] = '-'; }
  for (let y = 0; y < H; y++) { g[y][0] = '|'; g[y][W - 1] = '|'; }
  g[0][0] = g[0][W - 1] = g[H - 1][0] = g[H - 1][W - 1] = '+';

  // fork loop (@ sits OUTSIDE the cycle, since '@' is a nop and cannot turn him):
  //   > Y     east onto Y -> original turns S, clone spawns N of Y facing N
  //   ^ <     original walks the 2x2 cycle back onto the '>' -> 4 ticks per fork
  g[H - 3][1] = '@'; g[H - 3][2] = '>'; g[H - 3][3] = 'Y';
  g[H - 2][3] = '<'; g[H - 2][2] = '^';

  // feed corridor: clones spawn at (3,H-4) facing north, walk up column 3 to row 1
  for (let y = 1; y <= H - 4; y++) g[y][3] = '.';
  g[1][3] = '>';                                  // turn east into the serpentine

  // boustrophedon over rows 1..H-4, columns 4..W-2
  const last = H - 4;
  for (let y = 1; y <= last; y++) {
    for (let x = 4; x <= W - 2; x++) if (g[y][x] === ' ') g[y][x] = '.';  // keep entry turns
    const eastward = (y % 2 === 1);
    if (y === last) { g[y][eastward ? W - 2 : 4] = 'H'; break; }
    if (eastward) { g[y][W - 2] = 'v'; g[y + 1][W - 2] = '<'; }
    else { g[y][4] = 'v'; g[y + 1][4] = '>'; }
  }
  return g.map(r => r.join(''));
}

async function main() {
  const W = 24, H = 24, STEPS = 3000;
  const rows = build(W, H);
  const w = await boot();
  const s = w.newSession();
  const j0 = JSON.parse(w.load(s, rows, '', '', ''));
  for (const r of rows) console.log('   |' + r);
  if (j0.type === 'error') { console.log('LOAD ERROR:', j0.message, j0.pos); process.exit(1); }

  let max = 0, maxAt = 0, maxId = 0;
  for (let i = 1; i <= STEPS; i++) {
    const j = JSON.parse(w.step(s));
    if (j.type === 'error') { console.log(`t${i}: STEP-ERROR`, j.message); break; }
    const rs = (j.entities && j.entities.runners) || [];
    if (rs.length > max) { max = rs.length; maxAt = i; }
    for (const r of rs) if (r.id > maxId) maxId = r.id;
    if (j.halted) { console.log(`t${i}: END reason=${j.reason} ${JSON.stringify(j.fatal || {})}`); break; }
    if (i % 500 === 0) console.log(`t${i}: live=${rs.length} maxIdSeen=${maxId}`);
  }
  console.log(`\nmax simultaneous men = ${max} (at t${maxAt}); highest entity id seen = ${maxId}`);
  process.exit(0);
}
main();
