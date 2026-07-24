const {boot,trace}=require('./lab.js');
const {grid,rect,put,toRows}=require('./build.js');

// Scenario 1: blocked man B as obstacle; mover A approaches B's cell.
// Main room interior cols 6..10, rows 1..4. Borders col5,col11 / row0,row5.
// I-room cols0..2 rows1..3 with 'I', pipe '>>' at cols3-4 row2 (empty input -> r blocks).
function buildS1(){
  const g=grid(12,6);
  rect(g,5,0,11,5);          // main room
  rect(g,0,1,2,3);           // I-room
  put(g,1,2,'I');            // input cell
  put(g,3,2,'>'); put(g,4,2,'>'); // pipe into main room (empty)
  // main-room contents
  put(g,6,1,'>');            // top-left corner turn E (return path re-entry)
  put(g,9,1,'r');            // B parks here (empty pipe)
  put(g,6,3,'@');            // spawn, faces E
  put(g,9,3,'Y');            // fork
  put(g,6,4,'^');            // bottom-left corner turn N
  put(g,9,4,'<');            // bottom-right corner turn W
  return toRows(g);
}
(async()=>{const w=await boot();
  await trace(w,'S1 blocked-obstacle',buildS1(),{input:'',steps:20});
  process.exit(0);
})();
