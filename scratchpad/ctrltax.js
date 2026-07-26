// Per-MAN breakdown: for each man, classify its non-stall ticks compute/turn/nop, count stall.
const { boot } = require((__dirname + '/../sim/harness.js'));
const fs=require('fs'),path=require('path');
const TURN=new Set(['<','>','^','v','V']);const NOP=new Set([' ','.','']);
const cls=ch=>TURN.has(ch)?'turn':NOP.has(ch)?'nop':'op';
function buildCase(tc){const R=tc.rounds||[{in:tc.in||[],out:tc.out||[]}];return{
  input:R.map(r=>(r.in||[]).join(' ')).join(' / '),expected:R.map(r=>(r.out||[]).join(' ')).join(' / '),frames:R.map(r=>r.frames||[])};}
(async()=>{
  const [slug,file,ci]=[process.argv[2],process.argv[3],parseInt(process.argv[4]||'0',10)];
  const spec=JSON.parse(fs.readFileSync(path.join('tests',slug+'.json'),'utf8'));
  const tc=spec.publicTestData[ci];const {input,expected,frames}=buildCase(tc);const isDisp=frames.some(f=>f.length);
  const rows=fs.readFileSync(file,'utf8').replace(/\n$/,'').split('\n');const cellAt=(x,y)=>(rows[y]&&rows[y][x])||' ';
  const w=await boot();const s=w.newSession();
  let j=JSON.parse(w.load(s,rows,input,expected,isDisp?JSON.stringify(frames):''));
  const per=new Map();const prev=new Map();const cap=spec.tickCap||5e6;
  while(!j.halted&&!j.outputSettled&&j.step<cap){
    for(const r of (j.entities?.runners||[])){
      if(r.halted)continue;
      if(!per.has(r.id))per.set(r.id,{op:0,turn:0,nop:0,stall:0,send:0});
      const p=per.get(r.id);const key=`${r.pos},${r.a},${r.b},${r.backpack}`;const g=cellAt(r.pos[0],r.pos[1]);
      if(prev.get(r.id)===key)p.stall++;
      else{const c=cls(g);p[c]++;if('sS'.includes(g))p.send++;}
      prev.set(r.id,key);
    }
    const nj=JSON.parse(w.stepN(s,1,false));if(nj.type==='error'||nj.step===j.step){j=nj;break;}j=nj;
  }
  w.closeSession(s);
  console.log(`${path.basename(file)} case ${ci} settle=${j.step}`);
  [...per.entries()].sort((a,b)=>b[1].op-a[1].op).forEach(([id,p])=>{
    const tot=p.op+p.turn+p.nop+p.stall||1;const pct=k=>(100*k/tot).toFixed(0)+'%';
    console.log(`  man#${id}: total ${tot}  op ${p.op}(${pct(p.op)}) [send ${p.send}]  turn ${p.turn}(${pct(p.turn)})  nop ${p.nop}(${pct(p.nop)})  stall ${p.stall}(${pct(p.stall)})`);
  });
  process.exit(0);
})().catch(e=>{console.error(String(e).slice(0,300));process.exit(1);});
