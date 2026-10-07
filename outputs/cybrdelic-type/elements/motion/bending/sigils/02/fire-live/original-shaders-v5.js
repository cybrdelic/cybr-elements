import {gasThermoGLSL,GAS_THERMO,PLUME_THERMAL} from './gas-thermodynamics.js?v=studio-rc-37-repair';
import {firePresentationGLSL} from './fire-presentation.js?v=studio-rc-37-repair';
// Pure shader assembly. Source motion supplies gas; every source uses the
// same combustion and optical paths. This module owns no GPU or DOM state.
import {GAS_DIFFUSIVITY,PRODUCT_DIFFUSIVITY} from './gas-transport.js?v=studio-rc-37-repair';
import {groundInjectionGLSL,groundSurfaceGLSL} from './ground-fuel-gl.js?v=studio-rc-37-repair';
import {woodSamplingGLSL} from './wood-state-gl.js?v=studio-rc-37-repair';
import {woodMechanicsGLSL} from './wood-structure-gl.js?v=studio-rc-37-repair';
import {SMOKE_CLEAR_DENSITY} from './smoke-lifecycle.js?v=studio-rc-37-repair';
import {WOOD_THERMO} from './wood-thermo.js?v=studio-rc-37-repair';
import {GAS_CHEMISTRY,sourceMixingGLSL} from './reduced-chemistry.js?v=studio-rc-37-repair';
import {powerSourceFor} from './fire-powers.js?v=studio-rc-37-repair';
import {POWER_CAST_CAPACITY} from './fire-power-definitions.js?v=studio-rc-37-repair';

// The cursor inlet and fireball use world-space source momentum. Their ambient
// curl and planar swirl must use the same units before entering normalized vf.
// Retain the authored motion of every other Original source.
export const originalAmbientScaleGLSL = `
float originalAmbientScale(int emitter,int effect,float sourceMode,float extent){
 bool worldMotion=sourceMode<.5&&((emitter==0&&effect<0)||emitter==23);
 return worldMotion?1./extent:1.;
}
`;


// Limit added force peaks in world acceleration units, retaining weak eddies.
// These authored scene limits apply only to Original cursor fire/fireball.
// No transported velocity, source momentum, timestep or render value is clamped.
export const ORIGINAL_MOTION_PEAK_ACCELERATION = Object.freeze({free:6,fireball:4});
export const originalPeakForceGLSL = `
bool originalPeakForceTarget(int emitter,int effect,float sourceMode){
 return sourceMode<.5&&((emitter==0&&effect<0)||emitter==23);
}
float originalPeakForceMaximum(int emitter){
 return emitter==23?${ORIGINAL_MOTION_PEAK_ACCELERATION.fireball.toFixed(1)}:${ORIGINAL_MOTION_PEAK_ACCELERATION.free.toFixed(1)};
}
float originalPeakForceScale(float worldMagnitude,float maximum){
 return min(1.,max(maximum,0.)/max(worldMagnitude,.00001));
}
`;

export function createOriginalShaders({domain,hasPowers,hasWood,initialPowerKind,MAX_POWER_EMITTER,renderSize,emittersGLSL,propsGLSL,woodMaterialGLSL}){
 const NX=domain.nx,NZ=domain.ny,DEPTH=domain.depth,TILES_X=8,TILES_Y=DEPTH/8,AW=NX*TILES_X,AH=NZ*TILES_Y;
 const [RW,RH]=renderSize;
  const vertex = `#version 300 es
  precision highp float;
  precision highp int;
  out vec2 uv;
  void main(){
    vec2 p=vec2((gl_VertexID<<1)&2, gl_VertexID&2);
    uv=p;
    gl_Position=vec4(p*2.0-1.0,0.0,1.0);
  }`;
  const shared = `
  #define FIRE_HAS_POWERS ${hasPowers ? 1 : 0}
  #define FIRE_OBJECT_SOURCE ${domain.object ? 1 : 0}
  precision highp float;
  precision highp int;
  precision highp sampler2D;
  in vec2 uv;
  uniform sampler2D vfTex;
  uniform sampler2D chemTex;
  uniform sampler2D noiseTex;
  uniform highp sampler3D turbulenceTex;
  ${hasWood ? woodMechanicsGLSL : woodMechanicsGLSL.replace('uniform float woodMechanicsEnabled,woodRestScale;', 'const float woodMechanicsEnabled=0.;uniform float woodRestScale;')}
  ${hasWood ? woodSamplingGLSL : woodSamplingGLSL.replace('uniform float woodEnabled,woodSigma,woodBark;', 'const float woodEnabled=0.;uniform float woodSigma,woodBark;')}
  vec4 woodStockRest(vec3 p){vec3 at=woodRestOrigin+p*woodRestScale;return woodCapacityAt(at).r>0.?woodStockAt(at):vec4(0);}
  vec4 woodWearRest(vec3 p){vec3 at=woodRestOrigin+p*woodRestScale;return woodCapacityAt(at).r>0.?woodWearAt(at):vec4(0);}
  vec3 curlNoise(vec3 q,float scale){
    vec3 p=q/(scale*64.);float h=1./64.;
    vec3 dx=texture(turbulenceTex,p+vec3(h,0,0)).rgb-texture(turbulenceTex,p-vec3(h,0,0)).rgb;
    vec3 dy=texture(turbulenceTex,p+vec3(0,h,0)).rgb-texture(turbulenceTex,p-vec3(0,h,0)).rgb;
    vec3 dz=texture(turbulenceTex,p+vec3(0,0,h)).rgb-texture(turbulenceTex,p-vec3(0,0,h)).rgb;
    return vec3(dy.z-dz.y,dz.x-dx.z,dx.y-dy.x)/(2.*scale);
  }
  uniform float clock;
  const vec3 simExtent=${domain.extentGLSL};
  const vec3 simMin=${domain.minimumGLSL};
  const float NXf=${NX}.0, NZf=${NZ}.0;
  const float DEPTHf=${DEPTH}.0;
  const vec2 atlasSize=vec2(${AW}.0,${AH}.0);
  vec2 atlasUV(vec2 p,float layer){
    p=clamp(p,vec2(.5/NXf,.5/NZf),vec2(1.0-.5/NXf,1.0-.5/NZf));
    float tx=mod(layer,${TILES_X}.0), ty=floor(layer/${TILES_X}.0);
    return (vec2(tx*NXf,ty*NZf)+p*vec2(NXf,NZf))/atlasSize;
  }
  vec4 field(sampler2D tex,vec3 p){
    p=clamp(p,vec3(0.0),vec3(1.0));
    float z=p.z*(DEPTHf-1.0), lo=floor(z), hi=min(DEPTHf-1.0,lo+1.0);
    return mix(texture(tex,atlasUV(p.xy,lo)),texture(tex,atlasUV(p.xy,hi)),fract(z));
  }
  vec4 layer(sampler2D tex,vec2 p,float z){ return texture(tex,atlasUV(p,z)); }
  float hash(vec2 p){ return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
  `;
  const simulation = (kind=initialPowerKind,{pressureGLSL,vorticityGLSL,advectionGLSL}) => `#version 300 es
  ${shared}
  ${pressureGLSL}
  ${vorticityGLSL}
  uniform sampler2D sourceTex;
  uniform sampler2D widthTex;
  uniform float delta;uniform float smokeDecayDt;
  uniform vec2 pointer;
  uniform vec2 pointerMotion;
  uniform float pointerStrength;
  uniform vec2 brushFrom;
  uniform vec2 brushTo;
  uniform float brushActive;
  uniform float sourceEnabled;
  uniform float smokeOnly;
  uniform float presetBuoyancy;
  uniform float sourceHeat;
  uniform float powerConfinement;
  uniform float powerTurbulence;
  ${sourceMixingGLSL}
  ${gasThermoGLSL}
  float richSootYield(float fuel,float oxygen){return mix(.35,1.,smoothstep(.3,1.2,.7*max(fuel,0.)/max(oxygen,.02)));}
  float powerTimeStep(){return delta;}
  ${hasPowers ? powerSourceFor(kind,'glsl') : ''}
  ${emittersGLSL}
  ${originalAmbientScaleGLSL}
  ${originalPeakForceGLSL}
  ${advectionGLSL}
  ${groundInjectionGLSL}
  layout(location=0) out vec4 outVF;
  layout(location=1) out vec4 outChem;
  void main(){
    ivec2 ip=ivec2(gl_FragCoord.xy);
    float slice=float(ip.x/${NX}+${TILES_X}*(ip.y/${NZ}));
    vec2 p=(vec2(ip.x%${NX},ip.y%${NZ})+.5)/vec2(NXf,NZf);
    float depth=slice/(DEPTHf-1.0);
    vec3 at=vec3(p,depth);
    vec4 oldVF=texelFetch(vfTex,ip,0);
    oldVF.xyz+=samplePressureCorrection(at);
    vec3 mid=at-.5*oldVF.xyz*delta;
    vec3 midVelocity=field(vfTex,mid).xyz+samplePressureCorrection(mid);
    vec3 back=at-midVelocity*delta;
    vec4 vf=field(vfTex,back);
    vf.xyz+=samplePressureCorrection(back);
    vec4 scalars=maccormackScalars(at,back,oldVF.xyz,sourceEnabled<.5&&emitterKind>0);
    // Match concentration change to the divergence of the projected flow.
    // Original velocities are normalized domain units, so derivatives use
    // normalized voxel spacing (the extents cancel in divergence).
    if(sourceEnabled<.5 && (emitterKind==6||emitterKind>=22) && scalars.r+scalars.a>.00001){
    vec3 dh=vec3(1./NXf,1./NZf,1./(DEPTHf-1.));
    vec3 vp=field(vfTex,at+vec3(dh.x,0,0)).xyz+samplePressureCorrection(at+vec3(dh.x,0,0));
    vec3 vq=field(vfTex,at+vec3(0,dh.y,0)).xyz+samplePressureCorrection(at+vec3(0,dh.y,0));
    vec3 vr=field(vfTex,at+vec3(0,0,dh.z)).xyz+samplePressureCorrection(at+vec3(0,0,dh.z));
    float flowDivergence=(vp.x-oldVF.x)/dh.x+(vq.y-oldVF.y)/dh.y+(vr.z-oldVF.z)/dh.z;
    float dilution=exp(-clamp(flowDivergence*delta,-.5,.5));
    scalars.ra*=dilution;
    }
    float fuel=scalars.r;
    float oxygen=scalars.g;
    float temp=scalars.b, soot=scalars.a;
    if(temp+soot>.00001){
      vec3 force=vortexForce(at);
      float confinement=sourceEnabled<.5&&emitterKind==6?2.2:sourceEnabled<.5&&emitterKind==0&&sourceEffectKind<=0?3.5:emitterKind>=22&&emitterKind<=${MAX_POWER_EMITTER}?powerConfinement:1.;
      if(originalPeakForceTarget(emitterKind,sourceEffectKind,sourceEnabled)){
        confinement*=originalPeakForceScale(length(force*simExtent)*confinement,originalPeakForceMaximum(emitterKind));
      }
      vf.xyz+=force*delta*confinement;
    }
    // The source field enters as fresh gas. It never clips existing fire to glyph edges.
    float worldX=simMin.x+p.x*simExtent.x, worldZ=simMin.y+p.y*simExtent.y, worldY=(depth-.5)*simExtent.z;
    woodFuelGas(vec3(worldX,worldZ,worldY),delta,fuel,oxygen,temp);
    float support=0.0, sheet=0.0;
    if(sourceEnabled>.5&&woodEnabled<.5) {
    vec4 source=texture(sourceTex,p);
    support=source.r;
    // Most atlas cells have no emitter. Preserve their air entrainment while
    // avoiding the ignition, thickness, pulse and jet calculations entirely.
    if(support>0.) {
    float age=clock-source.g*10.0;
    float opened=smoothstep(-.055,.04,age);
    float leading=exp(-pow((age-.08)/.105,2.0));
    float valve=exp(-3.2*max(0.0,clock-6.8));
    float corr=.22*sin(worldX*3.1+worldZ*3.7-clock*2.4)+.085*sin(worldX*9.0-worldZ*7.0+clock*4.3);
    float halfwidth=texture(widthTex,p).r*.27;
    float sheetDepth=.065+.045*sqrt(clamp(halfwidth/.27,0.0,1.0));
    sheet=exp(-1.5*pow((worldY-corr)/max(.035,sheetDepth),2.0))*support;
    // Turbulent ambient air meets rising fuel away from the thin source sheet.
    // The sheet itself remains fuel rich, so it cannot become a solid bright mask.

    float pulse=texture(noiseTex,p*vec2(3.0,2.0)+vec2(clock*.04,-clock*.08)).r;
    float puff=mix(.75,1.25,smoothstep(.35,.65,pulse));
    float added=sheet*valve*delta*(8.*leading+.6*opened*puff);
    float fuelBeforeRelease=fuel;
    float inject=sourceMomentumFraction(fuelBeforeRelease,added);
    oxygen=1.-sourceOxygenDeficit(1.-oxygen,added);
    temp=sourceSensibleHeat(temp,fuel,added,mix(.5,1.25,leading));
    temp=sourceIgnition(temp,added,mix(.28,.69,leading));fuel+=added;
    vec2 tangent=normalize(source.ba*2.0-1.0+vec2(.0001));
    float speed=.25+7.75*leading;
    float shear=4.8*sin(worldY*19.0+clock*13.0)*cos((worldX+worldZ)*12.0-clock*11.0)*leading;
    vf.x=mix(vf.x,(tangent.x*speed-tangent.y*shear)/simExtent.x,inject);
    vf.y=mix(vf.y,(tangent.y*speed+tangent.x*shear)/simExtent.y,inject);
    vf.z=mix(vf.z,(.18+sin(worldX*38.0+worldZ*27.0+clock*23.0)*(.12+.68*leading))/simExtent.z,inject);
    vf.y+=sheet*leading*sin(worldY*18.0+clock*15.0)*20.0*delta/simExtent.y;
    vf.z+=sheet*leading*cos(worldZ*14.0-clock*12.0)*16.0*delta/simExtent.z;
    }
    } else {
    if(woodEnabled<.5 && brushActive>.5 && (emitterKind!=6 || burstAge<burstDuration)) {

    // A click creates a new fuel source in the same simulated volume. During a
    // drag the source fills the segment between consecutive simulation steps.
    vec2 start=simMin.xy+brushFrom*simExtent.xy;
    vec2 end=simMin.xy+brushTo*simExtent.xy;
    vec2 path=end-start;
    vec2 here=vec2(worldX,worldZ);
    float along=clamp(dot(here-start,path)/max(dot(path,path),.00001),0.0,1.0);
    vec2 local=here-(emitterKind>=22?end:start+path*along);
    float brush; vec3 jet;
    emitter(local,worldY,brush,jet);
    if(brush>.000001) {
    if(emitterKind>=22&&emitterKind<=${MAX_POWER_EMITTER}){
      // Integrate a release rate over simulation time. Source changes do not
      // replace advected gas or re-initialize the combustion field.
      float fuelBeforeRelease=fuel;
      float added=brush*delta*6.*fuelProfile.x;
      if(smokeOnly>.5)soot+=added*fuelProfile.y;
      else {
        fuel+=added;oxygen/=1.+added;
        // Bound source ignition instead of adding sensible heat every frame.
        // A hotter transported flame is retained. Oxygen is the absolute
        // fraction here; the Volume deficit uses (deficit+added)/(1+added).
        temp=powerIgnitionHeat(temp,fuelBeforeRelease,added,sourceHeat,oxygen);
      }
      vf.xyz=mix(vf.xyz,jet/simExtent,sourceMomentumFraction(fuelBeforeRelease,added));
    }else if(emitterKind==6){
      float added=brush*delta*9.*fuelProfile.x;
      vec3 mixField=texture(noiseTex,local*.42+worldY*vec2(.31,-.22)+vec2(.17,.38)).rgb;
      float fuelBeforeRelease=fuel;
      if(smokeOnly>.5)soot+=added*.75*fuelProfile.y;
      else{
       oxygen=1.-sourceMixtureDeficit(1.-oxygen,added,mix(.035,.5,smoothstep(.28,.7,mixField.b)));
       temp=sourceSensibleHeat(temp,fuel,added,mix(.5,1.65,smoothstep(.28,.72,mixField.g))*sourceHeat);
       temp=sourceIgnition(temp,added,sourceHeat*.69);fuel+=added;
      }
      vf.xyz=mix(vf.xyz,jet/simExtent,sourceMomentumFraction(fuelBeforeRelease,added));
    }else{
    float pulse=.72+.28*sin(clock*47.0);
    if(emitterKind==1||emitterKind==2||emitterKind==5)pulse=mix(.72,1.08,texture(noiseTex,vec2(clock*.27+.13,clock*.07+.7)).r);
    if(emitterKind==0&&sourceEffectKind<=0)pulse=.94+.06*sin(clock*2.3+.7);
    float fuelBeforeRelease=fuel;
    float added=brush*delta*ordinaryFuelRate(float(sourceEffectKind),1.)*pulse*fuelProfile.x;
    if(smokeOnly>.5)soot+=added*.8*fuelProfile.y;
    else{
     float incomingOxygen=emitterKind==2?.8:0.;
     oxygen=1.-sourceMixtureDeficit(1.-oxygen,added,incomingOxygen);
     if(emitterKind==0&&sourceEffectKind<=0){
      temp=sourceSensibleHeat(temp,fuel,added,${((PLUME_THERMAL.fuelTemperatureK-GAS_THERMO.ambientK)/GAS_THERMO.temperatureScaleK).toFixed(8)});
      vec3 q=vec3(local.x,local.y,worldY)/sourceScale;
      vec3 pilotQ=(q-vec3(${PLUME_THERMAL.pilotOffset.join(',')}))/vec3(${PLUME_THERMAL.pilotWidth.join(',')});
      float dose=boundedPilotDose(burstAge,delta,${PLUME_THERMAL.pilotHeatingRate}.,${PLUME_THERMAL.startupHeatingRate}.,${PLUME_THERMAL.startupDurationS});
      temp+=dose*sourceHeat/${PLUME_THERMAL.referencePilotHeat}*exp(-dot(pilotQ,pilotQ))/(1.+fuel+added);
     }else{
      temp=sourceSensibleHeat(temp,fuel,added,.85*sourceHeat);
      temp=sourceIgnition(temp,added,sourceHeat*.47);
     }
     fuel+=added;
    }
    jet/=simExtent;
    jet.xy+=clamp(pointerMotion*.12,vec2(-.24),vec2(.24));
    vf.xyz=mix(vf.xyz,jet,sourceMomentumFraction(fuelBeforeRelease,added));
    }
    }
    }
    }

    float fuelBeforeGround=fuel;
    groundFuelGas(vec3(worldX,worldZ,worldY),delta,fuel,temp);
    if(emitterKind>=22&&emitterKind<=${MAX_POWER_EMITTER})oxygen/=1.+max(fuel-fuelBeforeGround,0.);
    // Ambient cells retain transported/projected velocity, but need no
    // combustion, turbulence or buoyancy work. Test after source injection so
    // ignition is never skipped, and retain oxygen deficits until they mix out.
    if(fuel+temp+soot<=.00001 && oxygen>=.99999){
      vf.xyz*=exp(-delta*.04);
      if(worldZ<.10)vf.y=max(vf.y,0.);
      outVF=vec4(vf.xyz,0.);
      outChem=vec4(0.,1.,0.,0.);
      return;
    }
    float activation;
    activation=smokeOnly>.5?0.:smoothstep(${GAS_CHEMISTRY.ignitionLow},${GAS_CHEMISTRY.ignitionHigh},temp);
    if(woodEnabled>.5){float products=smoothstep(.005,.05,max(soot,1.-oxygen));activation=max(smoothstep(.35,.75,temp),products*smoothstep(.15,.35,temp));}
    float burn=min(fuel,oxygen/${GAS_CHEMISTRY.oxygenPerFuel})*(1.0-exp(-${GAS_CHEMISTRY.rate}*delta))*activation;
    if(woodEnabled>.5)burn=min(fuel,oxygen/.7)*(1.-exp(-4.*delta))*activation;
    float mixtureCapacity=1.+max(fuel,0.);
    fuel=max(0.0,fuel-burn);
    oxygen=clamp(oxygen-burn*.7,0.0,1.0);
    float heatRelease=${GAS_CHEMISTRY.heatRelease};
    temp=coolGasTemperature(temp+burn*(woodEnabled>.5?${(WOOD_THERMO.volatileHeatJkg*WOOD_THERMO.gasSensibleFraction/(WOOD_THERMO.gasHeatCapacityJkgK*WOOD_THERMO.gasHeatScaleK)).toFixed(8)}/mixtureCapacity:heatRelease/mixtureCapacity),fuel,soot,delta);
    // Soot travels with the same corrected flow as heat and fuel. Fuel-rich
    // burning produces more soot; hot oxygen oxidizes it. Cold smoke survives
    // cooling, rather than disappearing with the flame's temperature.
    float sootYield=fuelProfile.y*richSootYield(fuel+burn,oxygen+burn*.7);
    soot+=burn*sootYield;
    float oxidized=soot*(1.0-exp(-1.2*oxygen*smoothstep(.7,1.8,temp)*delta));
    oxidized=min(oxidized,oxygen/.08);
    soot=clamp((soot-oxidized)*exp(-smokeLossRate(temp)*smokeDecayDt),0.0,8.0);
    oxygen=max(0.0,oxygen-oxidized*.08);
    temp+=oxidized*.3;

    // Buoyancy, resolved swirl and an interactive force all modify the live state.
    float n1=texture(noiseTex,p*vec2(1.6,1.2)+vec2(clock*.037,depth*.41)).r;
    float n2=texture(noiseTex,p*vec2(4.2,3.0)+vec2(-clock*.08,depth*.83)).g;
    float curl=(n1-n2)*(.035+.13*temp);
    vec2 ambientScale=vec2(originalAmbientScale(emitterKind,sourceEffectKind,sourceEnabled,simExtent.x),originalAmbientScale(emitterKind,sourceEffectKind,sourceEnabled,simExtent.y));
    vf.x+=curl*delta*(sourceEnabled<.5&&emitterKind==2?.8:5.0)*ambientScale.x;
    float buoyancy=sourceEnabled>.5?6.5:emitterKind==1?3.2*sourceLift:emitterKind==2?3.:emitterKind==3||emitterKind==4?.35:sourceEnabled<.5&&emitterKind==0&&sourceEffectKind<=0?2.1:emitterKind>=7?presetBuoyancy:6.5;
    if(sourceEnabled<.5 && emitterKind==6)buoyancy=mix(.3,3.6,smoothstep(.2,1.2,burstAge));
    vf.y+=(densityBuoyancy(temp,buoyancy)-smokeWeight(soot,temp))*delta/simExtent.y;
    #if FIRE_HAS_POWERS
    if(sourceEnabled<.5&&brushActive>.5&&emitterKind>=22&&emitterKind<=${MAX_POWER_EMITTER}){
      for(int actor=0;actor<${POWER_CAST_CAPACITY};actor++){
        vec4 kindScale=powerCastKindScale[actor];if(kindScale.z<.5)continue;
        if(!((kindScale.x>3.5&&kindScale.x<4.5)||(kindScale.x>19.5&&kindScale.x<20.5)))continue;
        vec4 originAge=powerCastOriginAge[actor],directionStrength=powerCastDirectionStrength[actor],targetCharge=powerCastTargetCharge[actor];
        vf.xyz+=powerCastAcceleration(kindScale.x,vec3(worldX,worldZ,worldY),originAge.xyz,kindScale.y,sourceSampleAge(originAge.w,kindScale.z,delta),sourceClock(clock-delta,kindScale.w,delta),directionStrength.xyz,directionStrength.w,targetCharge.xyz,targetCharge.w)*delta/simExtent;
      }
    }
    #endif
    if(sourceEnabled<.5 && emitterKind==6 && temp>.18){
      // Resolved 3D curl accelerates gas at two smaller scales. Its signal is
      // sampled only by simulation; lighting has no noise or texture overlay.
      vec3 q=vec3(worldX,worldZ-clock*.8,worldY)+vec3(clock*.21,0,-clock*.17);
      vec3 eddy=curlNoise(q,.23)*9.+curlNoise(q+vec3(3.4,1.1,5.7),.11)*2.;
      float energy=smoothstep(.18,.75,temp)*exp(-max(burstAge,0.)*.4);
      vf.xyz+=eddy*energy*delta/simExtent;
    }
    if(sourceEnabled<.5 && emitterKind>=22 && emitterKind<=${MAX_POWER_EMITTER} && temp>.35){
      // A single resolved 3D curl octave breaks up the transported power gas.
      // Reuse the existing turbulence basis only in warm cells; no extra pass,
      // resource, or display-space detail is introduced.
      vec3 q=vec3(worldX,worldZ-clock*.65,worldY)+vec3(clock*.16,0,-clock*.13);
      float energy=smoothstep(.35,1.1,temp)*clamp(powerTurbulence,.6,1.2);
      if(emitterKind==23){
        vec3 eddy=curlNoise(q,.20)*3.4*energy;
        eddy*=originalPeakForceScale(length(eddy),originalPeakForceMaximum(emitterKind));
        vf.xyz+=eddy*delta/simExtent;
      }else vf.xyz+=curlNoise(q,.20)*3.4*energy*delta/simExtent;
    }
    // Sculpted fire uses a circulating force field, not a screen-space mask.
    // Fuel, heat and soot still advect and cool through the same solver.
    if(sourceEnabled<.5 && (emitterKind==3||emitterKind==4) && temp+soot+fuel>.00001){
      vec2 center=simMin.xy+brushTo*simExtent.xy;
      vec2 q=vec2(worldX,worldZ)-center;float radius=length(q);
      float influence=emitterKind==3?exp(-pow((radius-1.30)/.45,2.)):exp(-pow(radius/.95,4.));
      vec2 tangent=vec2(-q.y,q.x)/max(radius,.05);
      vec2 target=tangent*(emitterKind==3?1.8:1.2)+q*.18;
      if(emitterKind==3){
        vec2 horizontal=vec2(worldX-center.x,worldY);float ringRadius=length(horizontal);
        float ringWeight=exp(-pow((ringRadius-.65*sourceScale)/(.25*sourceScale),2.))*exp(-pow(q.y/(.30*sourceScale),2.));
        vec2 ringTarget=vec2(-horizontal.y,horizontal.x)/max(ringRadius,.05)*1.8;
        vf.xz=mix(vf.xz,ringTarget/simExtent.xz,1.-exp(-delta*5.*ringWeight));
      }
      else {
        vec3 q3=vec3(q,worldY);float r=length(q3);
        float weight=exp(-pow(r/1.4,4.));
        vec3 circulating=cross(vec3(.8,.5,1.2),q3)*2.-q3*max(r-.60,0.)*8.;
        vf.xyz=mix(vf.xyz,circulating/simExtent,1.-exp(-delta*12.*weight));
      }
    }
    float waveX=worldX*4.7+clock*2.4+(n1-.5)*3.0;
    float waveZ=worldZ*5.3-clock*1.8+(n2-.5)*3.0;
    float swirl=(.05+.35*clamp(temp,0.0,2.0))*delta*(1.0-.7*support)
                 *mix(.15,1.0,sourceEnabled);
    if(sourceEnabled<.5&&emitterKind==2)swirl*=.15;
    vf.x+=sin(waveX)*cos(waveZ)*swirl*ambientScale.x;
    vf.y-=cos(waveX)*sin(waveZ)*swirl*ambientScale.y;
    // Depth shear belongs to the evolving velocity, never the display shader.
    vf.z+=(sin(worldX*3.7+worldZ*4.3+clock*2.1)*(n2-.5))
          *delta*(.15+.55*clamp(temp+soot,0.,1.))/simExtent.z;
    vec2 distance=p-pointer;
    float falloff=exp(-dot(distance,distance)/(pointerStrength>.5?.005:.0025));
    vf.xy+=pointerStrength*falloff*(pointerMotion*.055+normalize(distance+vec2(.0001))*.075)*delta*24.0;
    vf.xyz*=exp(-delta*.04);
    // Free gas leaves the finite domain instead of sticking to its boundary.
    float edge=smoothstep(0.0,.055,p.x)*smoothstep(0.0,.055,1.0-p.x)
              *smoothstep(0.0,.07,p.y)*smoothstep(0.0,.05,1.0-p.y);
    float depthEdge=smoothstep(0.,.055,depth)*smoothstep(0.,.055,1.-depth);
    edge*=depthEdge;
    // Preserve the 30 Hz sponge strength at any physical timestep.
    edge=pow(max(edge,.000001),delta*30.);
    fuel*=edge; temp*=edge; soot*=edge;
    // A no-through-flow floor keeps cursor flames attached to the room.
    if(worldZ<0.){fuel=0.;temp=0.;soot=0.;burn=0.;oxygen=1.;vf.y=max(vf.y,0.);}
    else if(worldZ<.10) vf.y=max(vf.y,0.);
    oxygen=mix(1.0,oxygen,edge);
    // Remove only invisible storage residue: binary16 damping otherwise stops
    // changing tiny cold soot. Fresh smoke retains its .055/s dissipation.
    if(soot<${SMOKE_CLEAR_DENSITY})soot=0.;
    // Keep transported scalars together: the limiter reads one RGBA texel per
    // corner. Reaction is recomputed here, so it shares velocity's spare lane.
    outVF=vec4(vf.xyz,burn/max(delta,.0001));
    outChem=vec4(fuel,oxygen,temp,soot);
  }`;
  // Shared-face fluxes on stationary cells before advection. Each interior
  // exchange is antisymmetric; no donor-position snapping or depth bias.
  const diffusion=`#version 300 es
  ${shared}
  uniform float delta;uniform float smokeDecayDt;
  layout(location=1) out vec4 mixed;
  vec4 donor(ivec3 q){q=clamp(q,ivec3(0),ivec3(${NX-1},${NZ-1},${DEPTH-1}));return texelFetch(chemTex,ivec2(q.x+(q.z%${TILES_X})*${NX},q.y+(q.z/${TILES_X})*${NZ}),0);}
  void main(){
   ivec2 ip=ivec2(gl_FragCoord.xy);ivec3 q=ivec3(ip.x%${NX},ip.y%${NZ},ip.x/${NX}+${TILES_X}*(ip.y/${NZ}));
   vec4 c=donor(q);vec3 h=simExtent/vec3(NXf,NZf,DEPTHf-1.);
   vec3 weights=delta/(h*h);vec4 D=vec4(${GAS_DIFFUSIVITY},${GAS_DIFFUSIVITY},${PRODUCT_DIFFUSIVITY},${PRODUCT_DIFFUSIVITY});
   mixed=c+D*(weights.x*(donor(q+ivec3(1,0,0))+donor(q-ivec3(1,0,0))-2.*c)
     +weights.y*(donor(q+ivec3(0,1,0))+donor(q-ivec3(0,1,0))-2.*c)
     +weights.z*(donor(q+ivec3(0,0,1))+donor(q-ivec3(0,0,1))-2.*c));
  }`;
  const rendering = (roomGLSL) => `#version 300 es
  ${shared}
  ${roomGLSL}
  ${woodMaterialGLSL}
  ${propsGLSL}
  ${groundSurfaceGLSL}
  uniform sampler2D smokeLightTex;
  uniform sampler2D woodSurfaceTex;
  uniform float woodSurfaceVisible;
  uniform float roomEnabled;
  uniform float customLighting;
  uniform float viewZoom;
  uniform vec2 viewPan;
  uniform float inspectSmoke;
  layout(location=0) out vec4 outColor;
  void main(){
    vec2 screenWorld=(uv-.5)*vec2(14.,7.875)/viewZoom+vec2(0,2.8875)+viewPan;
    vec2 p=(screenWorld-fireMin.xy)/fireExtent.xy;
    if(roomEnabled<.5 && (any(lessThan(p,vec2(0)))||any(greaterThan(p,vec2(1))))){outColor=vec4(0,0,0,1);return;}
    vec3 light=vec3(0.0);
    float transmittance=1.0;
    vec3 ray=roomEnabled>.5?roomRay(uv):vec3(0,0,-1),surfaceNormal=vec3(0);
    vec3 eye=roomEnabled>.5?cameraEye:vec3(fireMin.xy+p*fireExtent.xy,3.);
    float surfaceDistance=1000.;
    vec3 surface=vec3(0);
    if(roomEnabled>.5){
      surfaceDistance=roomHit(cameraEye,ray,surfaceNormal);
      surface=roomSurface(cameraEye+ray*surfaceDistance,surfaceNormal,-ray);
      if(surfaceNormal.y>.5)surface=groundFloorSurface(cameraEye+ray*surfaceDistance,surface);
    }
    vec3 propColor;
    if(sourceProp(eye,ray,surfaceDistance,propColor))surface=propColor;
    if(sourceGuideSurface(eye,ray,surfaceDistance,propColor))surface=propColor;
    if(woodSurfaceVisible>.5){vec4 woodSurface=texelFetch(woodSurfaceTex,ivec2(gl_FragCoord.xy),0);if(woodSurface.a<surfaceDistance){surfaceDistance=woodSurface.a;surface=woodSurface.rgb;}}
    // Integrate the continuous trilinear field at ray-segment midpoints.
    // Sampling isolated atlas layers imprints slice contours into lit smoke.
    // The sample count and simulated depth resolution stay unchanged. The volume has
    // actual parallax; no screen-space billboard or rendered fire plane is used.
    bool fineDepth=visibleEmitter==4||visibleEmitter==6||(visibleEmitter>=22&&visibleEmitter<=${MAX_POWER_EMITTER});
    int sampleCount=fineDepth?${DEPTH*2}:${DEPTH};
    for(int i=0;i<${DEPTH*2};i++){
      if(i>=sampleCount)break;
      float z=(float(i)+.5)/float(sampleCount)*float(${DEPTH-1});
      z=float(${DEPTH-1})-z;
      float worldDepth=fireMin.z+z/float(${DEPTH-1})*fireExtent.z;
      float distance=(worldDepth-eye.z)/ray.z;
      if(distance<0. || distance>=surfaceDistance)continue;
      if(roomEnabled>.5){
        vec3 at=eye+ray*distance;
        p=(at.xy-fireMin.xy)/fireExtent.xy;
        if(any(lessThan(p,vec2(0)))||any(greaterThan(p,vec2(1)))) continue;
      }
      vec4 c=field(chemTex,vec3(p,z/float(${DEPTH-1})));
      float temp=c.b, soot=c.a;
      if(temp<=0.0 && soot<=0.0) continue;
      float reaction=field(vfTex,vec3(p,z/float(${DEPTH-1}))).a;
      // Soot provides the bulk extinction; reacting gas remains optically thin.
      float sigma=clamp(sootExtinction(soot)+(1.-inspectSmoke)*reaction*.025,0.0,24.0);
      vec3 emission=(1.-inspectSmoke)*(fireEmission(reaction,temp)+sootEmission(soot,temp));
      float stepLength=fireExtent.z/float(sampleCount)/(roomEnabled>.5?max(-ray.z,.1):1.);
      float opacity=1.0-exp(-sigma*stepLength);
      // Light is attenuated by the advected soot above this point. This gives
      // cold smoke volume and self-shadowing without a procedural overlay.
      vec3 scatter;
      if(roomEnabled>.5||customLighting>.5) scatter=smokeIrradiance(vec3(p,z/float(${DEPTH-1})));
      else {
        float lo=floor(z),hi=min(lo+1.,float(${DEPTH-1}));
        vec2 lp=clamp(p,vec2(.5/128.0,.5/72.0),vec2(1.0-.5/128.0,1.0-.5/72.0));
        vec2 lightUV=(vec2(mod(lo,8.0),floor(lo/8.0))+lp)/vec2(8.0,${TILES_Y}.0);
        vec2 lightHi=(vec2(mod(hi,8.0),floor(hi/8.0))+lp)/vec2(8.0,${TILES_Y}.0);
        float key=exp(-mix(texture(smokeLightTex,lightUV).r,texture(smokeLightTex,lightHi).r,fract(z)));
        scatter=vec3(.020,.019,.025)+vec3(1.4,1.10,.85)*key;
      }
      // A modest scattering albedo gives soot illuminated rims while its
      // extinction still silhouettes the dense core against the room.
      float scattering=sootExtinction(soot)*mix(.14,.025,smoothstep(.3,.95,temp))/12.56637;
      light+=transmittance*(emission+scattering*scatter)*opacity/max(sigma,.0001);
      transmittance*=1.0-opacity;
    }
    outColor=vec4(light+transmittance*surface,1.0);
  }`;
  const presentation = `#version 300 es
  precision highp float;
  in vec2 uv;
  uniform sampler2D projection;
  layout(location=0) out vec4 outColor;
  ${firePresentationGLSL}
  void main(){
    vec2 stepSize=1.0/vec2(${RW}.0,${RH}.0);
    vec3 linear=texture(projection,uv).rgb;
    vec3 glow=(texture(projection,uv+vec2(stepSize.x*3.0,0.0)).rgb+
               texture(projection,uv-vec2(stepSize.x*3.0,0.0)).rgb+
               texture(projection,uv+vec2(0.0,stepSize.y*3.0)).rgb+
               texture(projection,uv-vec2(0.0,stepSize.y*3.0)).rgb)*.25;
    linear=linear+max(glow-vec3(1.),vec3(0))*.012;
    outColor=vec4(presentFire(linear),1.0);
  }`;

 return {vertex,shared,simulation,diffusion,rendering,presentation};
}
