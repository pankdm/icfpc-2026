// Debug one .man against a single input string. Prints output, status, runner states.
//   node sim/dbg.js <file.man> "<input>" [maxTicks] [traceEvery]
const { boot } = require('./harness.js');
const fs = require('fs');

function dirName(d){ if(!d) return '?'; const[x,y]=d; if(x===1)return '>'; if(x===-1)return '<'; if(y===1)return 'v'; if(y===-1)return '^'; return '?'; }
function brief(j){ const rs=(j.entities&&j.entities.runners)||[]; return rs.map(r=>`#${r.id}@[${r.pos}]${dirName(r.dir)}${r.halted?'H':''}(a${r.a} b${r.b} bp${r.backpack})`).join('  '); }

(async () => {
  const [file, input, maxT, traceEvery] = process.argv.slice(2);
  const rows = fs.readFileSync(file,'utf8').replace(/\r/g,'').split('\n');
  const cap = parseInt(maxT||'20000',10);
  const te = parseInt(traceEvery||'0',10);
  const w = await boot();
  const s = w.newSession();
  let j = JSON.parse(w.load(s, rows, input||'', '', ''));
  if(j.type==='error'){ console.log('LOAD ERROR:', j.message); process.exit(1); }
  console.log('load:', brief(j));
  let last=j, t=0;
  while(!j.halted && j.step<cap){
    const nj = JSON.parse(w.stepN(s, te?1:2000, false));
    if(nj.type==='error'){ console.log('STEP ERROR @tick',nj.step,':',nj.message); j=nj; break; }
    if(nj.step===j.step){ j=nj; break; }
    j=nj;
    if(te && j.step%te===0) console.log(`t${j.step}:`, brief(j), j.output?('out=['+j.output+']'):'');
  }
  console.log('final tick:', j.step, 'halted:', j.halted, 'reason:', j.reason||(j.fatal&&j.fatal.reason)||'');
  console.log('output:', JSON.stringify(j.output||[]));
  console.log('state:', brief(j));
  process.exit(0);
})().catch(e=>{console.log('ERR',String(e));process.exit(1);});
