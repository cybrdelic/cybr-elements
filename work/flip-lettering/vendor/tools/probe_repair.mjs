import {FlipSolver,makePreset} from '../src/flip.js';
import {FlipSolver as Reference,makePreset as makeReference} from '../src/flip-reference.js';
const [name='breach',quality='ultra',variant='repair',steps='4']=process.argv.slice(2);
const c=variant==='ii'?makeReference(name,quality):makePreset(name,quality);
if(['repair','hybrid'].includes(variant)){c.flip=.93;c.separation=true;}
if(variant==='hybrid')c.transfer='apic-flip';
const sim=new (variant==='ii'?Reference:FlipSolver)(c); const start=performance.now();
for(let f=0;f<Number(steps);f++){const m=sim.advance(1/48); console.log(JSON.stringify({variant,frame:f,particles:sim.count,h:c.h,time:m.time,wall:(performance.now()-start)/1000,substeps:m.substeps,speed:m.maxSpeed,energy:m.kineticEnergy,pressure:m.pressure}));}
