const {boot}=require((__dirname + '/../sim/harness.js'));
const {execSync}=require("child_process");
(async()=>{
 const w=await boot();
 const src=`+-+
|I|
+-+
 >-v
   v
+-----+  +-+
|>@Rsv|>>|O|
|^   <|  +-+
+-----+`;
 const rows=src.split("\n");
 const s=w.newSession();
 const j=JSON.parse(w.load(s,rows,"3 1 2 3","3 1 2 3",""));
 console.log("pipes:",JSON.stringify(j.entities.pipes));
 console.log("rooms:",JSON.stringify(j.entities.rooms.map(r=>({id:r.id,min:r.min,max:r.max}))));
})();
