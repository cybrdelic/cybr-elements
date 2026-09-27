(() => {
  'use strict';
  // The source texture is static emitter geometry, not footage or baked motion.
  // Every visible frame is generated from the evolving GPU state below.
  const fullGrid = new URL(location.href).searchParams.get('grid') === '896';
  const NX = fullGrid ? 896 : 640, NZ = fullGrid ? 504 : 360;
  const DEPTH = 32, TILES_X = 8, TILES_Y = 4;
  const SOURCE_NX = 896, SOURCE_NZ = 504;
  const RW = 896, RH = 504;
  const AW = NX * TILES_X, AH = NZ * TILES_Y;
  const STEP = 1 / 30, DURATION = 9.8;
  let stateRevision=0, roomLightRevision=-1, smokeLightRevision=-1;
  const canvas = document.querySelector('#fire');
  const view = document.querySelector('#view');
  const message = document.querySelector('#message');
  const metrics = document.querySelector('#metrics');
  const help = document.querySelector('#help');
  const modeButton = document.querySelector('#mode');
  const restartButton = document.querySelector('#restart');
  const extinguishButton = document.querySelector('#extinguish');
  const roomToggle = document.querySelector('#room');
  const orbitControl = document.querySelector('#orbit');
  const zoomControl = document.querySelector('#zoom');
  const focusButton = document.querySelector('#focus-fire');
  const fullscreenButton = document.querySelector('#fullscreen');
  let viewZoom=1, panX=0, panY=0, panTool=false, panGesture=null;
  const lensTan=()=>.3443276133/viewZoom;
  let roomEnabled = new URL(location.href).searchParams.get('room') !== '0';
  let viewAngle = Number(new URL(location.href).searchParams.get('angle') ?? 16);
  viewAngle = Number.isFinite(viewAngle) ? Math.max(-30,Math.min(30,viewAngle)) : 16;
  roomToggle.checked = roomEnabled; orbitControl.value = viewAngle; orbitControl.disabled = !roomEnabled;
  const sceneLabel=document.querySelector('.stamp strong');
  sceneLabel.textContent=roomEnabled?'Fire-lit room · etched stone':'Fire and smoke · black background';
  function camera() {
    const yaw=viewAngle*Math.PI/180;
    const eye=[panX+Math.sin(yaw)*13,3.5+panY,Math.cos(yaw)*13];
    const normalize=v=>{const length=Math.hypot(...v);return v.map(x=>x/length);};
    const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
    const forward=normalize([panX-eye[0],2.4+panY-eye[1],-eye[2]]);
    const right=normalize(cross(forward,[0,1,0]));
    return {eye,forward,right,up:cross(right,forward)};
  }
  const gl = canvas.getContext('webgl2', { alpha: false, antialias: false, powerPreference: 'high-performance', preserveDrawingBuffer: false });
  if (!gl) { message.textContent = 'WebGL 2 is required for the live volume'; return; }
  if (!gl.getExtension('EXT_color_buffer_float')) { message.textContent = 'Floating point GPU targets are unavailable in this browser'; return; }
  const halfFloatLinear = !!gl.getExtension('OES_texture_float_linear');

  const vertex = `#version 300 es
  precision highp float;
  out vec2 uv;
  void main(){
    vec2 p=vec2((gl_VertexID<<1)&2, gl_VertexID&2);
    uv=p;
    gl_Position=vec4(p*2.0-1.0,0.0,1.0);
  }`;
  const shared = `
  precision highp float;
  precision highp sampler2D;
  in vec2 uv;
  uniform sampler2D vfTex;
  uniform sampler2D chemTex;
  uniform sampler2D noiseTex;
  uniform float clock;
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
  const simulation = () => `#version 300 es
  ${shared}
  ${pressure.samplingGLSL}
  ${vorticity.samplingGLSL}
  uniform sampler2D sourceTex;
  uniform sampler2D widthTex;
  uniform float delta;
  uniform vec2 pointer;
  uniform vec2 pointerMotion;
  uniform float pointerStrength;
  uniform vec2 brushFrom;
  uniform vec2 brushTo;
  uniform float brushActive;
  uniform float sourceEnabled;
  ${advection.correctionGLSL}
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
    vec3 back=at-vec3(oldVF.xy,oldVF.z)*delta;
    vec4 vf=field(vfTex,back);
    vf.xyz+=samplePressureCorrection(back);
    vec4 scalars=maccormackScalars(at,back,oldVF.xyz);
    float fuel=scalars.r;
    float oxygen=scalars.g;
    float temp=scalars.b, soot=scalars.a;
    if(temp+soot>.00001) vf.xyz+=vortexForce(at)*delta;
    // The source field enters as fresh gas. It never clips existing fire to glyph edges.
    float worldX=-7.0+p.x*14.0, worldZ=-1.05+p.y*7.875, worldY=(depth-.5)*1.8;
    float support=0.0, sheet=0.0;
    if(sourceEnabled>.5) {
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
    float entrainment=(.05+.8*clamp(temp,0.0,1.0))*(1.0-clamp(sheet,0.0,1.0));
    oxygen=mix(oxygen,1.0,1.0-exp(-delta*entrainment));
    float front=clamp(sheet*leading*delta*19.0,0.0,1.0);
    float pulse=texture(noiseTex,p*vec2(3.0,2.0)+vec2(clock*.04,-clock*.08)).r;
    float puff=mix(.75,1.25,smoothstep(.35,.65,pulse));
    float sustained=clamp(sheet*opened*valve*delta*2.5*puff,0.0,1.0);
    float inject=clamp(front+sustained,0.0,1.0);
    fuel=mix(fuel,.55,sustained);
    fuel=mix(fuel,.95,front);
    oxygen*=1.0-inject;
    temp=mix(temp,.5,sustained);
    temp=mix(temp,1.25,front);
    vec2 tangent=normalize(source.ba*2.0-1.0+vec2(.0001));
    float speed=.25+7.75*leading;
    float shear=4.8*sin(worldY*19.0+clock*13.0)*cos((worldX+worldZ)*12.0-clock*11.0)*leading;
    vf.x=mix(vf.x,(tangent.x*speed-tangent.y*shear)/14.0,inject);
    vf.y=mix(vf.y,(tangent.y*speed+tangent.x*shear)/7.875,inject);
    vf.z=mix(vf.z,(.18+sin(worldX*38.0+worldZ*27.0+clock*23.0)*(.12+.68*leading))/1.8,inject);
    vf.y+=sheet*leading*sin(worldY*18.0+clock*15.0)*20.0*delta/7.875;
    vf.z+=sheet*leading*cos(worldZ*14.0-clock*12.0)*16.0*delta/1.8;
    } else {
      oxygen=mix(oxygen,1.0,1.0-exp(-delta*(.05+.8*clamp(temp,0.0,1.0))));
    }
    } else {
    oxygen=mix(oxygen,1.0,1.0-exp(-delta*(.05+.8*clamp(temp,0.0,1.0))));
    if(brushActive>.5) {

    // A click creates a new fuel source in the same simulated volume. During a
    // drag the source fills the segment between consecutive simulation steps.
    vec2 start=vec2(-7.0+brushFrom.x*14.0,-1.05+brushFrom.y*7.875);
    vec2 end=vec2(-7.0+brushTo.x*14.0,-1.05+brushTo.y*7.875);
    vec2 path=end-start;
    vec2 here=vec2(worldX,worldZ);
    float along=clamp(dot(here-start,path)/max(dot(path,path),.00001),0.0,1.0);
    vec2 local=here-(start+path*along);
    // The offline emitter feeds a moving, sheared sheet of gas. A fixed
    // spherical source with a uniform upward velocity makes a laminar column.
    float sourceDepth=.16*sin(clock*7.3)+local.x*.48*sin(clock*9.1);
    float radiusSquared=pow(local.x/.42,2.0)+pow(local.y/.18,2.0)+pow((worldY-sourceDepth)/.15,2.0);
    // Beyond this support, injection is below one RGBA16F subnormal quantum.
    // Skip nozzle work there; existing fire and smoke still evolve everywhere.
    if(radiusSquared<12.0) {
    // Uneven gas feed produces separate tongues at the source. This enters the
    // gas state and is subsequently advected; it is not a display texture.
    float feed=.62+.38*sin(local.x*18.+worldY*23.+clock*11.)
                            *sin(local.x*9.-worldY*17.-clock*7.3);
    float brush=exp(-1.5*radiusSquared)*feed;
    float gasFeed=brush*(1.0-exp(-1.8*delta));
    float nozzle=clamp(brush*delta*20.0*(.72+.28*sin(clock*47.0)),0.0,1.0);
    fuel=mix(fuel,.22,gasFeed);
    oxygen=mix(oxygen,.80,gasFeed);
    temp=mix(temp,.80,gasFeed);
    fuel=mix(fuel,.95,nozzle);
    oxygen*=1.0-nozzle;
    temp=mix(temp,.85,nozzle);
    float jetShear=4.8*sin(worldY*19.0+clock*13.0)
                       *cos((local.x+local.y)*12.0-clock*11.0);
    vec3 jet=vec3(jetShear*.35/14.0,(2.8+jetShear*.30)/7.875,
                  sin(local.x*23.0+local.y*19.0+clock*13.0)*1.1/1.8);
    jet.xy+=clamp(pointerMotion*.12,vec2(-.24),vec2(.24));
    vf.xyz=mix(vf.xyz,jet,nozzle);
    }
    }
    }

    float activation=clamp((temp-.15)/.22,0.0,1.0);
    float burn=min(fuel,oxygen*.7)*(1.0-exp(-8.0*delta))*activation;
    fuel=max(0.0,fuel-burn);
    oxygen=clamp(oxygen-burn/.7,0.0,1.0);
    temp=min(3.0,(temp+burn*5.5)*exp(-1.15*delta));
    // Soot travels with the same corrected flow as heat and fuel. Fuel-rich
    // burning produces more soot; hot oxygen oxidizes it. Cold smoke survives
    // cooling, rather than disappearing with the flame's temperature.
    float sootYield=mix(.45,1.55,1.0-oxygen);
    soot+=burn*sootYield;
    float oxidized=soot*(1.0-exp(-1.2*oxygen*smoothstep(.7,1.8,temp)*delta));
    oxidized=min(oxidized,oxygen/.08);
    soot=clamp((soot-oxidized)*exp(-.055*delta),0.0,8.0);
    oxygen=max(0.0,oxygen-oxidized*.08);
    temp=min(3.0,temp+oxidized*.3);

    // Buoyancy, resolved swirl and an interactive force all modify the live state.
    float n1=texture(noiseTex,p*vec2(1.6,1.2)+vec2(clock*.037,depth*.41)).r;
    float n2=texture(noiseTex,p*vec2(4.2,3.0)+vec2(-clock*.08,depth*.83)).g;
    float curl=(n1-n2)*(.035+.13*temp);
    vf.x+=curl*delta*5.0;
    vf.y+=(temp*6.5-soot*.32)*delta/7.875;
    float waveX=worldX*4.7+clock*2.4+(n1-.5)*3.0;
    float waveZ=worldZ*5.3-clock*1.8+(n2-.5)*3.0;
    float swirl=(.05+.35*clamp(temp,0.0,2.0))*delta*(1.0-.7*support)
                 *mix(.15,1.0,sourceEnabled);
    vf.x+=sin(waveX)*cos(waveZ)*swirl;
    vf.y-=cos(waveX)*sin(waveZ)*swirl;
    // Depth shear belongs to the evolving velocity, never the display shader.
    vf.z+=(sin(worldX*3.7+worldZ*4.3+clock*2.1)*(n2-.5))
          *delta*(.15+.55*clamp(temp+soot,0.,1.))/1.8;
    vec2 distance=p-pointer;
    float falloff=exp(-dot(distance,distance)/(pointerStrength>.5?.005:.0025));
    vf.xy+=pointerStrength*falloff*(pointerMotion*.055+normalize(distance+vec2(.0001))*.075)*delta*24.0;
    vf.xyz*=exp(-delta*.30);
    // Free gas leaves the finite domain instead of sticking to its boundary.
    float edge=smoothstep(0.0,.055,p.x)*smoothstep(0.0,.055,1.0-p.x)
              *smoothstep(0.0,.07,p.y)*smoothstep(0.0,.05,1.0-p.y);
    float depthEdge=smoothstep(0.,.055,depth)*smoothstep(0.,.055,1.-depth);
    edge*=depthEdge;
    fuel*=edge; temp*=edge; soot*=edge;
    // A no-through-flow floor keeps cursor flames attached to the room.
    if(worldZ<0.){fuel=0.;temp=0.;soot=0.;burn=0.;oxygen=1.;vf.y=max(vf.y,0.);}
    else if(worldZ<.10) vf.y=max(vf.y,0.);
    oxygen=mix(1.0,oxygen,edge);
    // Keep transported scalars together: the limiter reads one RGBA texel per
    // corner. Reaction is recomputed here, so it shares velocity's spare lane.
    outVF=vec4(clamp(vf.xyz,vec3(-1.0),vec3(1.0)),burn/max(delta,.0001));
    outChem=vec4(fuel,oxygen,temp,soot);
  }`;
  const rendering = () => `#version 300 es
  ${shared}
  ${room.surfaceGLSL}
  uniform sampler2D smokeLightTex;
  uniform float roomEnabled;
  uniform float viewZoom;
  uniform vec2 viewPan;
  layout(location=0) out vec4 outColor;
  vec3 aces(vec3 x){return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.0,1.0);}
  void main(){
    vec2 p=(uv-.5)/viewZoom+.5+viewPan/vec2(14.,7.875);
    if(roomEnabled<.5 && (any(lessThan(p,vec2(0)))||any(greaterThan(p,vec2(1))))){outColor=vec4(0,0,0,1);return;}
    vec3 light=vec3(0.0);
    float transmittance=1.0;
    vec3 ray=roomRay(uv),surfaceNormal=vec3(0);
    float surfaceDistance=1000.;
    vec3 surface=vec3(0);
    if(roomEnabled>.5){
      surfaceDistance=roomHit(cameraEye,ray,surfaceNormal);
      surface=roomSurface(cameraEye+ray*surfaceDistance,surfaceNormal,-ray);
    }
    // Sample every simulated depth layer along the camera ray. The volume has
    // actual parallax; no screen-space billboard or rendered fire plane is used.
    for(int i=0;i<${DEPTH};i++){
      float z=roomEnabled>.5?float(${DEPTH-1}-i):float(i);
      if(roomEnabled>.5){
        float worldDepth=fireMin.z+z/float(${DEPTH-1})*fireExtent.z;
        float distance=(worldDepth-cameraEye.z)/ray.z;
        if(distance<0. || distance>=surfaceDistance) continue;
        vec3 at=cameraEye+ray*distance;
        p=(at.xy+vec2(7.,1.05))/vec2(14.,7.875);
        if(any(lessThan(p,vec2(0)))||any(greaterThan(p,vec2(1)))) continue;
      }
      vec4 c=layer(chemTex,p,z);
      float temp=c.b, soot=c.a;
      if(temp<=0.0 && soot<=0.0) continue;
      float reaction=layer(vfTex,p,z).a;
      float sigma=clamp(sootExtinction(soot)+reaction*.025,0.0,24.0);
      vec3 emission=fireEmission(reaction,temp);
      float stepLength=fireExtent.z/float(${DEPTH})/(roomEnabled>.5?max(-ray.z,.1):1.);
      float opacity=1.0-exp(-sigma*stepLength);
      // Light is attenuated by the advected soot above this point. This gives
      // cold smoke volume and self-shadowing without a procedural overlay.
      vec3 scatter;
      if(roomEnabled>.5) scatter=smokeIrradiance(vec3(p,z/float(${DEPTH-1})));
      else {
        vec2 lightUV=(vec2(mod(z,8.0),floor(z/8.0))+clamp(p,vec2(.5/128.0,.5/72.0),vec2(1.0-.5/128.0,1.0-.5/72.0)))/vec2(8.0,4.0);
        float key=exp(-texture(smokeLightTex,lightUV).r);
        scatter=vec3(.08,.09,.12)+vec3(2.8,2.9,3.2)*key;
      }
      light+=transmittance*(emission+soot*.22*scatter)*opacity/max(sigma,.0001);
      transmittance*=1.0-opacity;
    }
    outColor=vec4(light+transmittance*surface,1.0);
  }`;
  const presentation = `#version 300 es
  precision highp float;
  in vec2 uv;
  uniform sampler2D projection;
  layout(location=0) out vec4 outColor;
  vec3 aces(vec3 x){return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.0,1.0);}
  void main(){
    vec2 stepSize=1.0/vec2(${RW}.0,${RH}.0);
    vec3 linear=texture(projection,uv).rgb;
    vec3 glow=(texture(projection,uv+vec2(stepSize.x*3.0,0.0)).rgb+
               texture(projection,uv-vec2(stepSize.x*3.0,0.0)).rgb+
               texture(projection,uv+vec2(0.0,stepSize.y*3.0)).rgb+
               texture(projection,uv-vec2(0.0,stepSize.y*3.0)).rgb)*.25;
    linear=(linear+max(glow-vec3(1.),vec3(0))*.012)*.60;
    float luminance=dot(linear,vec3(.2126,.7152,.0722));
    vec3 huePreserving=linear*aces(vec3(luminance)).x/max(luminance,.00001);
    vec3 mapped=mix(aces(linear),clamp(huePreserving,0.,1.),.45);
    mapped=mix(mapped*12.92,1.055*pow(mapped,vec3(1.0/2.4))-.055,step(vec3(.0031308),mapped));
    outColor=vec4(mapped,1.0);
  }`;

  function shader(type, source) {
    const s = gl.createShader(type); gl.shaderSource(s, source); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || 'Shader compile failed');
    return s;
  }
  function program(fragment) {
    const p = gl.createProgram();
    gl.attachShader(p, shader(gl.VERTEX_SHADER, vertex));
    gl.attachShader(p, shader(gl.FRAGMENT_SHADER, fragment));
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p) || 'Shader link failed');
    return p;
  }
  // Uniform locations are stable for a linked program. Avoid synchronously
  // looking up twenty locations on every simulation step.
  const locations = new WeakMap();
  function uniform(p, name) {
    let cache=locations.get(p);
    if (!cache) { cache=new Map(); locations.set(p,cache); }
    if (!cache.has(name)) cache.set(name,gl.getUniformLocation(p,name));
    return cache.get(name);
  }
  function texture(width, height, data, filter = gl.LINEAR, internal = gl.RGBA8, format = gl.RGBA, type = gl.UNSIGNED_BYTE) {
    const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, filter);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texImage2D(gl.TEXTURE_2D, 0, internal, width, height, 0, format, type, data);
    return t;
  }
  function target() {
    const filter = halfFloatLinear ? gl.LINEAR : gl.NEAREST;
    const vf = texture(AW, AH, null, filter, gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT);
    const chem = texture(AW, AH, null, filter, gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT);
    const fbo = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, vf, 0);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT1, gl.TEXTURE_2D, chem, 0);
    gl.drawBuffers([gl.COLOR_ATTACHMENT0, gl.COLOR_ATTACHMENT1]);
    if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) throw new Error('Floating point simulation framebuffer incomplete');
    return { vf, chem, fbo };
  }
  function projectionTarget() {
    const color = texture(RW, RH, null, gl.LINEAR, gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT);
    const fbo = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, color, 0);
    gl.drawBuffers([gl.COLOR_ATTACHMENT0]);
    if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) throw new Error('Volume projection framebuffer incomplete');
    return { color, fbo };
  }
  function bind(tex, unit, location) {
    gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, tex); gl.uniform1i(location, unit);
  }
  function reset() {
    stateRevision++;
    elapsed = 0; accumulator = 0;
    needsDraw = true;
    brush.active = false;
    brush.fromX = brush.x; brush.fromY = brush.y;
    pointer.vx = 0; pointer.vy = 0;
    if (!pressure || !targets) return;
    pressure.reset();
    for (const t of targets) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, t.fbo); gl.viewport(0, 0, AW, AH);
      gl.clearBufferfv(gl.COLOR, 0, new Float32Array([0, 0, 0, 0]));
      gl.clearBufferfv(gl.COLOR, 1, new Float32Array([0, 1, 0, 0]));
    }
    current = 0;
  }
  function runStep() {
    const from = targets[current], to = targets[1 - current];
    vorticity.update(from.vf,from.chem,brush,freeMode);
    const predictor = advection.step(from.vf, from.chem, pressure.getCorrection(), STEP);
    gl.useProgram(simProgram); gl.bindFramebuffer(gl.FRAMEBUFFER, to.fbo); gl.viewport(0, 0, AW, AH);
    bind(from.vf, 0, uniform(simProgram, 'vfTex'));
    bind(from.chem, 1, uniform(simProgram, 'chemTex'));
    bind(sourceTexture, 2, uniform(simProgram, 'sourceTex'));
    bind(noiseTexture, 3, uniform(simProgram, 'noiseTex'));
    bind(widthTexture, 4, uniform(simProgram, 'widthTex'));
    bind(pressure.getCorrection(), 5, uniform(simProgram, 'pressureCorrectionTex'));
    bind(predictor, 6, uniform(simProgram, 'mcPredictorTex'));
    bind(vorticity.texture, 7, uniform(simProgram, 'vortexTex'));
    gl.uniform3fv(uniform(simProgram, 'vortexOrigin'), vorticity.origin);
    gl.uniform3fv(uniform(simProgram, 'vortexSpan'), vorticity.span);
    gl.uniform1f(uniform(simProgram, 'clock'), elapsed);
    gl.uniform1f(uniform(simProgram, 'delta'), STEP);
    gl.uniform2f(uniform(simProgram, 'pointer'), pointer.x, pointer.y);
    const movingSource = !freeMode || pointer.down;
    gl.uniform2f(uniform(simProgram, 'pointerMotion'), movingSource ? pointer.vx : 0, movingSource ? pointer.vy : 0);
    // Holding a source must not continuously push gas radially away from it.
    gl.uniform1f(uniform(simProgram, 'pointerStrength'), !freeMode && pointer.active ? .32 : 0.0);
    gl.uniform2f(uniform(simProgram, 'brushFrom'), brush.fromX, brush.fromY);
    gl.uniform2f(uniform(simProgram, 'brushTo'), brush.x, brush.y);
    gl.uniform1f(uniform(simProgram, 'brushActive'), brush.active ? 1.0 : 0.0);
    gl.uniform1f(uniform(simProgram, 'sourceEnabled'), freeMode ? 0.0 : 1.0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    brush.fromX = brush.x; brush.fromY = brush.y;
    current = 1 - current;
    gl.activeTexture(gl.TEXTURE5); gl.bindTexture(gl.TEXTURE_2D, null);
    pressure.update(targets[current].vf);
    stateRevision++;
    pointer.vx *= .48; pointer.vy *= .48;
  }
  function draw() {
    // Camera changes do not change emission or soot. Reuse their illumination
    // while paused so inspecting the volume does not rebuild all shadow maps.
    if(roomEnabled && roomLightRevision!==stateRevision){
      room.update(targets[current].vf,targets[current].chem);roomLightRevision=stateRevision;
    } else if(!roomEnabled && smokeLightRevision!==stateRevision){
      smokeLight.update(targets[current].chem);smokeLightRevision=stateRevision;
    }
    gl.useProgram(renderProgram); gl.bindFramebuffer(gl.FRAMEBUFFER, projected.fbo);
    gl.viewport(0, 0, RW, RH);
    bind(targets[current].vf, 0, uniform(renderProgram, 'vfTex'));
    bind(targets[current].chem, 1, uniform(renderProgram, 'chemTex'));
    bind(smokeLight.texture, 8, uniform(renderProgram, 'smokeLightTex'));
    room.bind(renderProgram,uniform);
    gl.uniform1f(uniform(renderProgram,'roomEnabled'),roomEnabled?1:0);
    gl.uniform1f(uniform(renderProgram,'cameraTan'),lensTan());
    gl.uniform1f(uniform(renderProgram,'viewZoom'),viewZoom);
    gl.uniform2f(uniform(renderProgram,'viewPan'),panX,panY);
    const viewCamera=camera();
    for(const name of ['eye','forward','right','up']) {
      gl.uniform3fv(uniform(renderProgram,'camera'+name[0].toUpperCase()+name.slice(1)),viewCamera[name]);
    }
    gl.uniform1f(uniform(renderProgram, 'clock'), elapsed);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    gl.useProgram(presentProgram); gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, canvas.width, canvas.height);
    bind(projected.color, 0, uniform(presentProgram, 'projection'));
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
  const pointer = { x: .5, y: .5, vx: 0, vy: 0, active: false, down: false, id: null, last: 0 };
  const brush = { x: .5, y: .5, fromX: .5, fromY: .5, active: false };
  let freeMode = false;
  // Rendering and pointer unprojection share the same lens and camera. Keep
  // this unclamped for cursor-anchored zoom and pan; clamp only fuel placement.
  function scenePoint(e) {
    const r = canvas.getBoundingClientRect();
    let x = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
    let y = Math.max(0, Math.min(1, 1 - (e.clientY - r.top) / r.height));
    if(roomEnabled) {
      const c=camera();
      const ray=c.forward.map((v,i)=>v+(x*2-1)*(16/9)*lensTan()*c.right[i]+(y*2-1)*lensTan()*c.up[i]);
      const distance=-c.eye[2]/ray[2];
      x=(c.eye[0]+ray[0]*distance+7)/14;
      y=(c.eye[1]+ray[1]*distance+1.05)/7.875;
    } else {x=(x-.5)/viewZoom+.5+panX/14;y=(y-.5)/viewZoom+.5+panY/7.875;}
    return {x,y};
  }
  function point(e) {
    const at=scenePoint(e);
    const x=Math.max(.02,Math.min(.98,at.x)),y=Math.max(1.13/7.875,Math.min(.96,at.y));
    const now = performance.now();
    const dt = Math.max(.01, (now - pointer.last) / 1000);
    pointer.vx = pointer.last ? Math.max(-2, Math.min(2, (x - pointer.x) / dt)) : 0;
    pointer.vy = pointer.last ? Math.max(-2, Math.min(2, (y - pointer.y) / dt)) : 0;
    pointer.x = x; pointer.y = y; pointer.last = now; pointer.active = true;
  }
  view.addEventListener('pointermove', e => {
    if(panGesture){
      if(e.pointerId!==panGesture.id)return;
      const at=scenePoint(e);
      panX+=(panGesture.anchor.x-at.x)*14;panY+=(panGesture.anchor.y-at.y)*7.875;
      updateView();return;
    }
    if(panTool||e.shiftKey||e.buttons===2){pointer.active=false;return;}
    if (pointer.down && e.pointerId !== pointer.id) return;
    point(e);
    if (freeMode && pointer.down) { brush.x = pointer.x; brush.y = pointer.y; }
  });
  view.addEventListener('pointerdown', e => {
    if(pointer.down||panGesture)return;
    if(panTool||e.shiftKey||e.button===2){
      e.preventDefault();view.focus({preventScroll:true});
      pointer.active=false;pointer.last=0;
      panGesture={id:e.pointerId,anchor:scenePoint(e)};
      view.setPointerCapture(e.pointerId);view.classList.add('is-panning');return;
    }
    if (pointer.down || (e.pointerType === 'mouse' && e.button !== 0)) return;
    e.preventDefault();
    view.focus({preventScroll:true});
    pointer.last=0;
    point(e);
    pointer.down = true; pointer.id = e.pointerId;
    view.setPointerCapture(e.pointerId);
    if (!freeMode) {
      freeMode = true;
      reset();
      modeButton.hidden = false;
      restartButton.textContent = 'Clear fire';
    }
    brush.x = brush.fromX = pointer.x;
    brush.y = brush.fromY = pointer.y;
    brush.active = true;
    focusButton.disabled=false;
    extinguishButton.hidden = false;
    extinguishButton.disabled = false;
    help.textContent = 'Drag to move the source. Release to leave it burning. Stop fuel to watch the flame die and smoke drift; click to reignite.';
    canvas.setAttribute('aria-label', 'Interactive live GPU fire. Drag the burning source to move it.');
    message.textContent = 'Free fire · drag to move the source';
    if (paused) { paused = false; document.querySelector('#pause').textContent = 'Pause'; }
    captureAt = 0;
  });
  view.addEventListener('pointerup', e => {
    if(panGesture?.id===e.pointerId){endPan();return;}
    if (e.pointerId !== pointer.id) return;
    point(e);
    if (freeMode) { brush.x = pointer.x; brush.y = pointer.y; }
    pointer.down = false; pointer.id = null;
  });
  view.addEventListener('pointercancel', e => {
    if(panGesture?.id===e.pointerId){endPan();return;}
    if (e.pointerId !== pointer.id) return;
    pointer.down = false; pointer.id = null; pointer.active = false;
  });
  view.addEventListener('lostpointercapture', () => { endPan();pointer.down = false; pointer.id = null; });
  window.addEventListener('blur', () => { endPan();pointer.down = false; pointer.id = null; pointer.active = false; });
  view.addEventListener('pointerleave', () => { if (!pointer.down) pointer.active = false; });
  let captureAt = Number(new URL(location.href).searchParams.get('capture')) || 0;
  let paused = false, elapsed = 0, accumulator = 0, lastFrame = performance.now();
  let observedSteps = 0, observedDraws = 0, observedStart = lastFrame, needsDraw = true;
  function endPan(){panGesture=null;view.classList.remove('is-panning');pointer.last=0;}
  function updateView(){
    panX=Math.max(-6.5,Math.min(6.5,panX));panY=Math.max(-2.8,Math.min(3.5,panY));
    zoomControl.value=Math.round(viewZoom*100);
    document.querySelector('#zoom-value').textContent=`${Math.round(viewZoom*100)}%`;
    orbitControl.value=viewAngle;document.querySelector('#angle-value').textContent=`${viewAngle}°`;
    document.querySelector('#zoom-out').disabled=viewZoom<=.7;
    document.querySelector('#zoom-in').disabled=viewZoom>=3;
    pointer.active=false;pointer.last=0;needsDraw=true;
  }
  function setZoom(value,anchorEvent){
    if(pointer.down||panGesture)return;
    const before=anchorEvent?scenePoint(anchorEvent):null;
    viewZoom=Math.max(.7,Math.min(3,Math.round(value*100)/100));
    if(before){const after=scenePoint(anchorEvent);panX+=(before.x-after.x)*14;panY+=(before.y-after.y)*7.875;}
    updateView();
  }
  function setTool(pan){
    endPan();panTool=pan;pointer.active=false;
    document.querySelector('#fire-tool').setAttribute('aria-pressed',String(!pan));
    document.querySelector('#pan-tool').setAttribute('aria-pressed',String(pan));
    view.dataset.tool=pan?'pan':'fire';
  }
  view.addEventListener('contextmenu',e=>e.preventDefault());
  view.addEventListener('wheel',e=>{
    e.preventDefault();
    const delta=e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?view.clientHeight:1);
    setZoom(viewZoom*Math.exp(-Math.max(-250,Math.min(250,delta))*.0015),e);
  },{passive:false});
  document.querySelector('#fire-tool').onclick=()=>setTool(false);
  document.querySelector('#pan-tool').onclick=()=>setTool(true);
  zoomControl.oninput=()=>setZoom(Number(zoomControl.value)/100);
  document.querySelector('#zoom-in').onclick=()=>setZoom(viewZoom+.25);
  document.querySelector('#zoom-out').onclick=()=>setZoom(viewZoom-.25);
  document.querySelector('#reset-view').onclick=()=>{endPan();viewZoom=1;panX=panY=0;viewAngle=16;updateView();};
  focusButton.onclick=()=>{
    if(!freeMode)return;
    panX=-7+brush.x*14;panY=-1.05+brush.y*7.875+1.1-2.4;viewZoom=2.25;updateView();
  };
  fullscreenButton.onclick=async()=>{
    try{if(document.fullscreenElement)await document.exitFullscreen();else await document.querySelector('main').requestFullscreen();}
    catch{message.textContent='Fullscreen is unavailable in this browser. Zoom and Move view are still available.';}
  };
  document.addEventListener('fullscreenchange',()=>{fullscreenButton.textContent=document.fullscreenElement?'Exit fullscreen':'Fullscreen';needsDraw=true;});
  updateView();
  roomToggle.onchange=()=>{
    roomEnabled=roomToggle.checked;orbitControl.disabled=!roomEnabled;needsDraw=true;
    sceneLabel.textContent=roomEnabled?'Fire-lit room · etched stone':'Fire and smoke · black background';
  };
  orbitControl.oninput=()=>{viewAngle=Number(orbitControl.value);updateView();};
  document.querySelector('#pause').onclick = () => { paused = !paused; document.querySelector('#pause').textContent = paused ? 'Resume' : 'Pause'; };
  extinguishButton.onclick = () => {
    brush.active = false;
    pointer.down = false; pointer.id = null;
    extinguishButton.disabled = true;
    message.textContent = 'Fuel stopped · smoke continues to drift';
    paused = false; captureAt = 0;
    document.querySelector('#pause').textContent = 'Pause';
  };
  restartButton.onclick = () => {
    paused = false;
    document.querySelector('#pause').textContent = 'Pause';
    lastFrame = performance.now();
    reset();
    focusButton.disabled=true;
    extinguishButton.disabled = true;
    if (freeMode) {
      message.textContent = 'Free fire · click to ignite';
      help.textContent = 'Click anywhere in the canvas to ignite a new flame, then drag to move its source.';
      canvas.setAttribute('aria-label', 'Interactive live GPU fire. Click to ignite a new flame.');
    }
  };
  modeButton.onclick = () => {
    setTool(false);focusButton.disabled=true;
    freeMode = false;
    pointer.down = false; pointer.id = null;
    modeButton.hidden = true;
    extinguishButton.hidden = true;
    restartButton.textContent = 'Restart';
    help.textContent = 'Click the canvas to create your own fire; drag to move its source. The live sigil will give way to your flame.';
    message.textContent = 'Live GPU simulation · click to create fire';
    canvas.setAttribute('aria-label', 'Live GPU-simulated volumetric fire forming the Cybrdelic 02 mark. Click to create your own fire.');
    paused = false;
    document.querySelector('#pause').textContent = 'Pause';
    lastFrame = performance.now();
    reset();
  };
  window.addEventListener('keydown', e => {
    if(e.ctrlKey||e.metaKey||e.altKey||e.repeat)return;
    if(e.target instanceof HTMLElement && (e.target.isContentEditable||e.target.matches('input,select,textarea')))return;
    const key=e.key.toLowerCase();
    if(e.code==='Space' && !(e.target instanceof HTMLElement && e.target.matches('button,a'))){e.preventDefault();document.querySelector('#pause').click();}
    else if(key==='r')restartButton.click();
    else if(key==='0')document.querySelector('#reset-view').click();
    else if(key==='+'||key==='='){e.preventDefault();setZoom(viewZoom+.25);}
    else if(key==='-'||key==='_'){e.preventDefault();setZoom(viewZoom-.25);}
    else if(key==='f')fullscreenButton.click();
    else if(key==='escape'){setTool(false);pointer.down=false;pointer.id=null;}
  });
  let simProgram, renderProgram, presentProgram, targets, projected, sourceTexture, widthTexture, noiseTexture, pressure, advection, vorticity, smokeLight, room, current = 0;
  function frame(now) {
    const delta = Math.min(.08, (now - lastFrame) / 1000); lastFrame = now;
    let steps = 0;
    if (!paused) {
      accumulator += delta;
      while (accumulator >= STEP && steps < 2) {
        elapsed += STEP;
        if (!freeMode && elapsed > DURATION) { reset(); accumulator = STEP; }
        runStep(); accumulator -= STEP; steps++;
        observedSteps++;
        if (captureAt > 0 && elapsed >= captureAt) { paused = true; document.querySelector('#pause').textContent = 'Resume'; break; }
      }
      if (steps === 2 && accumulator > STEP * 2) accumulator = STEP;
    }
    if (steps > 0 || needsDraw) { draw(); observedDraws++; needsDraw = false; }
    if (now - observedStart > 800) {
      const span = (now - observedStart) / 1000;
      const simRate = Math.round(observedSteps / span);
      const renderRate = Math.round(observedDraws / span);
      metrics.textContent = `${paused ? 'paused' : `${simRate} sim steps/s · ${renderRate} rendered fps`} · ${elapsed.toFixed(1)} s · ${NX} × ${NZ} × ${DEPTH} cells`;
      observedSteps = 0; observedDraws = 0; observedStart = now;
    }
    requestAnimationFrame(frame);
  }
  async function start() {
    try {
      if (AW > gl.getParameter(gl.MAX_TEXTURE_SIZE) || AH > gl.getParameter(gl.MAX_TEXTURE_SIZE)) {
        throw new Error('This GPU cannot fit the live fire volume');
      }
      pressure = CoarsePressure.setup(gl, { nx: NX, nz: NZ, depth: DEPTH, tilesX: TILES_X, tilesY: TILES_Y, worldY: 1.8, coarseDepth: 8, iterations: 18 });
      advection = MacCormackAdvection.setup(gl, {
        nx: NX, nz: NZ, depth: DEPTH, tilesX: TILES_X, tilesY: TILES_Y,
        pressureSamplingGLSL: pressure.samplingGLSL
      });
      vorticity = FireVorticity.setup(gl, {nx: NX, nz: NZ, depth: DEPTH, tilesX: TILES_X});
      smokeLight = SmokeLight.setup(gl, {nx: NX, nz: NZ, depth: DEPTH, tilesX: TILES_X});
      room = FireRoom.setup(gl, {nx: NX, nz: NZ, depth: DEPTH, tilesX: TILES_X});
      simProgram = program(simulation()); renderProgram = program(rendering()); presentProgram = program(presentation);
      gl.bindVertexArray(gl.createVertexArray());
      targets = [target(), target()]; projected = projectionTarget();
      // Periodic smooth noise is sampled by the source and velocity fields.
      // It is a static turbulence basis, not prerecorded motion.
      const n = new Uint8Array(256 * 256 * 4);
      function hash(x, y, channel) {
        let v = (x * 374761393 + y * 668265263 + channel * 1442695041) >>> 0;
        v = Math.imul(v ^ (v >>> 13), 1274126177) >>> 0;
        return ((v ^ (v >>> 16)) >>> 0) / 4294967295;
      }
      function valueNoise(x, y, period, channel) {
        const xx = x * period / 256, yy = y * period / 256;
        const ix = Math.floor(xx), iy = Math.floor(yy);
        const fx = xx - ix, fy = yy - iy;
        const sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy);
        const a = hash(ix & (period - 1), iy & (period - 1), channel);
        const b = hash((ix + 1) & (period - 1), iy & (period - 1), channel);
        const c = hash(ix & (period - 1), (iy + 1) & (period - 1), channel);
        const d = hash((ix + 1) & (period - 1), (iy + 1) & (period - 1), channel);
        return (a + (b - a) * sx) * (1 - sy) + (c + (d - c) * sx) * sy;
      }
      for (let y = 0; y < 256; y++) for (let x = 0; x < 256; x++) for (let c = 0; c < 4; c++) {
        const v = .50 * valueNoise(x, y, 8, c) + .28 * valueNoise(x, y, 16, c)
                + .15 * valueNoise(x, y, 32, c) + .07 * valueNoise(x, y, 64, c);
        n[(y * 256 + x) * 4 + c] = Math.max(0, Math.min(255, Math.round(v * 255)));
      }
      noiseTexture = texture(256, 256, n);
      gl.bindTexture(gl.TEXTURE_2D, noiseTexture);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
      const [sourceBytes, widthBytes] = await Promise.all([
        fetch('source/source-native.rgba8.bin').then(r => { if (!r.ok) throw new Error('Source field missing'); return r.arrayBuffer(); }),
        fetch('source/halfwidth-native.r8.bin').then(r => { if (!r.ok) throw new Error('Source thickness missing'); return r.arrayBuffer(); })
      ]);
      if (sourceBytes.byteLength !== SOURCE_NX * SOURCE_NZ * 4 || widthBytes.byteLength !== SOURCE_NX * SOURCE_NZ) throw new Error('Source field size mismatch');
      const sourcePixels = new Uint8Array(sourceBytes);
      sourceTexture = texture(SOURCE_NX, SOURCE_NZ, sourcePixels);
      widthTexture = texture(SOURCE_NX, SOURCE_NZ, new Uint8Array(widthBytes), gl.LINEAR, gl.R8, gl.RED, gl.UNSIGNED_BYTE);
      canvas.width = 1920; canvas.height = 1080;
      const pendingBrush = brush.active;
      reset();
      if (freeMode && pendingBrush) brush.active = true;
      message.textContent = freeMode
        ? pendingBrush ? 'Free fire · drag to move the source' : 'Free fire · click to ignite'
        : 'Live GPU simulation · click to create fire';
      requestAnimationFrame(frame);
    } catch (err) {
      message.textContent = `Fire runtime failed: ${err.message}`;
      console.error(err);
    }
  }
  canvas.addEventListener('webglcontextlost', e => { e.preventDefault(); message.textContent = 'GPU context lost'; });
  canvas.addEventListener('webglcontextrestored', () => location.reload());
  start();
})();
