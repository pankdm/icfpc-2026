const { main } = require('./trace.js');
const { room } = require('./grid.js');

// Head-on: man climbs col5 into Y (heading north) -> original east, copy west on row2,
// both dropped to row3 and routed toward each other to collide near c5 (even gap).
const headonEven = room(9, 5, [
  [1,4,'@'], [5,4,'^'], [5,2,'Y'],
  [8,2,'v'], [8,3,'<'],
  [2,2,'v'], [2,3,'>'],
]);

// Odd gap: shift original's drop one cell west (7 instead of 8) to flip parity -> swap test.
const headonOdd = room(9, 5, [
  [1,4,'@'], [5,4,'^'], [5,2,'Y'],
  [7,2,'v'], [7,3,'<'],
  [2,2,'v'], [2,3,'>'],
]);

main([
  { name: 'head-on collision (even gap)', steps: 14, dumpFinal: true, rows: headonEven },
  { name: 'head-on / swap (odd gap)',     steps: 14, dumpFinal: true, rows: headonOdd },
]);
