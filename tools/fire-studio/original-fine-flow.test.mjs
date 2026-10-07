import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const source=await readFile(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/original-fine-flow.js',import.meta.url),'utf8');
const context={window:{}};vm.runInNewContext(source,context);const Flow=context.window.OriginalFineFlow;
const near=(a,b,tol=1e-10)=>assert(Math.abs(a-b)<=tol*Math.max(1,Math.abs(a),Math.abs(b)),`${a} != ${b}`);
const dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0),sum=a=>a.reduce((s,x)=>s+x,0);
function grid(n,h,floor=0){
 const size=n.reduce((a,b)=>a*b),idx=c=>(c[2]*n[1]+c[1])*n[0]+c[0],valid=c=>c.every((v,i)=>v>=0&&v<n[i]),fluid=c=>c[0]>0&&c[0]<n[0]-1&&c[1]>=floor&&c[1]<n[1]-1&&c[2]>0&&c[2]<n[2]-1;
 const cells=[];for(let z=0;z<n[2];z++)for(let y=0;y<n[1];y++)for(let x=0;x<n[0];x++)cells.push([x,y,z]);
 const add=(c,a,d)=>c.map((v,i)=>v+(i===a?d:0));
 const p=(a,c)=>{c=c.slice();c[1]=Math.max(c[1],floor);return fluid(c)?a[idx(c)]:0;};
 const G=(a,c)=>h.map((v,i)=>(p(a,c)-p(a,add(c,i,-1)))/v);
 const L=a=>Float64Array.from(cells,c=>fluid(c)?h.reduce((s,v,i)=>s+(p(a,add(c,i,1))-2*p(a,c)+p(a,add(c,i,-1)))/v**2,0):0);
 return {n,h,floor,size,idx,valid,fluid,cells,add,p,G,L};
}
function cg(A,b,tolerance=1e-12){let x=new Float64Array(b.length),r=Float64Array.from(b),p=Float64Array.from(r),rr=dot(r,r),start=rr,k=0;
 for(;k<4000&&rr>Math.max(1e-28,start*tolerance*tolerance);k++){const ap=A(p),alpha=rr/dot(p,ap);for(let i=0;i<x.length;i++){x[i]+=alpha*p[i];r[i]-=alpha*ap[i];}const next=dot(r,r),beta=next/rr;for(let i=0;i<p.length;i++)p[i]=r[i]+beta*p[i];rr=next;}assert(k<4000,'CG failed');return {x,k,residual:Math.sqrt(rr/Math.max(start,1e-28))};}
function periodic(n,h){const size=n.reduce((a,b)=>a*b),idx=c=>(c[2]*n[1]+c[1])*n[0]+c[0],cells=[];for(let z=0;z<n[2];z++)for(let y=0;y<n[1];y++)for(let x=0;x<n[0];x++)cells.push([x,y,z]);const at=(a,c,axis,step)=>a[idx(c.map((x,i)=>i===axis?(x+step+n[i])%n[i]:x))];
 const D=u=>Float64Array.from(cells,c=>h.reduce((s,v,a)=>s+(at(u[a],c,a,1)-u[a][idx(c)])/v,0));
 const G=p=>h.map((v,a)=>Float64Array.from(cells,c=>(p[idx(c)]-at(p,c,a,-1))/v));
 const A=p=>Float64Array.from(D(G(p)),x=>-x);
 return {size,cells,idx,at,D,G,A};
}
test('anisotropic forward D/backward G equals the fine floor/open matrix, including upper normal slots',t=>{
 let count=0,error=0;for(const [n,h,floor]of [[[9,8,7],[.2,.3,.7],2],[[7,9,6],[.5,.17,1.2],0]]){const g=grid(n,h,floor),p=Float64Array.from(g.cells,c=>g.fluid(c)?Math.sin(c[0]*.7+c[1]*.3-c[2]*.4):0),l=g.L(p);for(const c of g.cells.filter(g.fluid)){const grad=g.G(p,c),dg=h.reduce((s,v,a)=>s+(g.G(p,g.add(c,a,1))[a]-grad[a])/v,0);near(dg,l[g.idx(c)]);error=Math.max(error,Math.abs(dg-l[g.idx(c)]));count++;if(c[1]===floor)near(grad[1],0);}}
 assert.match(source,/if\(c.y==FLOOR\)v.y=0\./);assert.match(source,/c.y==FLOOR\?W.y:0\./);t.diagnostic(JSON.stringify({cells:count,maxDGError:error}));
});
test('checkerboard has the required nonzero eigenvalue, not a central-difference nullspace',()=>{
 const h=[.2,.3,.7],g=periodic([8,6,4],h),p=Float64Array.from(g.cells,c=>(c[0]+c[1]+c[2])%2?-1:1),Ap=g.A(p),lambda=4*h.reduce((s,x)=>s+1/x**2,0);for(let i=0;i<p.length;i++)near(Ap[i],lambda*p[i]);
});
test('the actual 640/128 unresolved pulse is removed on the fine operator',t=>{
 const n=640,u=new Float64Array(n);u[325]=.04;const D=u=>Float64Array.from(u,(x,i)=>(u[(i+1)%n]-x)*n),G=p=>Float64Array.from(p,(x,i)=>(x-p[(i+n-1)%n])*n),A=p=>Float64Array.from(D(G(p)),x=>-x),d=D(u);
 near(d[324],25.6);near(d[325],-25.6);const sample=p=>{const q=p*n-.5,lo=Math.floor(q),a=q-lo;return u[lo]*(1-a)+u[lo+1]*a;};const coarse=Float64Array.from({length:128},(_,i)=>sample((i+.5)/128));assert(coarse.every(x=>x===0));
 const solved=cg(A,Float64Array.from(d,x=>-x)),grad=G(solved.x),corrected=Float64Array.from(u,(x,i)=>x-grad[i]),post=D(corrected);assert(Math.max(...post.map(Math.abs))<1e-7);t.diagnostic(JSON.stringify({coarsePulseSeen:sum(coarse),finePreL1:sum(d.map(Math.abs)),finePostL1:sum(post.map(Math.abs)),iterations:solved.k}));
});
test('closed expansion is incompatible and the production open matrix supplies matching integrated boundary flux',t=>{
 const g=grid([12,10,8],[.2,.3,.5],2),b=Float64Array.from(g.cells,c=>g.fluid(c)?-1:0),closed=periodic([8,8,8],[.2,.3,.5]);near(sum(closed.D(closed.G(new Float64Array(closed.size)))),0);assert(sum(new Float64Array(closed.size).fill(1))>0);
 const solved=cg(p=>Float64Array.from(g.L(p),x=>-x),Float64Array.from(b,x=>-x)),p=solved.x;let totalD=0,flux=0;for(const c of g.cells.filter(g.fluid)){const u=g.G(p,c).map(x=>-x);totalD+=g.h.reduce((s,h,a)=>s+(-g.G(p,g.add(c,a,1))[a]-u[a])/h,0);for(let a=0;a<3;a++){if(!g.fluid(g.add(c,a,1)))flux+=-g.G(p,g.add(c,a,1))[a]/g.h[a];if(!g.fluid(g.add(c,a,-1)))flux-=u[a]/g.h[a];}}near(totalD,flux,1e-9);near(totalD,-sum(b),1e-9);t.diagnostic(JSON.stringify({openDivergenceSum:totalD,integratedBoundaryFlux:flux,closedExpansionMean:1}));
});
test('periodic pressure projection is energy nonincreasing and idempotent, with no extra timestep',t=>{
 const g=periodic([12,10,8],[.2,.3,.5]),u=[0,1,2].map(a=>Float64Array.from(g.cells,c=>Math.sin(c[0]*.6+c[1]*.7-c[2]*.8+a)+.3*Math.cos(c[0]*c[1]*.2+a)));
 const project=u=>{const d=g.D(u),s=cg(g.A,Float64Array.from(d,x=>-x)),grad=g.G(s.x);return u.map((q,a)=>Float64Array.from(q,(x,i)=>x-grad[a][i]));};const p=project(u),pp=project(p),e=q=>q.reduce((s,a)=>s+dot(a,a),0);assert(e(p)<=e(u)+1e-9);let max=0;for(let a=0;a<3;a++)for(let i=0;i<g.size;i++)max=Math.max(max,Math.abs(p[a][i]-pp[a][i]));assert(max<1e-9);t.diagnostic(JSON.stringify({energyBefore:e(u),energyAfter:e(p),idempotenceMax:max}));
});
const slope=(l,c,r)=>{const a=2*(c-l),b=.5*(r-l),d=2*(r-c);return .25*(Math.sign(a)+Math.sign(b))*Math.abs(Math.sign(a)+Math.sign(d))*Math.min(Math.abs(a),Math.abs(b),Math.abs(d));};
function transport(q,v,n,h,dt,periodicBoundary){const idx=(x,y)=>y*n[0]+x,at=(a,x,y)=>periodicBoundary?a[idx((x+n[0])%n[0],(y+n[1])%n[1])]:(x<0||x>=n[0]||y<0||y>=n[1]?0:a[idx(x,y)]);
 const flux=(a,x,y,axis)=>{const u=v[axis][idx(x%n[0],y%n[1])],e=axis===0?[1,0]:[0,1],dx=u>=0?x-e[0]:x,dy=u>=0?y-e[1]:y,c=at(a,dx,dy);return u*(c+(u>=0?.5:-.5)*slope(at(a,dx-e[0],dy-e[1]),c,at(a,dx+e[0],dy+e[1])));};
 const rate=a=>Float64Array.from(a,(_,i)=>{const x=i%n[0],y=Math.floor(i/n[0]);return (flux(a,x+1,y,0)-flux(a,x,y,0))/h[0]+(flux(a,x,y+1,1)-flux(a,x,y,1))/h[1];});const r=rate(q),stage=Float64Array.from(q,(x,i)=>x-dt*r[i]),rr=rate(stage);return Float64Array.from(q,(x,i)=>.5*(x+stage[i]-dt*rr[i]));}
test('fractional-CFL periodic and contracting blob conserve F/S/E inventories without cell clipping',t=>{
 const n=[40,32],h=[1/40,1/32],size=n[0]*n[1],q=Float64Array.from({length:size},(_,i)=>Math.exp(-(((i%n[0]+.5)/n[0]-.5)**2+((Math.floor(i/n[0])+.5)/n[1]-.5)**2)/.008));let examples=[];
 for(const contracting of [false,true]){const v=[0,1].map(a=>Float64Array.from(q,(_,i)=>{const x=(i%n[0]+.5)/n[0],y=(Math.floor(i/n[0])+.5)/n[1];return contracting?(a===0?Math.sin(2*Math.PI*x):Math.sin(2*Math.PI*y))*.13:(a===0?.11:-.07);}));let rate=0;for(let y=0;y<n[1];y++)for(let x=0;x<n[0];x++){const i=y*n[0]+x;rate=Math.max(rate,(Math.max(v[0][y*n[0]+(x+1)%n[0]],0)+Math.max(-v[0][i],0))/h[0]+(Math.max(v[1][((y+1)%n[1])*n[0]+x],0)+Math.max(-v[1][i],0))/h[1]);}const dt=.4/rate;
 let inventory=[];for(const scale of [2.5,.7,4]){let a=Float64Array.from(q,x=>x*scale),before=sum(a);for(let i=0;i<80;i++)a=transport(a,v,n,h,dt,true);near(sum(a),before,2e-12);assert(Math.min(...a)>-1e-12);inventory.push({before,after:sum(a),min:Math.min(...a),max:Math.max(...a)});}if(contracting)assert(inventory[0].max>2.5,'Contraction must concentrate without clipping');examples.push({contracting,CFL:dt*rate,inventory});}
 t.diagnostic(JSON.stringify(examples));
});
test('production hierarchy retains default physical floor row 48 and supports blast/anisotropic grids',()=>{
 for(const [n,e,min]of [[[640,360,32],[14,7.875,1.8],[-7,-1.05,-.9]],[[384,384,64],[8,8,4],[-4,-1.05,-2]],[[896,504,32],[14,7.875,1.8],[-7,-1.05,-.9]]]){const levels=Flow.hierarchy(n,e,min);assert(levels.length>=6);for(const g of levels){near(g.h[0],e[0]/g.n[0]);near(g.h[2],e[2]/(g.n[2]-1));assert(g.floor>=0&&g.floor<g.n[1]-1);}if(n[0]===640)assert.equal(levels[0].floor,48);}
});
test('production multigrid transfers and fixed cycle limit reduce a manufactured anisotropic fine residual',t=>{
 const hierarchy=Array.from(Flow.hierarchy([40,24,12],[14,7.875,1.8],[-7,-1.05,-.9]),r=>grid(Array.from(r.n),Array.from(r.h),r.floor));
 const levels=hierarchy.map(g=>({g,p:new Float64Array(g.size),b:new Float64Array(g.size)}));
 const sample=(g,a,c,pressureGhost=true)=>{const lo=c.map(Math.floor),f=c.map((x,i)=>x-lo[i]);let s=0;for(let z=0;z<2;z++)for(let y=0;y<2;y++)for(let x=0;x<2;x++){const o=[x,y,z],k=lo.map((q,i)=>q+o[i]);const value=pressureGhost?g.p(a,k):a[g.idx(k.map((v,i)=>Math.max(0,Math.min(g.n[i]-1,v))))];s+=value*f.reduce((w,q,i)=>w*(o[i]?q:1-q),1);}return s;};
 const smooth=(l,count)=>{const {g}=l;for(let step=0;step<count;step++){const lap=g.L(l.p),next=new Float64Array(g.size);for(const c of g.cells.filter(g.fluid)){const i=g.idx(c),diag=2*g.h.reduce((s,h)=>s+1/h**2,0)-(c[1]===g.floor?1/g.h[1]**2:0);next[i]=l.p[i]+2/3*(lap[i]-l.b[i])/diag;}l.p=next;}};
 const mapped=(c,from,to)=>c.map((x,i)=>i===2?x/(from.n[i]-1)*(to.n[i]-1):(x+.5)/from.n[i]*to.n[i]-.5);
 const filtered=(g,res,child)=>{let result=res;for(let a=0;a<3;a++)if(child.n[a]<g.n[a]){const old=result;result=Float64Array.from(g.cells,c=>[-1,0,1].reduce((s,d)=>{const k=g.add(c,a,d);return s+(g.valid(k)?old[g.idx(k)]:0)*(d===0?.5:.25);},0));}return result;};
 const cycle=i=>{const l=levels[i],g=l.g;if(i===levels.length-1){smooth(l,48);return;}smooth(l,2);const lap=g.L(l.p),res=Float64Array.from(l.b,(x,j)=>x-lap[j]),child=levels[i+1],restricted=filtered(g,res,child.g);child.b=Float64Array.from(child.g.cells,c=>child.g.fluid(c)?sample(g,restricted,mapped(c,child.g,g),false):0);child.p.fill(0);cycle(i+1);for(const c of g.cells.filter(g.fluid))l.p[g.idx(c)]+=sample(child.g,child.p,mapped(c,g,child.g));smooth(l,2);};
 const fine=levels[0],g=fine.g,truth=Float64Array.from(g.cells,c=>g.fluid(c)?Math.sin(Math.PI*c[0]/(g.n[0]-1))*Math.cos(.5*Math.PI*(c[1]-g.floor)/(g.n[1]-g.floor-1))*Math.sin(Math.PI*c[2]/(g.n[2]-1))+.02*Math.sin(c[0]*2.4+c[1]*2.1):0);fine.b=g.L(truth);const pre=sum(fine.b.map(Math.abs));let ratios=[];for(let i=0;i<4;i++){cycle(0);const lap=g.L(fine.p);ratios.push(sum(fine.b.map((x,j)=>Math.abs(x-lap[j])))/pre);}assert(ratios.at(-1)<=.2,JSON.stringify(ratios));t.diagnostic(JSON.stringify({grid:g.n,cycles:4,residualRatios:ratios,scope:'CPU oracle of production semicoarsening, weighted Jacobi, filtered residual restriction and trilinear prolongation; native storage still requires GPU evidence'}));
});
test('production GLSL includes compatible impulse and two-state conservative Hancock fluxes',()=>{
 assert.match(source,/v.xyz=traced\(c\)-grad\/EXTENT/);assert.doesNotMatch(source,/grad\s*\*\s*(delta|uDelta)/);assert.match(source,/uDelta\/width\(c,axis\)/);assert.match(source,/hancock\(l.r,center.r/);assert.match(source,/vec4\(q.r,\(1\.\+q.r\)\*q.b,0,0\)/);assert.doesNotMatch(source,/clamp\(next|max\(next|exp\(-clamp/);
});
test('filtered floor-localized residual restriction reads masked zeros, without pressure Neumann ghosts',t=>{
 const rows=[];for(const [fine,coarse,extent]of [[96,48,8],[126,63,7.875]]){const floorFine=Math.round(1.05/extent*fine),floorCoarse=Math.round(1.05/extent*coarse),residual=Float64Array.from({length:fine},(_,y)=>y===floorFine?1:0),q=(floorCoarse+.5)/coarse*fine-.5,lo=Math.floor(q),a=q-lo,weights=[.25*(1-a),.5-.25*a,.25+.25*a,.25*a],value=weights.reduce((s,w,i)=>s+w*residual[lo+i-1],0);near(value,.375);const mirrored=weights.reduce((s,w,i)=>s+w*residual[Math.max(lo+i-1,floorFine)],0);near(mirrored,.875);rows.push({fine,coarse,floorFine,floorCoarse,coordinate:q,productionRestriction:value,rejectedPressureGhostOracle:mirrored});}t.diagnostic(JSON.stringify(rows));
});
test('convergence/CFL reduction has explicit highp sampler precision and exposes unmet projection tolerance',()=>{
 const reduction=source.slice(source.indexOf('this.reduceProgram='),source.indexOf('for(let i=0;i<this.levels.length;i++)'));assert.match(reduction,/precision highp sampler2D/);assert.match(source,/converged=finite\&\&accepted\(metrics\)\&\&accepted\(midpoint\)/);assert.match(source,/rhoTolerance:\.2,etaTolerance:\.1/);assert.match(source,/if\(!converged\)/);
});
