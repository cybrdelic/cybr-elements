/** GPU-resident marching tetrahedra. No particle/grid/surface readback.
 * Fixed-capacity instanced geometry emits degenerate triangles for empty cells;
 * there is no false claim of GPU triangle compaction or sparse WebGPU compute.
 * Pressure, velocity, particle updates and phi stay in their actual GL textures.
 */
(function(){'use strict';const T=THREE;
const VERTEX=`precision highp float;precision highp int;uniform sampler2D uResidentPhi,uResidentBlocks,uResidentMap;
uniform ivec2 uResidentMapSize,uResidentListSize;uniform ivec3 uResidentDims,uResidentGrid;
uniform int uResidentColumns,uResidentCount;uniform float uResidentH;
varying float vFoam;varying vec3 vWorld,vNormalW,vView;
const ivec3 C[8]=ivec3[8](ivec3(0,0,0),ivec3(1,0,0),ivec3(1,1,0),ivec3(0,1,0),ivec3(0,0,1),ivec3(1,0,1),ivec3(1,1,1),ivec3(0,1,1));
const ivec4 TETS[6]=ivec4[6](ivec4(0,5,1,6),ivec4(0,1,2,6),ivec4(0,2,3,6),ivec4(0,3,7,6),ivec4(0,7,4,6),ivec4(0,4,5,6));
ivec2 pixel(int id,ivec2 size){return ivec2(id%size.x,id/size.x);}
float field(ivec3 g){
 if(any(lessThan(g,ivec3(0)))||any(greaterThanEqual(g,uResidentGrid)))return 3.*uResidentH;
 ivec3 b=g/8;int id=b.x+uResidentDims.x*(b.y+uResidentDims.y*b.z);
 int brick=int(texelFetch(uResidentMap,pixel(id,uResidentMapSize),0).r+.5)-1;if(brick<0)return 3.*uResidentH;
 ivec3 q=g-b*8;ivec2 px=ivec2((brick%uResidentColumns)*64+q.x+8*q.y,(brick/uResidentColumns)*8+q.z);
 return texelFetch(uResidentPhi,px,0).g;
}
vec3 gradient(ivec3 p){return vec3(field(p+ivec3(1,0,0))-field(p-ivec3(1,0,0)),field(p+ivec3(0,1,0))-field(p-ivec3(0,1,0)),field(p+ivec3(0,0,1))-field(p-ivec3(0,0,1)));}
void main(){
 int cell=gl_InstanceID,brick=cell/512,q=cell%512,tetra=gl_VertexID/6,vertex=gl_VertexID%6;
 vFoam=0.;vWorld=vNormalW=vView=vec3(0.);gl_Position=vec4(2.,2.,2.,1.);
 if(brick>=uResidentCount)return;
 ivec3 origin=ivec3(texelFetch(uResidentBlocks,pixel(brick,uResidentListSize),0).xyz+.5)*8+ivec3(q%8,(q/8)%8,q/64);
 if(any(greaterThanEqual(origin,uResidentGrid-1)))return;
 ivec4 indices=TETS[tetra];ivec3 g[4];float d[4];vec3 p[4];int negative[4],positive[4],nn=0,np=0;
 for(int i=0;i<4;i++){g[i]=origin+C[indices[i]];d[i]=field(g[i]);p[i]=(vec3(g[i])+.5)*uResidentH;if(d[i]<0.)negative[nn++]=i;else positive[np++]=i;}
 if(nn==0||nn==4)return;
 if(nn!=2&&vertex>=3)return;
 // Orient every triangle toward the positive (air) side of the tetrahedral
 // linear field. This also makes the back-face thickness pass well-defined.
 int base=(vertex/3)*3,k=vertex%3,aa[3],bb[3];float fractions[3];vec3 triangle[3];
 const ivec2 pairs[6]=ivec2[6](ivec2(0,0),ivec2(0,1),ivec2(1,0),ivec2(1,0),ivec2(0,1),ivec2(1,1));
 for(int j=0;j<3;j++){int v=base+j,a,b;if(nn==1){a=negative[0];b=positive[v];}else if(nn==3){a=negative[v];b=positive[0];}else{a=negative[pairs[v].x];b=positive[pairs[v].y];}aa[j]=a;bb[j]=b;fractions[j]=clamp(d[a]/(d[a]-d[b]),0.,1.);triangle[j]=mix(p[a],p[b],fractions[j]);}
 vec3 outward=vec3(0.);for(int j=0;j<4;j++){if(j<np)outward+=p[positive[j]]/float(np);if(j<nn)outward-=p[negative[j]]/float(nn);}
 if(dot(cross(triangle[1]-triangle[0],triangle[2]-triangle[0]),outward)<0.&&k!=0)k=3-k;
 int a=aa[k],b=bb[k];float f=fractions[k];vec3 world=triangle[k],normal=mix(gradient(g[a]),gradient(g[b]),f);
 vNormalW=length(normal)>1.e-8?normalize(normal):vec3(0.,1.,0.);vWorld=world;vec4 view=viewMatrix*vec4(world,1.);vView=view.xyz;gl_Position=projectionMatrix*view;
}`;
class ResidentSurface{
 constructor(liquid,gpu){
  this.liquid=liquid;this.gpu=gpu;this.oldDepthMaterial=liquid.back.material;this.wrappers=new Map();this.frames=0;this.cpuMeshBuilds=0;
  this.geometry=new T.InstancedBufferGeometry();this.geometry.setAttribute('position',new T.BufferAttribute(new Float32Array(36*3),3));this.geometry.instanceCount=0;
  const u={uResidentPhi:{value:null},uResidentMap:{value:null},uResidentBlocks:{value:null},uResidentMapSize:{value:gpu.mapSize},uResidentListSize:{value:gpu.listSize},uResidentDims:{value:gpu.blockDims},uResidentGrid:{value:gpu.gridSize},uResidentColumns:{value:0},uResidentCount:{value:0},uResidentH:{value:gpu.h}};
  let frag=liquid.material.fragmentShader;if(!frag.includes('#define gl_FragColor'))frag='out vec4 residentColor;\n#define gl_FragColor residentColor\n'+frag;
  this.waterMaterial=new T.ShaderMaterial({glslVersion:T.GLSL3,vertexShader:VERTEX,fragmentShader:frag,uniforms:{...liquid.material.uniforms,...u},side:T.DoubleSide});
  this.depthMaterial=new T.ShaderMaterial({glslVersion:T.GLSL3,vertexShader:VERTEX,fragmentShader:'precision highp float;varying vec3 vView,vNormalW;out vec4 depthColor;void main(){depthColor=vec4(-vView.z,normalize(vNormalW)*.5+.5);}',uniforms:u,side:T.BackSide});
  this.normalMaterial=new T.ShaderMaterial({glslVersion:T.GLSL3,vertexShader:VERTEX,fragmentShader:'precision highp float;varying vec3 vNormalW;out vec4 normalColor;void main(){normalColor=vec4(normalize(vNormalW)*.5+.5,1.);}',uniforms:u,side:T.DoubleSide});
  this.uniforms=u;liquid.opticsMode='raster';liquid.white.visible=false;liquid.bubbles.visible=false;liquid.particlePoints.visible=false;
 }
 wrap(raw){let t=this.wrappers.get(raw.texture);if(!t){t=new T.DataTexture(null,raw.width,raw.height,T.RGBAFormat,T.FloatType);t.version=0;t.minFilter=t.magFilter=T.NearestFilter;const properties=this.liquid.renderer.properties.get(t);properties.__webglTexture=raw.texture;properties.__version=0;this.wrappers.set(raw.texture,t);}return t;}
 update(){const g=this.gpu,l=this.liquid;g.beginCompute();try{g.levelSet();}finally{g.endCompute();}
  this.uniforms.uResidentPhi.value=this.wrap(g.field.textures[0]);this.uniforms.uResidentMap.value=this.wrap(g.mapTexture);this.uniforms.uResidentBlocks.value=this.wrap(g.blockTexture);
  this.uniforms.uResidentColumns.value=g.atlasColumns;this.uniforms.uResidentCount.value=g.blockCount;this.geometry.instanceCount=g.blockCount*512;
  l.water.geometry=l.back.geometry=this.geometry;l.geometry=this.geometry;l.water.material=l.mode==='normal'?this.normalMaterial:this.waterMaterial;l.back.material=this.depthMaterial;
  l.setMetrics({...g.lastMetrics,...g.lastTelemetry});this.frames++;
  return {surfaceBackend:'GPU marching tetrahedra / fixed capacity',cpuMeshBuilds:0,primaryReadbackBytes:g.primaryReadbackBytes,telemetryReadbackBytes:g.telemetryReadbackBytes,potentialTriangles:this.geometry.instanceCount*12,renderedFrames:this.frames};
 }
 dispose(){this.liquid.back.material=this.oldDepthMaterial;this.liquid.water.material=this.liquid.material;for(const t of this.wrappers.values())this.liquid.renderer.properties.remove(t);this.wrappers.clear();this.geometry.dispose();this.waterMaterial.dispose();this.depthMaterial.dispose();this.normalMaterial.dispose();}
}
window.ResidentSurface=ResidentSurface;
})();
