/* Analytic fuel emitters. Shapes only inject gas; they never mask the rendered
 * flame. Burst age is simulation time, so pausing also pauses the explosion. */
window.createFireEmitters = (maxPowerKind=6,castCapacity=4) => `
  uniform int emitterKind;
  
  uniform float burstAge;
  uniform vec3 fuelProfile; // feed, soot yield, jet speed
  uniform float sourceScale;
  uniform float sourceLift;
  uniform int sourceEffectKind;
  #ifndef FIRE_OBJECT_TEXTURE
#define FIRE_OBJECT_TEXTURE
uniform highp sampler3D objectTex;
#endif
  uniform float objectVariation;
  uniform float burstDuration;
  uniform vec4 powerCastOriginAge[${castCapacity}];
  uniform vec4 powerCastDirectionStrength[${castCapacity}];
  uniform vec4 powerCastKindScale[${castCapacity}];
  uniform vec4 powerCastTargetCharge[${castCapacity}];
  float sourceSegment(vec2 p,vec2 a,vec2 b){
    vec2 d=b-a;return length(p-a-d*clamp(dot(p-a,d)/max(dot(d,d),.00001),0.,1.));
  }
  float sourceGlyph(vec2 q,int kind){
    float d=1000.;
    if(kind==10){
      for(int i=0;i<3;i++){
        float a=1.570796+float(i)*2.094395;
        float b=a+2.094395;
        d=min(d,sourceSegment(q,.73*vec2(cos(a),sin(a)),.73*vec2(cos(b),sin(b))));
      }
      return min(d,abs(length(q)-.92));
    }
    if(kind==11){
      for(int i=0;i<5;i++){
        float a=1.570796+float(i)*1.256637;
        float b=a+2.513274;
        d=min(d,sourceSegment(q,.78*vec2(cos(a),sin(a)),.78*vec2(cos(b),sin(b))));
      }
      return min(d,abs(length(q)-.92));
    }
    d=sourceSegment(q,vec2(0,-.8),vec2(0,.8));
    d=min(d,sourceSegment(q,vec2(0,.05),vec2(-.62,.65)));
    d=min(d,sourceSegment(q,vec2(0,.05),vec2(.62,.65)));
    d=min(d,sourceSegment(q,vec2(0,-.25),vec2(-.48,-.65)));
    d=min(d,sourceSegment(q,vec2(0,-.25),vec2(.48,-.65)));
    return min(d,abs(abs(q.x)+abs(q.y+.2)-.32)*.7071068);
  }
  void emitter(vec2 local,float depth,out float density,out vec3 jet){
    density=0.;jet=vec3(0);
    #if FIRE_HAS_POWERS
    if(emitterKind>=22&&emitterKind<=${21+maxPowerKind}){
      // Both engines sample the same world-space release and trajectory. These
      // sources enter live gas; the display shader never draws a power shape.
      vec3 world=vec3(simMin.xy+brushTo*simExtent.xy+local,depth);
      for(int actor=0;actor<${castCapacity};actor++){
        vec4 kindScale=powerCastKindScale[actor];if(kindScale.z<.5)continue;
        vec4 originAge=powerCastOriginAge[actor],directionStrength=powerCastDirectionStrength[actor],targetCharge=powerCastTargetCharge[actor];
        vec4 release=powerCastSource(kindScale.x,world,originAge.xyz,kindScale.y,sourceSampleAge(originAge.w,kindScale.z,delta),sourceClock(clock-delta,kindScale.w,delta),directionStrength.xyz,directionStrength.w,targetCharge.xyz,targetCharge.w);
        density+=release.w;jet+=release.xyz*release.w;
      }
      jet/=max(density,.00001);return;
    }
    #endif
    if(emitterKind==6){
      // One irregular finite charge. Expansion is solved from combustion in
      // the pressure pass; there are no moving spherical emission pockets.
      if(burstAge<0. || burstAge>burstDuration || any(greaterThan(abs(local),vec2(.95)*sourceScale)))return;
      vec3 q=vec3(local,depth)/sourceScale;
      vec2 seed=vec2(clock-burstAge)*vec2(.137,.231);
      vec3 n=texture(noiseTex,local*.25+depth*vec2(.19,-.11)+seed).rgb;
      vec3 m=texture(noiseTex,local*.7+depth*vec2(-.31,.23)+seed+vec2(.13,.61)).rgb;
      float irregular=.65+1.4*(n.r-.5)+.35*(m.g-.5);
      float radius=length(q/vec3(1.,.9,.8));
      float body=1.-smoothstep(irregular-.12,irregular+.06,radius);
      density=body*mix(.12,1.4,smoothstep(.22,.72,n.g))*4.*(1.-smoothstep(burstDuration*.4,burstDuration,burstAge));
      jet=(normalize(q+vec3(.0001))*mix(3.,18.,smoothstep(.28,.72,m.r))+cross(vec3(.3,.8,.5),q)*8.+(n-m)*vec3(5.,5.,2.)+vec3(0,2.,0))*fuelProfile.z;
      return;
    }
    if(emitterKind>=16&&emitterKind<=20){
      // Timber is supplied by its persistent projected inventory. Retain this
      // separate coating emitter only for the car and mannequin presets.
      if(emitterKind==16||emitterKind==17||emitterKind==20)return;
      vec3 q=vec3(local,depth)/sourceScale;
      if(any(greaterThan(abs(q),vec3(1.5))))return;
      vec4 material=texture(objectTex,(q+1.5)/3.);
      if(material.y<=0.||material.x<-.025||material.x>.16)return;
      vec3 starter=emitterKind==20?vec3(0,objectVariation>2.5?.95:-1.10,0)
        :emitterKind==17?vec3(-.45,-.85,.15)
        :emitterKind==18?vec3(-.75,-.35,.2):vec3(0,-.65,0);
      float seed=objectVariation>.5&&objectVariation<1.5?1.:exp(-dot(q-starter,q-starter)*12.);
      if(objectVariation>1.5&&objectVariation<2.5)seed*=.25;
      seed*=1.-smoothstep(1.2,2.8,burstAge);
      vec3 at=vec3(brushTo+local/simExtent.xy,(depth-simMin.z)/simExtent.z);
      float heating=field(chemTex,at).b;
      float release=seed+smoothstep(objectVariation>1.5&&objectVariation<2.5?.55:.28,.9,heating);
      float coatingFeed=exp(-max(burstAge-2.,0.)*.07);
      density=exp(-pow((material.x-.04)/.065,2.))*material.y*release*coatingFeed;
      jet=vec3(q.x*.32,.65+material.z*.35,q.z*.32)*fuelProfile.z;
      return;
    }
    // Conservative support bounds avoid evaluating jets in millions of empty
    // cells. Bounds include every point inside the r² < 12 injection cutoff.
    vec2 bounds=emitterKind==1?vec2(3.30,.66)*sourceScale:emitterKind==2?vec2(.70,.42)
      :emitterKind==3?vec2(1.86):emitterKind==4?vec2(1.08)
      :emitterKind==5?vec2(3.60,.53)*sourceScale:emitterKind==6?vec2(3.76,3.18)
      :emitterKind==15?vec2(1.55)*sourceScale:emitterKind==21?vec2(.85)*sourceScale
      :vec2(1.7)*sourceScale;
    if(any(greaterThan(abs(local),bounds)))return;
    float shear=4.8*sin(depth*19.+clock*13.)*cos((local.x+local.y)*12.-clock*11.);
    float center=.16*sin(clock*7.3)+local.x*.48*sin(clock*9.1);
    vec2 inlet=local/sourceScale;
    float r2=dot(inlet/vec2(.42,.18),inlet/vec2(.42,.18))+pow((depth-center)/(.15*sourceScale),2.);
    jet=vec3(shear*.35,2.8+shear*.30,sin(local.x*23.+local.y*19.+clock*13.)*1.1);
    float sourceDuty=1.;
    if(emitterKind==0&&sourceEffectKind==0){ // Broad, slow source for a sooty plume.
      float x=local.x/sourceScale,y=local.y/sourceScale,z=depth/sourceScale;
      r2=pow(x/.62,2.)+pow((y-.04)/.22,2.)+pow(z/.44,2.);
      float drift=texture(noiseTex,vec2(x*.24+z*.12+clock*.035,y*.22-clock*.025)).r;
      jet=vec3((drift-.5)*1.10,.42+(drift-.5)*.18,(sin(z*3.+clock*.6)-.5)*.72);
    } else if(emitterKind==1){ // Three resolved tongues above the crossed logs.
      vec2 bed=local/sourceScale;
      // A connected, broad fuel bed feeds three overlapping flame tongues.
      // The old hard pocket selection pinched the source at each boundary;
      // advection then stretched those pinches into long, parallel streams.
      float x=bed.x,y=bed.y,z=depth/sourceScale;
      float roots=pow(x/.78,2.)+pow((y-.035)/.19,2.)+pow(z/.39,2.);
      float left=pow((x+.47)/.39,2.)+pow((y-.30)/.43,2.)+pow((z+.08)/.34,2.);
      float center=pow(x/.39,2.)+pow((y-.34)/.46,2.)+pow(z/.34,2.);
      float right=pow((x-.47)/.39,2.)+pow((y-.30)/.43,2.)+pow((z-.08)/.34,2.);
      float tongues=min(left,min(center,right));
      r2=mix(roots,tongues,smoothstep(.08,.60,y));
      jet=vec3(shear*.25,.92*sourceLift+shear*.08,
        sin(local.x*8.+clock*5.)*.30);
    } else if(emitterKind==2){ // A narrow, fast torch jet.
      // Gas exits a thin opening instead of a spherical glowing reservoir.
      r2=pow(local.x/.16,2.)+pow((local.y-.06)/.045,2.)+pow(depth/.15,2.);
      vec2 eddy=texture(noiseTex,vec2(local.x*1.7+depth*.8+clock*.13,local.y*.8-clock*.22)).rg;
      float speed=fuelProfile.y<.5?5.8:2.8;
      jet=vec3((eddy.r-.5)*9.,speed*(.7+.6*eddy.g),(eddy.g-.5)*4.);
    } else if(emitterKind==3){ // Horizontal ring with a finite vertical fuel layer.
      r2=pow((length(vec2(local.x,depth))-.65*sourceScale)/(.12*sourceScale),2.)+pow(local.y/(.10*sourceScale),2.);
      vec2 radial=normalize(local+vec2(.0001));
      jet=vec3(-radial.y*1.8+radial.x*.55+shear*.08,radial.x*1.8+radial.y*.55,sin(clock*9.+local.x*8.)*.4);
    } else if(emitterKind==4){ // Spherical shell, not a disk facing the camera.
      vec3 q=vec3(local,depth);
      float surface=.51+.045*sin(q.x*12.+clock*6.)*sin(q.y*10.-q.z*9.-clock*5.);
      r2=pow((length(q)-surface)/.08,2.);
      jet=cross(vec3(.8,.5,1.2),q)*2.+q*.25+vec3(shear*.25,0,0);
    } else if(emitterKind==5){ // Broad line of fuel, forming a fire wall.
      r2=pow(max(abs(local.x)-3.0*sourceScale,0.)/.17,2.)+pow(local.y/.15,2.)+pow((depth-.12*sin(local.x*4.+clock*3.))/.20,2.);
      jet=vec3(shear*.12,5.5+sin(local.x*5.+clock*4.)*1.3,sin(local.x*7.+clock*11.)*.6);
    } else if(emitterKind==7){ // Cube shell.
      vec3 q=vec3(local,depth)/sourceScale;
      r2=pow((max(max(abs(q.x),abs(q.y)),abs(q.z))-.60)/.055,2.);
      jet=vec3(-q.z*1.8,1.1+q.y*.6,q.x*1.8);
    } else if(emitterKind==8){ // Vertical helix.
      vec3 q=vec3(local,depth)/sourceScale;
      float angle=q.y*7.853982+clock*.45;
      r2=pow((length(q.xz-.5*vec2(cos(angle),sin(angle))))/.075,2.)+pow(max(abs(q.y)-.8,0.)/.06,2.);
      jet=vec3(-sin(angle)*1.8,1.6,cos(angle)*1.8);
    } else if(emitterKind==9||emitterKind==14){ // Twin and colliding nozzles.
      vec3 q=vec3(abs(local.x)/sourceScale-(emitterKind==14?.65:.48),local.y/sourceScale,depth/sourceScale);
      r2=dot(q/vec3(.12,.11,.12),q/vec3(.12,.11,.12));
      jet=emitterKind==14?vec3(-sign(local.x)*3.4,2.,0.):vec3(sign(local.x)*.45,4.2,shear*.12);
    } else if(emitterKind==10||emitterKind==11||emitterKind==12){ // Thin sigil strokes.
      vec3 q=vec3(local,depth)/sourceScale;
      float stroke=sourceGlyph(q.xy,emitterKind);
      r2=pow(stroke/.045,2.)+pow(q.z/.075,2.);
      jet=vec3(shear*.08,.65,sin(q.x*9.+clock*4.)*.2);
    } else if(emitterKind==13){ // Upright halo.
      vec3 q=vec3(local,depth)/sourceScale;
      r2=pow((length(q.xy)-.72)/.065,2.)+pow(q.z/.10,2.);
      jet=vec3(-q.y*.9,q.x*.9+.5,shear*.06);
    } else if(emitterKind==15){ // Broad connected fuel bed.
      vec3 q=vec3(local,depth)/sourceScale;
      r2=pow(max(abs(q.x)-.7,0.)/.12,2.)+pow(q.y/.08,2.)+pow(max(abs(q.z)-.7,0.)/.12,2.);
      jet=vec3(shear*.08,1.4,sin(q.x*6.+clock*3.)*.3);
    } else if(emitterKind==21){ // Directional jet; pulses detach in the flow.
      float sweep=sourceEffectKind==20?sin(clock*1.8)*.7:0.;
      vec3 direction=normalize(vec3(cos(sweep),.24+.12*sin(clock*2.1),sin(sweep)));
      vec3 q=vec3(local,depth)/sourceScale;
      float axial=dot(q,direction),radial=length(q-direction*axial);
      r2=pow(radial/.14,2.)+pow(axial/.20,2.);
      float pulse=sourceEffectKind==21?1.-smoothstep(.22,.30,fract(clock/.82)):1.;
      if(pulse<.01)return;
      jet=direction*(sourceEffectKind==21?8.:5.5)+vec3(shear*.06,0,sin(clock*11.)*.3);
    }
    if(r2>12.)return;
    float feed=.62+.38*sin(local.x*18.+depth*23.+clock*11.)*sin(local.x*9.-depth*17.-clock*7.3);
    if(emitterKind==0&&sourceEffectKind==0){
      float plumeFeed=texture(noiseTex,local*.12+depth*vec2(.08,-.06)+clock*vec2(.025,-.018)).b;
      feed=mix(.90,1.0,smoothstep(.08,.92,plumeFeed));
    } else if(emitterKind==1||emitterKind==2||emitterKind==5){
      float variation=texture(noiseTex,local*vec2(.58,.86)+depth*vec2(.36,-.24)+clock*vec2(.10,-.14)).b;
      // Keep coherent fuel coverage; high contrast holes become frozen source
      // masks that advection stretches into parallel filaments.
      feed=mix(.54,1.02,smoothstep(.12,.88,variation));
    }
    density=exp(-1.5*r2)*feed*sourceDuty;
    if(emitterKind==1)density*=.85;
    if(emitterKind==2)density*=4.4;
    if(emitterKind==3)density*=.65;
    if(emitterKind==4)density*=.30*feed;
    jet*=fuelProfile.z;
  }
`;
window.FireEmitters=window.createFireEmitters();
