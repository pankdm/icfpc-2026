const { boot } = require('./harness.js');

function dir(d){const m={'1,0':'>','-1,0':'<','0,1':'v','0,-1':'^'};return d?(m[d+'']||'?'):'-';}
function line(j){
  const rs=(j.entities&&j.entities.runners)||[];
  return rs.map(r=>`#${r.id}[${r.pos}]${dir(r.dir)}${r.halted?'H':''}`).join(' ')
    +(j.output&&j.output.length?` out=[${j.output}]`:'')
    +(j.halted?` <<${j.reason}${j.fatal?':'+j.fatal.reason:''}>>`:'');
}

async function trace(w, name, rows, input, steps, inputFn){
  const s=w.newSession();
  const j0=JSON.parse(w.load(s,rows,input||'','',''));
  console.log('\n### '+name+(input?`  (input="${input}")`:'  (no input)'));
  rows.forEach(r=>console.log('   '+r));
  if(j0.type==='error'){console.log('LOAD ERROR:',j0.message); w.closeSession(s); return;}
  console.log('t0 '+line(j0));
  for(let i=0;i<steps;i++){
    const j=JSON.parse(w.step(s));
    if(j.type==='error'){console.log('ERR',j.message);break;}
    console.log('t'+(i+1)+' '+line(j));
    if(j.halted)break;
  }
  w.closeSession(s);
}
module.exports={boot,trace,line,dir};

if(require.main===module){
(async()=>{const w=await boot();
  await trace(w,'block-confirm',[
    '+-+  +----+',
    '|I|>>|@r H|',
    '+-+  +----+'], '', 8);
  await trace(w,'block-then-unblock',[
    '+-+  +----+',
    '|I|>>|@r H|',
    '+-+  +----+'], '7', 8);
  process.exit(0);
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
}
