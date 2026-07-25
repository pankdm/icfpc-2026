// Trace a man's path on the oracle. Usage: node trace.js <gridfile> [input] [steps]
const { boot } = require('../../sim/harness.js');
const fs = require('fs');
function dirName(d){if(!d)return'?';const[x,y]=d;if(x===1)return'E';if(x===-1)return'W';if(y===1)return'S';if(y===-1)return'N';return'?';}
function brief(snap){const rs=(snap.entities&&snap.entities.runners)||[];return rs.map(r=>`#${r.id}[${r.pos}]${dirName(r.dir)}${r.halted?'H':''} a${r.a} b${r.b} bp${r.backpack}`).join('  ');}
(async()=>{
  const [gf, input='', stepsS='40'] = process.argv.slice(2);
  const steps=parseInt(stepsS);
  const rows=fs.readFileSync(gf,'utf8').replace(/\r/g,'').split('\n');
  const w=await boot();const s=w.newSession();
  const j0=JSON.parse(w.load(s,rows,input,'',''));
  rows.forEach((r,i)=>console.log(String(i).padStart(2),'|'+r));
  if(j0.type==='error'){console.log('LOAD ERROR:',j0.message);process.exit(1);}
  console.log('load:',brief(j0),'out=',JSON.stringify(j0.output||[]));
  let last=j0;
  for(let i=0;i<steps;i++){
    const jj=JSON.parse(w.step(s));
    if(jj.type==='error'){console.log(`t${i+1}: ERROR ${jj.message}`);break;}
    console.log(`t${i+1}:`,brief(jj),jj.output&&jj.output.length?'out='+JSON.stringify(jj.output):'',jj.halted?'<<HALTED '+jj.reason+'>>':'');
    last=jj;
    if(jj.halted)break;
  }
  process.exit(0);
})();
