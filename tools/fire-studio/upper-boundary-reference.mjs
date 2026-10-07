// Interpret the emitted production stencil, then compare it with an independent
// face-incidence matrix. These CPU checks do not certify native shader execution.
export function interpretUpperOperator(glsl){
 let code=glsl.replace(/precision[^;]+;/g,'').replace(/layout[^;]+;/g,'');
 code=code.replace(/const int/g,'const').replace(/const vec2 K=vec2\(([^,]+),([^\)]+)\)/,'const K={x:$1,y:$2}');
 code=code.replace(/int region\(ivec2 c\)/,'function region(c)');
 code=code.replace(/float value\(sampler2D tex,ivec2 c,int block\)\{/,'function value(tex,c,block){c={...c};');
 code=code.replace(/float diagonal\(ivec2 c\)/,'function diagonal(c)').replace(/float operatorA\(sampler2D tex,ivec2 c\)/,'function operatorA(tex,c)');
 code=code.replace(/c([+-])ivec2\((\d),(\d)\)/g,(_,sign,x,y)=>`offset(c,${sign==='-'?-1:1}*${x},${sign==='-'?-1:1}*${y})`);
 code=code.replace(/texelFetch\(tex,c,0\)\.r/g,'tex[c.y*(M+1)+c.x]').replace(/\b(?:int|float)\s+(?=[a-zA-Z_])/g,'let ').replace(/\bmax\(/g,'Math.max(');
 return new Function('offset','ivec2',code+';return {operatorA,diagonal,region};')((c,x,y)=>({x:c.x+x,y:c.y+y}),(x,y)=>({x,y}));
}
export function divergence(velocity,n,floor){
 const [nx,ny]=n,result=new Float64Array(nx*ny),slot=(a,x,y)=>a===1&&y===floor?0:velocity[a][y*nx+x];
 for(let y=floor;y<ny;y++)for(let x=0;x<nx;x++)result[y*nx+x]=nx*(slot(0,Math.min(x+1,nx-1),y)-slot(0,x,y))+ny*(slot(1,x,Math.min(y+1,ny-1))-slot(1,x,y));
 return result;
}
export function incidence(n,floor,extent){
 const [nx,ny]=n,cells=[],faces=[];
 for(let y=floor;y<ny;y++)for(let x=0;x<nx;x++)if(x!==nx-1||y!==ny-1)cells.push(y*nx+x);
 for(let a=0;a<2;a++)for(let y=floor+(a===1?1:0);y<ny;y++)for(let x=0;x<nx;x++)faces.push({a,index:y*nx+x});
 const D=cells.map(()=>new Float64Array(faces.length));
 faces.forEach((face,j)=>{const v=[new Float64Array(nx*ny),new Float64Array(nx*ny)];v[face.a][face.index]=1;const d=divergence(v,n,floor);cells.forEach((index,i)=>D[i][j]=d[index]);});
 const A=cells.map((_,i)=>Float64Array.from(cells,(_,j)=>faces.reduce((sum,face,k)=>sum+D[i][k]*D[j][k]/extent[face.a]**2,0)));
 return {cells,faces,D,A};
}
export function solve(matrix,rhs){
 const a=matrix.map((row,i)=>[...row,rhs[i]]),n=a.length;
 for(let i=0;i<n;i++){
  let pivot=i;for(let j=i+1;j<n;j++)if(Math.abs(a[j][i])>Math.abs(a[pivot][i]))pivot=j;
  [a[i],a[pivot]]=[a[pivot],a[i]];if(Math.abs(a[i][i])<1e-14)throw Error('Singular boundary block');
  const scale=a[i][i];for(let k=i;k<=n;k++)a[i][k]/=scale;
  for(let j=0;j<n;j++)if(j!==i){const gain=a[j][i];for(let k=i;k<=n;k++)a[j][k]-=gain*a[i][k];}
 }return Float64Array.from(a,row=>row[n]);
}
export function complete(velocity,n,floor,extent,source=new Float64Array(n[0]*n[1])){
 const system=incidence(n,floor,extent),d=divergence(velocity,n,floor),psi=solve(system.A,system.cells.map(i=>source[i]-d[i]));
 const out=velocity.map(a=>Float64Array.from(a)),delta=system.faces.map((face,k)=>system.cells.reduce((sum,_,i)=>sum+system.D[i][k]*psi[i]/extent[face.a]**2,0));
 system.faces.forEach((face,k)=>out[face.a][face.index]+=delta[k]);return {out,delta,psi,system};
}
