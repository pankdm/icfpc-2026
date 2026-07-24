const { boot } = require('./harness.js');
const T = n => n*(n+1)/2;
function fp(rows){let a=1e9,b=1e9,c=-1,d=-1;rows.forEach((r,y)=>{for(let x=0;x<r.length;x++)if(r[x]!==' '){a=Math.min(a,x);c=Math.max(c,x);b=Math.min(b,y);d=Math.max(d,y);}});const w=c-a+1,h=d-b+1;return{w,h,box:Math.max(w,h)**2};}
async function test(w,name,rows){
  const f=fp(rows);
  let allok=true, tick=null;
  for(const n of [0,1,4,987]){
    const s=w.newSession(); let j=JSON.parse(w.load(s,rows,String(n),String(T(n)),''));
    if(j.type==='error'){ w.closeSession(s); console.log(`${name}: LOAD ERROR: ${j.message}`); return;}
    for(let i=0;i<2000&&!j.halted&&!j.outputSettled;i++) j=JSON.parse(w.stepN(s,5000,false));
    const out=(j.output||[]).join(' '); const ok=out===String(T(n)); if(!ok)allok=false; if(n===4)tick=j.step;
    w.closeSession(s);
    if(!ok){console.log(`${name}: n=${n} FAIL out=[${out}] exp=${T(n)}`); return;}
  }
  console.log(`${name}: PASS all  footprint ${f.w}x${f.h} box ${f.box}  ~${tick}t  score~${f.box*tick}`);
}
(async()=>{const w=await boot();
 await test(w,'user-noH (9x7)',["+-+   +-+","|I|  >|O|","+-+>v^+-+","+-------+","|@rM*+Wv|"," .s/W2<|".padStart(8,' ').replace(/^ /,'|'),"+-------+"].map(r=>r));
 // careful build of user-noH:
 await test(w,'user-noH',["+-+   +-+","|I|  >|O|","+-+>v^+-+","+-------+","|@rM*+Wv|","| .s/W2<|","+-------+"]);
 process.exit(0);})();
