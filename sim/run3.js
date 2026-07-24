const { main } = require('./trace.js');
const { room } = require('./grid.js');

// Same as headon but vary copy's drop column to change approach parity on row3.
// copyDrop=2 -> even sep (same-cell); 3 -> odd sep (adjacency -> swap attempt).
const mk = (copyDrop) => room(9, 5, [
  [1,4,'@'], [5,4,'^'], [5,2,'Y'],
  [8,2,'v'], [8,3,'<'],
  [copyDrop,2,'v'], [copyDrop,3,'>'],
]);

main([
  { name: 'swap attempt (odd sep, copyDrop=3)', steps: 16, dumpFinal: true, rows: mk(3) },
  { name: 'sanity (even sep, copyDrop=4)',       steps: 16, dumpFinal: true, rows: mk(4) },
]);
