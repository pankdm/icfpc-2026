const { main } = require('./trace.js');
main([
  { name: 'baseline fork (sanity)', steps: 6, rows: [
    '+-----+',
    '|     |',
    '|     |',
    '|@ Y  |',
    '|     |',
    '|     |',
    '+-----+'] },

  // Converging men, EVEN gap: copy(north, reflected south) vs original(south, reflected north)
  // meet in column 3. Watch for same-cell landing vs pass-through, and whether they halt.
  { name: 'converging (reflectors), gap A', steps: 16, dumpFinal: true, rows: [
    '+-----+',
    '|  v  |',
    '|     |',
    '|@ Y  |',
    '|  ^  |',
    '|     |',
    '+-----+'] },

  // Converging, different spacing to flip parity.
  { name: 'converging (reflectors), gap B', steps: 16, dumpFinal: true, rows: [
    '+-----+',
    '|  v  |',
    '|     |',
    '|     |',
    '|@ Y  |',
    '|  ^  |',
    '+-----+'] },

  // Moving man walks into a HALTED man. Original halts on the H just south of Y;
  // copy loops back down the same column and reaches the halted man.
  { name: 'walk into halted man', steps: 16, dumpFinal: true, rows: [
    '+-----+',
    '|  v  |',
    '|     |',
    '|@ Y  |',
    '|  H  |',
    '+-----+'] },
]);
