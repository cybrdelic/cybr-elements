// CPU reference for the native WGSL geometry fixture; not shipped with the
// application. Keep the contour rule (bilinear R >= .5) explicit here.
export function supportTexture(bytes,width,height){return {width,height,read(x,y){return bytes[(Math.max(0,Math.min(height-1,y))*width+Math.max(0,Math.min(width-1,x)))*4]/255;}};}
export const guideUV=q=>[(q[0]*4+7)/14,(q[1]*4+2.95)/7.875];
export function bilinear(c,f){return (c[0]+(c[1]-c[0])*f[0])*(1-f[1])+(c[2]+(c[3]-c[2])*f[0])*f[1];}
export function crossing(c,f,d){
 if(bilinear(c,f)>=.5)return 0;
 const k=c[3]-c[1]-c[2]+c[0],a=k*d[0]*d[1],b=(c[1]-c[0])*d[0]+(c[2]-c[0])*d[1]+k*(f[0]*d[1]+f[1]*d[0]);
 const peak=a<0?Math.max(0,Math.min(1,-b/(2*a))):1;
 if(bilinear(c,f.map((x,i)=>x+d[i]*peak))<.5)return 2;
 let low=0,high=peak;for(let i=0;i<12;i++){const mid=(low+high)/2;if(bilinear(c,f.map((x,i)=>x+d[i]*mid))>=.5)high=mid;else low=mid;}
 return high;
}
export function traceGuide(texture,eye,ray,limit=100,{source=[0,1,0],scale=1.8,kind=10}={}){
 const miss={distance:limit,normal:[0,0,0],cells:0};if(Math.abs(kind-10)>.5||scale<=0)return miss;
 const low=[-1.6,-2.95/4,-.018].map((x,i)=>Math.max([-3,0,-3][i],source[i]+x*scale));
 const high=[1.6,(7.875-2.95)/4,.018].map((x,i)=>Math.min([3,6,3][i],source[i]+x*scale));
 const a=low.map((x,i)=>(x-eye[i])/(Math.abs(ray[i])>.000001?ray[i]:.000001));
 const b=high.map((x,i)=>(x-eye[i])/(Math.abs(ray[i])>.000001?ray[i]:.000001));
 const near=a.map((x,i)=>Math.min(x,b[i])),far=a.map((x,i)=>Math.max(x,b[i]));
 const start=Math.max(0,...near),end=Math.min(limit,...far);if(end<=start)return miss;
 let axis=2;if(near[0]>=near[1]&&near[0]>=near[2])axis=0;else if(near[1]>=near[2])axis=1;
 const cap=[0,0,0];cap[axis]=-Math.sign(ray[axis]);
 const size=[texture.width,texture.height];
 const pixel=x=>guideUV(x.map((v,i)=>(v-source[i])/scale)).map((v,i)=>v*size[i]-.5);
 const corners=cell=>[texture.read(...cell),texture.read(cell[0]+1,cell[1]),texture.read(cell[0],cell[1]+1),texture.read(cell[0]+1,cell[1]+1)];
 const origin=pixel(eye),p=pixel(eye.map((x,i)=>x+ray[i]*start)),cell=p.map(Math.floor);
 if(bilinear(corners(cell),p.map((x,i)=>x-cell[i]))>=.5)return {distance:start,normal:cap,cells:0};
 const direction=ray.slice(0,2).map((x,i)=>x/scale*[4/14,4/7.875][i]*size[i]);
 for(let i=0;i<2;i++)if(p[i]===Math.floor(p[i])&&direction[i]<0)cell[i]--;
 let t=start;
 for(let i=0;i<texture.width+texture.height+4;i++){
  const edges=cell.map((x,i)=>x+(direction[i]>0?1:0));
  const crossings=edges.map((x,i)=>Math.abs(direction[i])>.000001?(x-origin[i])/direction[i]:1e20);
  const next=Math.min(end,...crossings);
  if(next>t){
   const c=corners(cell),f=origin.map((x,i)=>x+direction[i]*t-cell[i]),delta=direction.map(x=>x*(next-t)),hit=crossing(c,f,delta);
   if(hit<=1){const at=f.map((x,i)=>x+delta[i]*hit),k=c[3]-c[1]-c[2]+c[0];
    const g=[c[1]-c[0]+k*at[1],c[2]-c[0]+k*at[0]].map((x,i)=>-x*size[i]*[4/14,4/7.875][i]);
    const length=Math.max(Math.hypot(...g),.000001);
    return {distance:t+(next-t)*hit,normal:[g[0]/length,g[1]/length,0],cells:i+1};}
  }
  if(next>=end)break;
  if(crossings[0]<=crossings[1])cell[0]+=direction[0]>0?1:-1;
  if(crossings[1]<=crossings[0])cell[1]+=direction[1]>0?1:-1;
  t=Math.max(t,next);
 }
 return miss;
}
