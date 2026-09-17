/** GPU-owned CSR pressure solve. Experimental building block, not a full FLIP backend.
 * encode() only records GPU work; no submit, mapping, readback or queue waits.
 * CPU uploads in setSystem() are for the reference harness. A future GPU matrix
 * builder must write problem/rows/edges directly before encode() on the same device.
 */
export const PRESSURE_WGSL=/* wgsl */`
struct Params { count:u32, groups:u32, tolerance:f32, unused:u32 }
struct Edge { column:u32, weight:f32 }
@group(0) @binding(0) var<storage,read> problem:array<vec4f>;
@group(0) @binding(1) var<storage,read_write> state:array<vec4f>;
@group(0) @binding(2) var<storage,read_write> applied:array<f32>;
@group(0) @binding(3) var<storage,read_write> partial:array<vec4f>;
@group(0) @binding(4) var<storage,read_write> scalar:array<vec4f>;
@group(0) @binding(5) var<storage,read> rows:array<u32>;
@group(0) @binding(6) var<storage,read> edges:array<Edge>;
@group(0) @binding(7) var<storage,read_write> indirect:array<u32>;
@group(0) @binding(8) var<uniform> params:Params;
var<workgroup> sums:array<vec4f,128>;
fn sumGroup(value:vec4f,lane:u32)->vec4f {
 sums[lane]=value;workgroupBarrier();
 for(var stride=64u;stride>0u;stride/=2u){
  if(lane<stride){sums[lane]+=sums[lane+stride];}workgroupBarrier();
 }
 return sums[0];
}
fn sumPartials(lane:u32)->vec4f {
 var value=vec4f(0);for(var i=lane;i<params.groups;i+=128u){value+=partial[i];}
 return sumGroup(value,lane);
}
fn finite(v:f32)->bool{return v==v && abs(v)<3.4e38;}
fn matrixAt(i:u32,component:u32)->f32 {
 var value=problem[i].x*state[i][component];
 for(var e=rows[i];e<rows[i+1u];e++){value-=edges[e].weight*state[edges[e].column][component];}
 return value;
}
@compute @workgroup_size(128)
fn initialize(@builtin(global_invocation_id) id:vec3u,@builtin(local_invocation_index) lane:u32,@builtin(workgroup_id) group:vec3u){
 var value=vec4f(0);let i=id.x;
 if(i<params.count){let b=problem[i].y;let z=b/problem[i].x;state[i]=vec4f(0,b,z,z);value=vec4f(b*z,b*b,0,0);}
 let total=sumGroup(value,lane);if(lane==0u){partial[group.x]=total;}
}
@compute @workgroup_size(128)
fn initializeScalars(@builtin(local_invocation_index) lane:u32){
 let total=sumPartials(lane);if(lane==0u){
  let running=select(0.0,1.0,total.y>0.0);
  scalar[0]=vec4f(total.x,total.y,total.y,running); // rho, r², b², active
  scalar[1]=vec4f(0); // alpha, beta, previous rho, iterations
  scalar[2]=vec4f(0); // explicit residual, passed, breakdown, reserved
  indirect[0]=select(0u,params.groups,running>0.0);indirect[1]=1u;indirect[2]=1u;
 }
}
@compute @workgroup_size(128)
fn applyDirection(@builtin(global_invocation_id) id:vec3u,@builtin(local_invocation_index) lane:u32,@builtin(workgroup_id) group:vec3u){
 var value=vec4f(0);let i=id.x;
 if(i<params.count){let ad=matrixAt(i,3u);applied[i]=ad;value.x=state[i].w*ad;}
 let total=sumGroup(value,lane);if(lane==0u){partial[group.x]=total;}
}
@compute @workgroup_size(128)
fn alpha(@builtin(local_invocation_index) lane:u32){
 let total=sumPartials(lane);if(lane==0u && scalar[0].w>0.0){
  if(total.x<=0.0 || !finite(total.x) || !finite(scalar[0].x)){
   scalar[0].w=0;scalar[2].z=1;indirect[0]=0u;
  }else{scalar[1].x=scalar[0].x/total.x;scalar[1].z=scalar[0].x;}
 }
}
@compute @workgroup_size(128)
fn update(@builtin(global_invocation_id) id:vec3u,@builtin(local_invocation_index) lane:u32,@builtin(workgroup_id) group:vec3u){
 var value=vec4f(0);let i=id.x;
 if(i<params.count){var s=state[i];s.x+=scalar[1].x*s.w;s.y-=scalar[1].x*applied[i];s.z=s.y/problem[i].x;state[i]=s;value=vec4f(s.y*s.z,s.y*s.y,0,0);}
 let total=sumGroup(value,lane);if(lane==0u){partial[group.x]=total;}
}
@compute @workgroup_size(128)
fn beta(@builtin(local_invocation_index) lane:u32){
 let total=sumPartials(lane);if(lane==0u && scalar[0].w>0.0){
  scalar[1].w+=1;scalar[1].y=total.x/max(scalar[1].z,1e-30);
  scalar[0].x=total.x;scalar[0].y=total.y;
  if(!finite(total.y) || !finite(total.x)){scalar[2].z=1;}
  if(total.y<=params.tolerance*params.tolerance*scalar[0].z || scalar[2].z>0.0){scalar[0].w=0;indirect[0]=0u;}
 }
}
@compute @workgroup_size(128)
fn direction(@builtin(global_invocation_id) id:vec3u){
 if(id.x<params.count){state[id.x].w=state[id.x].z+scalar[1].y*state[id.x].w;}
}
@compute @workgroup_size(128)
fn trueResidual(@builtin(global_invocation_id) id:vec3u,@builtin(local_invocation_index) lane:u32,@builtin(workgroup_id) group:vec3u){
 var value=vec4f(0);let i=id.x;
 if(i<params.count){let r=problem[i].y-matrixAt(i,0u);value.x=r*r;}
 let total=sumGroup(value,lane);if(lane==0u){partial[group.x]=total;}
}
@compute @workgroup_size(128)
fn finish(@builtin(local_invocation_index) lane:u32){
 let total=sumPartials(lane);if(lane==0u){
  scalar[2].x=sqrt(total.x/max(scalar[0].z,1e-30));
  scalar[2].y=select(0.0,1.0,finite(total.x) && scalar[2].x<=params.tolerance && scalar[2].z==0.0);
 }
}
`;

const BINDINGS={initialize:[0,1,3,8],initializeScalars:[3,4,7,8],applyDirection:[0,1,2,3,5,6,8],alpha:[3,4,7,8],update:[0,1,2,3,4,8],beta:[3,4,7,8],direction:[1,4,8],trueResidual:[0,1,3,5,6,8],finish:[3,4,8]};

export class WebGPUPressure {
 static async create(device,system,{tolerance=6e-5,maxIterations=240}={}){
  if(!Number.isFinite(tolerance)||tolerance<=0||!Number.isInteger(maxIterations)||maxIterations<1||maxIterations>4096)throw Error('Invalid pressure solve limits');
  const solver=new WebGPUPressure();solver.device=device;solver.maxIterations=maxIterations;
  solver.count=system.diagonal.length;solver.groups=Math.ceil(solver.count/128);solver.tolerance=tolerance;
  if(!solver.count)throw Error('Empty pressure system');
  const usage=GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_DST|GPUBufferUsage.COPY_SRC;
  solver.buffers=[solver.count*16,solver.count*16,solver.count*4,solver.groups*16,48,(solver.count+1)*4,Math.max(8,system.column.length*8),12,16].map((size,i)=>device.createBuffer({label:`pressure ${i}`,size,usage:i===8?GPUBufferUsage.UNIFORM|GPUBufferUsage.COPY_DST:usage|(i===7?GPUBufferUsage.INDIRECT:0)}));
  try{
   solver.setSystem(system);
   const params=new ArrayBuffer(16);new Uint32Array(params).set([solver.count,solver.groups]);new Float32Array(params)[2]=tolerance;
   device.queue.writeBuffer(solver.buffers[8],0,params);
   const module=device.createShaderModule({label:'GPU-owned PCG',code:PRESSURE_WGSL});
   const errors=(await module.getCompilationInfo()).messages.filter(m=>m.type==='error');
   if(errors.length)throw Error(errors.map(m=>`${m.lineNum}:${m.linePos} ${m.message}`).join('\n'));
   solver.pipelines={};solver.bindGroups={};
   for(const [entryPoint,bindings] of Object.entries(BINDINGS)){
    const pipeline=await device.createComputePipelineAsync({label:entryPoint,layout:'auto',compute:{module,entryPoint}});
    solver.pipelines[entryPoint]=pipeline;
    solver.bindGroups[entryPoint]=device.createBindGroup({layout:pipeline.getBindGroupLayout(0),entries:bindings.map(binding=>({binding,resource:{buffer:solver.buffers[binding]}}))});
   }
   return solver;
  }catch(error){solver.dispose();throw error;}
 }
 setSystem({diagonal,row,column,weight,rhs}){
  const n=this.count;
  if(diagonal.length!==n||rhs.length!==n||row.length!==n+1||row[n]!==column.length||weight.length!==column.length||column.length*8>this.buffers[6].size)throw Error('Invalid CSR dimensions');
  const problem=new Float32Array(n*4),edges=new ArrayBuffer(Math.max(8,column.length*8)),ei=new Uint32Array(edges),ef=new Float32Array(edges);
  for(let i=0;i<n;i++){
   if(!(diagonal[i]>0)||!Number.isFinite(diagonal[i])||!Number.isFinite(rhs[i])||row[i]>row[i+1])throw Error('Invalid pressure row');
   problem[i*4]=diagonal[i];problem[i*4+1]=rhs[i];
  }
  for(let i=0;i<column.length;i++){
   if(column[i]<0||column[i]>=n||!Number.isFinite(weight[i]))throw Error('Invalid pressure edge');
   ei[i*2]=column[i];ef[i*2+1]=weight[i];
  }
  this.device.queue.writeBuffer(this.buffers[0],0,problem);
  this.device.queue.writeBuffer(this.buffers[5],0,new Uint32Array(row));
  this.device.queue.writeBuffer(this.buffers[6],0,edges);
 }
 encode(encoder){
  // Each dispatch is a GPU memory-ordering boundary. No global workgroup barrier
  // or CPU convergence polling is needed. Indirect counts become zero on GPU.
  const pass=encoder.beginComputePass({label:'Pressure PCG / no host feedback'});
  const run=(name,groups=1,indirect=false)=>{
   pass.setPipeline(this.pipelines[name]);pass.setBindGroup(0,this.bindGroups[name]);
   if(indirect)pass.dispatchWorkgroupsIndirect(this.buffers[7],0);else pass.dispatchWorkgroups(groups);
  };
  run('initialize',this.groups);run('initializeScalars');
  for(let i=0;i<this.maxIterations;i++){
   run('applyDirection',0,true);run('alpha');run('update',0,true);run('beta');run('direction',0,true);
  }
  run('trueResidual',this.groups);run('finish');pass.end();
 }
 /** Explicit test/export operation, excluded from the simulation hot path. */
 async readDiagnostics(){
  const size=48+this.count*16,readback=this.device.createBuffer({size,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
  try{
   const encoder=this.device.createCommandEncoder();encoder.copyBufferToBuffer(this.buffers[4],0,readback,0,48);encoder.copyBufferToBuffer(this.buffers[1],0,readback,48,this.count*16);
   this.device.queue.submit([encoder.finish()]);await readback.mapAsync(GPUMapMode.READ);
   const data=new Float32Array(readback.getMappedRange()),solution=new Float32Array(this.count);
   for(let i=0;i<this.count;i++)solution[i]=data[12+i*4];
   return {solution,iterations:data[7],relativeResidual:data[8],converged:data[9]===1,breakdown:data[10]!==0};
  }finally{readback.destroy();}
 }
 dispose(){for(const buffer of this.buffers??[])buffer.destroy();}
}
