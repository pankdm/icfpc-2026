const { boot, trace } = require('./lab.js');
(async()=>{const w=await boot();
  const rows=[
    '+-+               ',
    '|I|               ',
    '+-+               ',
    ' v                ',
    ' v +------------+ ',
    ' >>|@rM*+M2W/s | ',
    '   +------------+ ',
  ];
  await trace(w,'tri linear',rows,{input:'4',steps:30});
  process.exit(0);
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
