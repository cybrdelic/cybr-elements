import {solverParamsWGSL} from './solver-params.js?v=studio-rc-37-audit';
import {powerSourceFor} from '../fire-powers.js?v=studio-rc-37-audit';
import {objectWGSL} from './objects.js?v=studio-rc-37-audit';
import {pruneShaderFunctions} from '../shader-specialization.js?v=studio-rc-37-audit';

export function powerContactShader(kind=null){
 // Collision assembly owns dependencies used by its entry point. Preserve
 // them during source specialization, then prune the complete shader once.
 let source=powerSourceFor(kind,'wgsl',['abilityFloorContact']);
 source=source.replace('fn powerRecording()->bool{return false;}','fn powerRecording()->bool{return true;}');
 source=source.replace('fn powerRecordProjectile(index:f32,a:vec3f,b:vec3f,duration:f32,arc:f32,radius:f32,t:f32)->bool{return false;}',`
fn powerRecordProjectile(index:f32,a:vec3f,b:vec3f,duration:f32,arc:f32,radius:f32,t:f32)->bool{
 if(u32(index)==flightIndex){recordA=a;recordB=b;recordShape=vec3f(duration,arc,radius);recordLaunch=recordAge-t;recorded=true;}return true;
}`);
 return pruneShaderFunctions(`
${solverParamsWGSL}
@group(0) @binding(0) var<uniform> p:Params;@group(0) @binding(1) var smp:sampler;
${objectWGSL}
@group(0) @binding(63) var<storage,read_write> contacts:array<ContactHit>;
var<private> flightIndex:u32;var<private> recordA:vec3f;var<private> recordB:vec3f;var<private> recordShape:vec3f;var<private> recorded:bool;var<private> recordLaunch:f32;var<private> recordAge:f32;
fn powerTimeStep()->f32{return p.step.x;}
${source}
fn worldPoint(origin:vec3f,scale:f32,u:f32)->vec3f{
 return origin+scale*(mix(recordA,recordB,u)+vec3f(0,4.*recordShape.y*u*(1.-u),0));
}
fn distanceToScene(x:vec3f)->f32{return min(x.y,objectDistance(x));}
fn contactNormal(x:vec3f)->vec3f{if(x.y<=objectDistance(x)){return vec3f(0,1,0);}return objectNormal(x);}
@compute @workgroup_size(32) fn main(@builtin(local_invocation_index) index:u32){
 if(index>=24u){return;}flightIndex=index%6u;let actor=p.casts[index/6u];contacts[index]=ContactHit(vec4f(-1,0,1,0),vec4f(0),vec4f(0));
 if(actor.kindScale.z<.5){return;}let kind=actor.kindScale.x;let scale=max(actor.kindScale.y,.05);let origin=actor.originAge.xyz;
 // Evaluate the production choreography in recording mode. Source functions
 // record trajectory inputs; no second list of launch paths is maintained.
 var age=actor.originAge.w+.001;
 if(kind>1.5&&kind<2.5){age=.221;}
 if(kind>8.5&&kind<9.5){age=1.551;}
 if(kind>10.5&&kind<11.5){age=1.251;}
 if(kind>12.5&&kind<13.5){age=.501;}
 if(kind>15.5&&kind<16.5){age=.251;}
 if(kind>16.5&&kind<17.5){age=.301;}
 if(kind>17.5&&kind<18.5){age=.281;}
 if(kind>21.5&&kind<22.5){age=.321;}
 recordAge=age;let ignored=powerCastSource(kind,origin,origin,scale,age,p.step.y,actor.directionStrength.xyz,actor.directionStrength.w,actor.targetCharge.xyz,actor.targetCharge.w);
 if(!recorded){return;}
 let floor=abilityFloorContact(recordA,recordB,recordShape.y,recordShape.z,-origin.y/scale);
 var fraction=floor;var normal=vec3f(0,1,0);
 if(object.options.x>.5){
  let radius=recordShape.z*scale*.8;let speedBound=scale*(length(recordB-recordA)+4.*abs(recordShape.y));
  var u=0.;var previous=0.;
  for(var sample=0u;sample<2048u;sample++){
   if(u>min(1.,fraction)){break;}let point=worldPoint(origin,scale,u);let distance=distanceToScene(point)-radius;
   let velocity=recordB-recordA+vec3f(0,4.*recordShape.y*(1.-2.*u),0);
   let n=contactNormal(point);
   if(distance<=.0005&&dot(velocity,n)<0.){
    var lo=previous;var hi=u;
    for(var refine=0u;refine<10u;refine++){let mid=(lo+hi)*.5;
     if(distanceToScene(worldPoint(origin,scale,mid))>radius){lo=mid;}else{hi=mid;}}
    fraction=hi;normal=contactNormal(worldPoint(origin,scale,hi));break;
   }
   previous=u;
   // Moving voxelized wood is not a globally smooth signed-distance field.
   // Bound the geometric march by half a collision voxel as well as distance.
   u+=clamp(.8*max(distance,.001)/max(speedBound,.001),.00001,(3./128.)/max(speedBound,.001));
  }
 }
 let surface=worldPoint(origin,scale,min(fraction,1.))-normal*recordShape.z*scale*.8;
 contacts[index]=ContactHit(vec4f(fraction,normal),vec4f(recordLaunch,recordShape.x,recordShape.z,1),vec4f(surface,1));
}`);
}

export class PowerContacts {
 constructor(solver){this.solver=solver;this.cache=new Map();this.output=solver.device.createBuffer({label:'resolved-power-contacts',size:1152,usage:GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_SRC});}
 async select(kind){if(!this.cache.has(kind))this.cache.set(kind,await this.solver.pipeline(powerContactShader(kind),'resolve-power-contacts-'+kind));this.pipeline=this.cache.get(kind);}
 encode(encoder,params){const s=this.solver;const pass=encoder.beginComputePass();pass.setPipeline(this.pipeline);
  pass.setBindGroup(0,s.group(this.pipeline,[[0,{buffer:params}],[1,s.sampler],...s.objectBindings(),[63,{buffer:this.output}]]));pass.dispatchWorkgroups(1);pass.end();
  encoder.copyBufferToBuffer(this.output,0,params,384,1152);
 }
 destroy(){this.output.destroy();this.cache.clear();}
}
