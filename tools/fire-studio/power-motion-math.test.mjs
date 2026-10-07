import test from 'node:test';
import assert from 'node:assert/strict';
import {powerSourceWGSL as abilityMotionWGSL} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/fire-powers.js';
import {sourceMixingWGSL} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/reduced-chemistry.js';
function body(source,name){const start=source.indexOf('fn '+name+'(');assert.ok(start>=0);const a=source.indexOf('{',start)+1;let b=a,depth=1;while(depth){if(source[b]==='{')depth++;if(source[b]==='}')depth--;b++;}return source.slice(a,b-1).replace(/let (\w+):f32=/g,'const $1=').replace(/\b(abs|sign|exp|max|min|sin|cos)\(/g,'Math.$1(');}
const erf=new Function('x',body(abilityMotionWGSL,'abilityErf'));
const sweep=new Function('d','travel','length','dot','abilityErf',body(abilityMotionWGSL,'abilitySweptGaussian'));
const norm=v=>Math.hypot(...v),dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
const average=(d,v)=>sweep(d,v,norm,dot,erf);
test('swept release agrees with independent time integration for short and long source travel',()=>{
 for(const speed of [0,.1,.5,2,5,12])for(const d of [[0,0,0],[.3,.7,-.2],[2.5,.1,.4],[-3,1,.5]]){
  const v=[speed,.2*speed,-.1*speed];let reference=0;const count=20000;
  for(let i=0;i<count;i++){const t=(i+.5)/count-.5,q=d.map((x,k)=>x+t*v[k]);reference+=Math.exp(-1.2*dot(q,q))/count;}
  assert.ok(Math.abs(average(d,v)-reference)<.0015,JSON.stringify({speed,d,actual:average(d,v),reference}));
 }
});
test('swept release preserves integrated Gaussian mass as travel increases',()=>{
 const step=.01;let expected=0;for(let x=-14;x<=14;x+=step)expected+=Math.exp(-1.2*x*x)*step;
 for(const speed of [.5,3,12]){let mass=0;for(let x=-14;x<=14;x+=step)mass+=average([x,0,0],[speed,0,0])*step;assert.ok(Math.abs(mass-expected)<1e-5);}
});
test('held casts cannot advance into release and both engines use one deterministic source clock',()=>{
 const age=new Function('age','state','dt',body(sourceMixingWGSL,'sourceSampleAge'));
 const clock=new Function('clock','seed','dt',body(sourceMixingWGSL,'sourceClock'));
 assert.equal(age(.2199,2,1/30),.2199);assert.equal(age(.2199,1,1/30),.2199+1/60);
 assert.equal(clock(3, .4, 1/30),3+1/60+.4*11.37);
});

test('orbit release velocity matches the differentiated rotating and shrinking source path',()=>{
 const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));const smoothstep=(a,b,x)=>{const u=clamp((x-a)/(b-a),0,1);return u*u*(3-2*u);};
 const omega=new Function(body(abilityMotionWGSL,'abilityOrbitAngularSpeed'));
 const angle=new Function('index','t','abilityOrbitAngularSpeed',body(abilityMotionWGSL,'abilityOrbitAngle'));
 const radius=new Function('t','smoothstep',body(abilityMotionWGSL,'abilityOrbitRadius'));
 const dr=new Function('t','clamp',body(abilityMotionWGSL,'abilityOrbitRadialSpeed'));
 const center=(index,t)=>{const a=angle(index,t,omega),r=radius(t,smoothstep);return [r*Math.cos(a),.7+.1*Math.sin(2*a+index),r*Math.sin(a)];};
 for(const index of [0,1,2])for(const t of [.1,.64,.8,1.1,1.19]){
  const a=angle(index,t,omega),r=radius(t,smoothstep),radial=dr(t,clamp),w=omega();
  const velocity=[Math.cos(a)*radial-Math.sin(a)*w*r,2*w*.1*Math.cos(2*a+index),Math.sin(a)*radial+Math.cos(a)*w*r];
  const h=1e-5,left=center(index,t-h),right=center(index,t+h);
  for(let k=0;k<3;k++)assert.ok(Math.abs(velocity[k]-(right[k]-left[k])/(2*h))<1e-6);
 }
 assert.ok(abilityMotionWGSL.includes('abilityMovingPacket(q,a,abilityOrbitVelocity('));
});
