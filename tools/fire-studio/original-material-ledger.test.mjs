import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {interpretHancockGLSL,transportReference,inventory} from './original-compact-reference.mjs';
const source=await readFile(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/original-fine-flow.js',import.meta.url),'utf8'),context={window:{}};vm.runInNewContext(source,context);const Flow=context.window.OriginalFineFlow,kernel=interpretHancockGLSL(Flow.hancockGLSL),f=Math.fround;
function reduce4(input,width,height){
 while(width>1||height>1){const w=Math.ceil(width/4),h=Math.ceil(height/4),next=new Float32Array(w*h);for(let y=0;y<h;y++)for(let x=0;x<w;x++){let sum=0;for(let j=0;j<4;j++)for(let i=0;i<4;i++)if(x*4+i<width&&y*4+j<height)sum=f(sum+input[(y*4+j)*width+x*4+i]);next[y*w+x]=sum;}input=next;width=w;height=h;}return input[0];
}
function gpuInventory(input,n){
 const [nx,ny,nz]=n,width=Math.ceil(nx*8/4),height=Math.ceil(ny*Math.ceil(nz/8)/4),pixels=new Float32Array(width*height),volume=f(f(f(1/nx)*f(1/ny))*f(1/(nz-1)));
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){let sum=0;for(let j=0;j<4;j++)for(let i=0;i<4;i++){const px=x*4+i,py=y*4+j,z=Math.floor(px/nx)+8*Math.floor(py/ny);if(px>=nx*8||py>=ny*Math.ceil(nz/8)||z>=nz)continue;const q=input[(z*ny+py%ny)*nx+px%nx],weight=z===0||z===nz-1?.5:1;sum=f(sum+f(q*f(volume*weight)));}pixels[y*width+x]=sum;}return reduce4(pixels,width,height);
}
// Independent atlas traversal/reduction model; the full-volume update oracle
// separately accumulates boundary flux while updating every cell. The face
// kernel interprets production scalar GLSL, not a separately authored limiter.
function gpuBoundary(n,{axis,delta,flux}){
 const h=n.map((v,i)=>f(1/(i===2?v-1:v))),blocks=Math.ceil(Math.max(n[0],n[1])/4),width=blocks*2,height=Math.ceil(Math.max(n[1],n[2])/4),pixels=new Float32Array(width*height),visited=new Set();
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){const side=Math.floor(x/blocks),base=[x%blocks*4,y*4];let sum=0;for(let j=0;j<4;j++)for(let i=0;i<4;i++){
  const u=base[0]+i,v=base[1]+j,c=axis===0?[side? n[0]-1:0,u,v]:axis===1?[u,side?n[1]-1:0,v]:[u,v,side?n[2]-1:0];if(c.some((q,a)=>q<0||q>=n[a]))continue;
  const key=side+':'+c.join(',');assert(!visited.has(key));visited.add(key);let area=f(f(f(h[0]*h[1])*h[2])/h[axis]);if(axis!==2&&(c[2]===0||c[2]===n[2]-1))area=f(area*.5);const face=c.map((q,a)=>q+(side&&a===axis?1:0));sum=f(sum+f(flux(face)*f(f((side?1:-1)*delta)*area)));
 }pixels[y*width+x]=sum;}
 assert.equal(visited.size,2*n.filter((_,a)=>a!==axis).reduce((a,b)=>a*b,1));return reduce4(pixels,width,height);
}
test('CPU Float32 boundary atlas closes F/E/S inventories for signed open faces, half-depth and impermeable floor',t=>{
 const rows=[];for(const n of [[19,11,5],[7,9,3]])for(const axis of [0,1,2])for(const sign of [-1,1])for(const scale of [2.5,.4,5]){
  const size=n.reduce((a,b)=>a*b),v=[0,1,2].map(a=>new Float32Array(size).fill(a===axis?sign*.3:0)),q=Float32Array.from({length:size},(_,i)=>scale*(.1+Math.exp(-(((i%n[0]-n[0]*.7)/2)**2)))),before=gpuInventory(q,n);let boundary=0,sweeps=0;
  const out=transportReference(q,v,n,.4,Flow.schedule,{floor:2,kernel,onSweep:s=>{boundary=f(boundary+gpuBoundary(n,s));sweeps++;}}),after=gpuInventory(out.q,n),relativeClosure=(after+boundary-before)/before;
  assert(Math.abs(relativeClosure)<16*2**-23,JSON.stringify({n,axis,sign,scale,before,after,boundary,relativeClosure}));assert(out.minCell>=0&&out.minFace>=0);assert(Math.abs(boundary-out.boundaryLoss)/Math.max(inventory(q,n),1e-30)<16*2**-23);if(axis===1&&sign===-1)assert.equal(boundary,0);rows.push({n,axis,sign,scale,sweeps,relativeClosure,boundary});
 }t.diagnostic(JSON.stringify({cases:rows.length,maximumRelativeClosure:Math.max(...rows.map(r=>Math.abs(r.relativeClosure))),scope:'CPU generated-atlas Float32 reduction model against full-volume independent shared-face update. Native compile and actual boundary closure remain pending.'}));
});
test('closed random contracting flow has zero outward ledger and conserves weighted volumes without clipping',t=>{
 const n=[13,9,5],size=n.reduce((a,b)=>a*b),v=[0,1,2].map(a=>Float32Array.from({length:size},(_,i)=>{const c=[i%n[0],Math.floor(i/n[0])%n[1],Math.floor(i/n[0]/n[1])];return c[a]===0||c[a]===n[a]-1?0:.11*Math.sin(2*Math.PI*c[a]/(n[a]-1));}));let q=Float32Array.from({length:size},(_,i)=>i%5===0?2.5:0),before=gpuInventory(q,n),boundary=0;
 for(let k=0;k<12;k++){const out=transportReference(q,v,n,.1,Flow.schedule,{floor:1,kernel,onSweep:s=>{boundary=f(boundary+gpuBoundary(n,s));}});q=out.q;assert(out.minCell>=0);}
 const after=gpuInventory(q,n),relativeClosure=(after+boundary-before)/before;assert.equal(boundary,0);assert(Math.abs(relativeClosure)<16*2**-23);t.diagnostic(JSON.stringify({relativeClosure,boundary,maximum:Math.max(...q)}));
});
