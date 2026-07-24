// Differential fuzzer: generate random littleman programs and diff Rust `lm` vs the oracle
// per-step (runners + pipe values + output + end). Reports the first divergence with the grid.
//
//   node sim/fuzz.js [count] [seed] [--pipes] [--steps=N]
const { boot } = require('./harness.js');
const dt = require('./difftest.js');

// ---- tiny seeded RNG ----
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Instruction alphabet for interior fill (weighted toward movement/arith; pipe ops sparse).
const OPS = ('....    >><<^^vv' + 'MWNbmdax]+-*/%&|~{}X0123456789@Y' + 'HH').split('');
const OPS_PIPE = OPS.concat('srRUqsS'.split(''));

function randRoom(rng, opts = {}) {
  const iw = 3 + Math.floor(rng() * 6); // interior 3..8
  const ih = 2 + Math.floor(rng() * 5); // interior 2..6
  const W = iw + 2, H = ih + 2;
  const g = Array.from({ length: H }, () => Array(W).fill(' '));
  for (let x = 0; x < W; x++) { g[0][x] = '-'; g[H - 1][x] = '-'; }
  for (let y = 0; y < H; y++) { g[y][0] = '|'; g[y][W - 1] = '|'; }
  g[0][0] = g[0][W - 1] = g[H - 1][0] = g[H - 1][W - 1] = '+';
  const alpha = opts.pipeOps ? OPS_PIPE : OPS;
  // ensure at least one '@'
  const ax = 1 + Math.floor(rng() * iw), ay = 1 + Math.floor(rng() * ih);
  for (let y = 1; y < H - 1; y++)
    for (let x = 1; x < W - 1; x++)
      g[y][x] = alpha[Math.floor(rng() * alpha.length)];
  g[ay][ax] = '@';
  return g.map(r => r.join(''));
}

// Two rooms connected by a vertical pipe, both with random interiors (+ optional IO).
function randPipeProgram(rng) {
  const src = randRoom(rng, { pipeOps: true });
  const dst = randRoom(rng, { pipeOps: true });
  const w = Math.max(src[0].length, dst[0].length);
  const pad = s => s.padEnd(w, ' ');
  const plen = 2 + Math.floor(rng() * 2);
  const rows = [];
  src.forEach(r => rows.push(pad(r)));
  for (let i = 0; i < plen; i++) rows.push(pad(' v'));
  dst.forEach(r => rows.push(pad(r)));
  return rows;
}

// A display fed by one driver room via a single pipe on a chosen side. Driver interior is
// randomised, so the man sends arbitrary values (incl. out-of-range -> fatal parity) and
// drives the cursor around. Display is 2x2.
function randDispProgram(rng) {
  const side = ['data', 'addr', 'swap'][Math.floor(rng() * 3)];
  // driver interior 4x2, random ops incl. digits, arith, s (send), arrows
  const dalpha = ('..>><<^^vv' + '0123456789MW+-*NX' + 'sss').split('');
  const di = () => dalpha[Math.floor(rng() * dalpha.length)];
  // driver 6x4 box (interior 4x2)
  const drv = [
    '+----+',
    '|' + [di(), di(), di(), di()].join('') + '|',
    '|' + [di(), di(), di(), di()].join('') + '|',
    '+----+',
  ];
  // place @ somewhere in interior
  const ax = 1 + Math.floor(rng() * 4), ay = 1 + Math.floor(rng() * 2);
  drv[ay] = drv[ay].slice(0, ax) + '@' + drv[ay].slice(ax + 1);
  const disp = ['+==+', ':..:', ':..:', '+==+'];
  const pad = (s, w) => s.padEnd(w, ' ');
  if (side === 'data') {
    // driver left, display right, DATA pipe '>>' into display left row (row1 of display)
    const rows = [];
    const W = 6 + 2 + 4;
    rows.push(pad(drv[0], W));
    rows.push(pad(drv[1] + '>>' + disp[1], W));
    rows.push(pad(drv[2] + '  ' + disp[2], W));
    rows.push(pad(drv[3], W));
    return rows;
  } else if (side === 'addr') {
    // driver on top, display below, ADDR pipe 'v' at col1 down into display top
    return [...drv, ' v', ' v', ...disp];
  } else {
    // display on top, driver below, SWAP pipe '^' at col1 up into display bottom
    return [...disp, ' ^', ' ^', ...drv];
  }
}

// Two rooms stacked, connected by TWO vertical pipes (top->bottom) at two columns.
// Bottom room has two incoming pipes, top room two outgoing -> stresses nearest (s/r/q)
// and reading-order (R/U) selection.
function randMultiPipe(rng) {
  const alpha = OPS_PIPE.concat('sSrRUq'.split(''));
  const iw = 6;
  const mkroom = () => {
    const box = ['+------+'];
    for (let y = 0; y < 3; y++) {
      let row = '|';
      for (let x = 0; x < iw; x++) row += alpha[Math.floor(rng() * alpha.length)];
      box.push(row + '|');
    }
    box.push('+------+');
    const ax = 1 + Math.floor(rng() * iw), ay = 1 + Math.floor(rng() * 3);
    box[ay] = box[ay].slice(0, ax) + '@' + box[ay].slice(ax + 1);
    return box;
  };
  const top = mkroom(), bot = mkroom();
  const rows = [...top];
  const plen = 2 + Math.floor(rng() * 2);
  // pipes at columns 2 and 5
  for (let i = 0; i < plen; i++) rows.push('  v  v  ');
  rows.push(...bot);
  return rows;
}

(async () => {
  const w = await boot();
  dt.setW(w);
  const count = parseInt(process.argv[2] || '2000');
  const baseSeed = parseInt(process.argv[3] || '1');
  const usePipes = process.argv.includes('--pipes');
  const useDisp = process.argv.includes('--disp');
  const useMulti = process.argv.includes('--multi');
  const stepsArg = process.argv.find(a => a.startsWith('--steps='));
  const steps = stepsArg ? parseInt(stepsArg.split('=')[1]) : 60;

  let ok = 0, div = 0, loadErr = 0;
  const rng = mulberry32(baseSeed);
  for (let i = 0; i < count; i++) {
    const rows = useDisp ? randDispProgram(rng)
      : useMulti ? randMultiPipe(rng)
      : usePipes ? randPipeProgram(rng)
      : randRoom(rng, { pipeOps: rng() < 0.3 });
    const input = rng() < 0.5 ? '' : String(Math.floor(rng() * 200) - 100);
    const opt = { input };
    if (useDisp) opt.frames = JSON.stringify([[['00', '00'], ['11', '22']]]);
    const res = dt.compareFull(`fuzz#${i}`, rows, steps, opt);
    if (res.ok) { ok++; if (res.r.includes('load-error')) loadErr++; }
    else {
      div++;
      console.log('\n=== DIVERGENCE ===');
      for (const r of rows) console.log('   |' + r);
      console.log('   input:', JSON.stringify(input));
      console.log(res.r);
      if (div >= 5) break;
    }
  }
  console.log(`\nfuzz: ${ok} ok (${loadErr} load-errors agreed), ${div} divergences / ${count}`);
  process.exit(div ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
