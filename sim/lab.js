const { boot } = require('./harness.js');

function dir(d){const m={'1,0':'E','-1,0':'W','0,1':'S','0,-1':'N'};return d?(m[d+'']||'?'):'-';}
function line(j){
  const rs=(j.entities&&j.entities.runners)||[];
  const rstr = rs.map(r=>`#${r.id}@[${r.pos}]${dir(r.dir)}${r.halted?'!H':''}`).join('  ');
  let extra='';
  if(j.output&&j.output.length) extra+=` out=[${JSON.stringify(j.output)}]`;
  if(j.halted) extra+=` <<HALTED ${j.reason}${j.fatal?' FATAL:'+j.fatal.reason+'@'+j.fatal.pos+' cell='+j.fatal.cell:''}>>`;
  return rstr+extra;
}

// steps can be a number, or an object { n, inputs: {tickIndex: 'char'} } -- but wasm has fixed input at load.
async function trace(w, name, rows, opts={}){
  const {input='', steps=12, expected='', showLoad=true} = opts;
  const s=w.newSession();
  const j0=JSON.parse(w.load(s,rows,input,expected,''));
  console.log('\n=== '+name+' ===  input='+JSON.stringify(input));
  if(showLoad) rows.forEach(r=>console.log('   |'+r));
  if(j0.type==='error'){console.log('LOAD ERROR:',j0.message,j0.pos||''); w.closeSession(s); return {err:j0.message};}
  console.log('t0  '+line(j0));
  let last=j0;
  for(let i=0;i<steps;i++){
    const j=JSON.parse(w.step(s));
    if(j.type==='error'){console.log('t'+(i+1)+'  STEP-ERR',j.message);last=j;break;}
    console.log('t'+(i+1)+'  '+line(j));
    last=j;
    if(j.halted)break;
  }
  w.closeSession(s);
  return last;
}
module.exports={boot,trace,line,dir};

if(require.main===module){
(async()=>{const w=await boot();
  // Understand Y fork: single man walking east onto a Y in a big room.
  await trace(w,'Y-fork basic',[
    '+---------+',
    '|@   Y    |',
    '|         |',
    '|         |',
    '+---------+'], {steps:8});
  process.exit(0);
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
}
