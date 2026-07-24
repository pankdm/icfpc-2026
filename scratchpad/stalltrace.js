// Attribute every STALLED man-tick to (position, glyph, blocked-kind).
// A man is stalled if pos+a+b+backpack unchanged since last tick.
// Glyph r/R/U => blocked RECEIVE (upstream pipe empty); s/S => blocked SEND (downstream full).
const { boot } = require('/Users/visenbaev/icfpc26/sim/harness.js');
const fs = require('fs'), path = require('path');
function buildCase(tc){const rounds=tc.rounds||[{in:tc.in||[],out:tc.out||[]}];return{
  input:rounds.map(r=>(r.in||[]).join(' ')).join(' / '),
  expected:rounds.map(r=>(r.out||[]).join(' ')).join(' / '),
  frames:rounds.map(r=>r.frames||[])};}
(async()=>{
  const [slug,file,ci]=[process.argv[2],process.argv[3],parseInt(process.argv[4]||'0',10)];
  const spec=JSON.parse(fs.readFileSync(path.join('tests',slug+'.json'),'utf8'));
  const tc=spec.publicTestData[ci];const {input,expected,frames}=buildCase(tc);
  const isDisp=frames.some(f=>f.length);
  const rows=fs.readFileSync(file,'utf8').replace(/\n$/,'').split('\n');
  const cellAt=(x,y)=>(rows[y]&&rows[y][x])||' ';
  const w=await boot();const s=w.newSession();
  let j=JSON.parse(w.load(s,rows,input,expected,isDisp?JSON.stringify(frames):''));
  if(j.type==='error'){console.log('LOAD ERR',j.message);process.exit(1);}
  const prev=new Map();           // id -> state key
  const stallByCell=new Map();    // "x,y glyph" -> count
  const kind={recv:0,send:0,other:0};
  const cap=spec.tickCap||5e6;
  while(!j.halted&&!j.outputSettled&&j.step<cap){
    for(const r of (j.entities?.runners||[])){
      if(r.halted)continue;
      const key=`${r.pos},${r.a},${r.b},${r.backpack}`;
      if(prev.get(r.id)===key){
        const g=cellAt(r.pos[0],r.pos[1]);
        const ck=`${r.pos[0]},${r.pos[1]} '${g}'`;
        stallByCell.set(ck,(stallByCell.get(ck)||0)+1);
        if('rRU'.includes(g))kind.recv++; else if('sS'.includes(g))kind.send++; else kind.other++;
      }
      prev.set(r.id,key);
    }
    const nj=JSON.parse(w.stepN(s,1,false));
    if(nj.type==='error'||nj.step===j.step){j=nj;break;}
    j=nj;
  }
  w.closeSession(s);
  const tot=kind.recv+kind.send+kind.other||1;
  console.log(`${path.basename(file)} [${slug} case ${ci}] settle=${j.step}`);
  console.log(`STALL kind: RECV(empty upstream) ${kind.recv} (${(100*kind.recv/tot).toFixed(0)}%)  SEND(full downstream) ${kind.send} (${(100*kind.send/tot).toFixed(0)}%)  OTHER ${kind.other} (${(100*kind.other/tot).toFixed(0)}%)`);
  console.log('TOP STALL CELLS:');
  [...stallByCell.entries()].sort((a,b)=>b[1]-a[1]).slice(0,12).forEach(([k,v])=>console.log(`  ${String(v).padStart(6)}  ${k}`));
  process.exit(0);
})().catch(e=>{console.error(String(e).slice(0,300));process.exit(1);});
