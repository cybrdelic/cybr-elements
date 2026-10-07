// Keep display pacing out of the physical clock. Bounded debt prevents a
// suspended tab or overloaded GPU from building an unbounded catch-up queue.
export class SimulationClock {
  constructor(now=null){this.last=now;this.debt=0;this.dropped=0;}
  tick(now,running=true){
    if(!Number.isFinite(now))throw Error('Invalid simulation clock');
    const dt=this.last===null?0:Math.max(0,(now-this.last)/1000);this.last=now;
    if(!running){this.debt=0;return;}
    const total=this.debt+dt;this.debt=Math.min(.25,total);
    this.dropped+=Math.max(0,total-this.debt);
  }
  consume(dt){this.debt=Math.max(0,this.debt-dt);}
  reset(now=null){this.last=now;this.debt=0;}
}
