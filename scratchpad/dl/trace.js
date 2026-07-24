// Trace runner positions per tick. usage: node trace.js <file.man> "<input>" [steps] [expected]
const { boot } = require('../../sim/harness.js');
const fs = require('fs');
function dn(d){const[x,y]=d||[0,0];return x===1?'E':x===-1?'W':y===1?'S':y===-1?'N':'?';}
(async()=>{
  const [file,input,steps,expected]=process.argv.slice(2);
  const rows=fs.readFileSync(file,'utf8').replace(/\n$/,'').split('\n');
  const w=await boot();const s=w.newSession();
  let j=JSON.parse(w.load(s,rows,input||'',expected||'',''));
  if(j.type==='error'){console.log('LOAD ERROR:',j.message);process.exit(0);}
  const N=parseInt(steps||'60');
  rows.forEach((r,i)=>console.log(String(i).padStart(2),'|'+r));
  const brief=jj=>((jj.entities&&jj.entities.runners)||[]).map(r=>`#${r.id}[${r.pos}]${dn(r.dir)}${r.halted?'H':''}(a${r.a} b${r.b} bp${r.backpack})`).join(' ');
  console.log('t0:',brief(j),j.output?'out='+JSON.stringify(j.output):'');
  for(let i=0;i<N;i++){
    const jj=JSON.parse(w.step(s));
    if(jj.type==='error'){console.log('t'+(i+1)+' ERR',jj.message);break;}
    console.log('t'+(i+1)+':',brief(jj),jj.output&&jj.output.length?'out='+JSON.stringify(jj.output):'', jj.halted?'HALT '+jj.reason:'');
    if(jj.halted)break;
    j=jj;
  }
  w.closeSession(s);process.exit(0);
})().catch(e=>{console.error(e);process.exit(1);});
