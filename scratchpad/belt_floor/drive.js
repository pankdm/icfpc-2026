// drive.js — measure ticks-per-rotation of a littleman belt rig on the wasm oracle.
// Usage: node drive.js <file.man> <input> [--cap=N] [--warm=T0]
// Steps to cap (no expected output). For every runner it records the tick of each
// successful `s` and `r` (execute-then-move). Reports steady-state ticks/rotation
// = (tick_of_last_s - tick_of_first_steady_s) / (#s in that window), skipping the
// first --warm ticks as priming.
const { boot } = require('/Users/visenbaev/icfpc26/sim/harness.js');
const fs = require('fs');

(async () => {
  const argv = process.argv.slice(2);
  const flags = Object.fromEntries(argv.filter(a=>a.startsWith('--')).map(a=>{const [k,v]=a.slice(2).split('=');return [k, v===undefined?true:v];}));
  const pos = argv.filter(a=>!a.startsWith('--'));
  const file = pos[0];
  let input = pos[1] || "";
  const m = /^seq:(\d+)$/.exec(input);
  if (m) input = Array.from({length:+m[1]}, (_,i)=>i+1).join(' ');
  const cap = parseInt(flags.cap||'20000',10);
  const warm = parseInt(flags.warm||'800',10);
  const rows = fs.readFileSync(file,'utf8').replace(/\n$/,'').split('\n');
  const W = Math.max(...rows.map(r=>r.length));
  const glyph = (x,y)=>(rows[y]&&rows[y][x])||' ';

  const w = await boot();
  const s = w.newSession();
  let j = JSON.parse(w.load(s, rows, input, "", ""));
  if (j.type==='error'){ console.log('LOAD ERROR:', j.message, j.pos); process.exit(2); }

  // per-runner: {sTicks:[], rTicks:[], visits:{glyph:count}, stalls}
  const R = new Map();
  const prevPos = new Map(), prevState = new Map();
  let step = 0, halted=false, faulted=null;
  while (step < cap) {
    const cur = JSON.parse(step===0 ? w.stepN(s,1,false) : w.stepN(s,1,false));
    step = cur.step;
    if (cur.type==='error'){ faulted = cur.message; break; }
    // examine runners at PREVIOUS snapshot j, compare pos to cur to detect moves
    for (const r of (j.entities?.runners||[])) {
      if (r.halted) continue;
      const [x,y]=r.pos, g=glyph(x,y);
      if (!R.has(r.id)) R.set(r.id,{s:[],r:[],vis:{},stall:0});
      const rec=R.get(r.id);
      rec.vis[g]=(rec.vis[g]||0)+1;
      const now = R.get(r.id);
      const cr = (cur.entities?.runners||[]).find(u=>u.id===r.id);
      const moved = cr && (cr.pos[0]!==x || cr.pos[1]!==y);
      const stateKey = `${r.pos},${r.a},${r.b},${r.backpack}`;
      const cstate = cr?`${cr.pos},${cr.a},${cr.b},${cr.backpack}`:null;
      if (cstate===stateKey) now.stall++;
      if (g==='s' && moved) now.s.push(j.step);
      if ((g==='r'||g==='R'||g==='U') && moved) now.r.push(j.step);
    }
    j = cur;
    if (cur.halted){ halted=true; break; }
  }
  w.closeSession(s);

  const summ = [];
  for (const [id,rec] of R) {
    const steadyS = rec.s.filter(t=>t>=warm);
    const steadyR = rec.r.filter(t=>t>=warm);
    let tpr=null, n=0, span=0;
    if (steadyS.length>=4){ n=steadyS.length; span=steadyS[n-1]-steadyS[0]; tpr = span/(n-1); }
    const opCells = Object.entries(rec.vis).filter(([g])=>!' .<>^vV'.includes(g)).reduce((a,[,c])=>a+c,0);
    summ.push({id, sends:rec.s.length, recvs:rec.r.length, steadySends:steadyS.length, tpr, stalls:rec.stall, opVisits:opCells});
  }
  summ.sort((a,b)=>b.sends-a.sends);
  console.log(JSON.stringify({file:file.split('/').pop(), step, halted, faulted, cap, warm, runners:summ}, null, 0));
})().catch(e=>{console.error(String(e).slice(0,500));process.exit(1)});
