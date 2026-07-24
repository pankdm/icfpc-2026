// Oracle-validated greedy compaction: remove blank/'|'-only rows and
// blank/'-'-only columns as long as all 7 public cases still pass 7/7.
// Ground truth = wasm oracle via harness/gradeAll.
//   node compact_oracle.js <in.man> <out.man> [--rows-only]
const { boot } = require('../../sim/harness.js');
const L = require('../../tools/lib.js');
const fs = require('fs');

function pad(rows){ const w=Math.max(...rows.map(r=>r.length)); return rows.map(r=>r.padEnd(w)); }
function render(rows){ return rows.map(r=>r.replace(/\s+$/,'')).join('\n'); }
function removableRow(rows,i){ const s=new Set([...rows[i]].filter(c=>c!==' ')); return s.size===0 || (s.size===1 && s.has('|')); }
function removableCol(rows,j){ const s=new Set(rows.map(r=>r[j]).filter(c=>c!==' ')); return s.size===0 || (s.size===1 && s.has('-')); }

(async()=>{
  const [inp,outp,flag]=process.argv.slice(2);
  const rowsOnly = flag==='--rows-only';
  const problem = await L.fetchProblem('matmul');
  const w = await boot();
  const ok = (rows)=>{ const g=L.gradeAll(w, render(rows).split('\n'), problem); return g.passed===g.total ? g : null; };

  let rows = pad(L.manRows(fs.readFileSync(inp,'utf8')));
  const base = ok(rows);
  if(!base){ console.error('BASELINE FAILS'); process.exit(1); }
  console.log(`baseline ${base.footprint.w}x${base.footprint.h} box ${base.footprint.box} avg ${base.avgTicks.toFixed(1)} score ${Math.round(base.score)}`);

  let changed=true, nRow=0, nCol=0;
  while(changed){
    changed=false;
    for(let i=0;i<rows.length;i++){
      if(!removableRow(rows,i)) continue;
      const cand=rows.slice(0,i).concat(rows.slice(i+1));
      if(ok(pad(cand))){ rows=pad(cand); changed=true; nRow++; break; }
    }
    if(changed) continue;
    if(rowsOnly) break;
    const wI=rows[0].length;
    for(let j=0;j<wI;j++){
      if(!removableCol(rows,j)) continue;
      const cand=rows.map(r=>r.slice(0,j)+r.slice(j+1));
      if(ok(pad(cand))){ rows=pad(cand); changed=true; nCol++; break; }
    }
  }
  const g=ok(rows);
  fs.writeFileSync(outp, render(rows)+'\n');
  console.log(`removed ${nRow} rows, ${nCol} cols`);
  console.log(`result   ${g.footprint.w}x${g.footprint.h} box ${g.footprint.box} avg ${g.avgTicks.toFixed(1)} score ${Math.round(g.score)}`);
  console.log(`wrote ${outp}`);
})().catch(e=>{console.error(e);process.exit(1);});
