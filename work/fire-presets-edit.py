from pathlib import Path
p=Path('outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live')
f=p/'fire.js'
s=f.read_text(encoding='utf-8')
s=s.replace('  ${advection.correctionGLSL}', '  ${window.FireEmitters}\n  ${advection.correctionGLSL}')
a=s.index('    // The offline emitter feeds')
b=s.index('    jet.xy+=clamp(pointerMotion',a)
s=s[:a]+'''    float brush; vec3 jet;
    emitter(local,worldY,brush,jet);
    if(brush>.000001) {
    float gasFeed=brush*(1.0-exp(-1.8*delta))*fuelProfile.x;
    float nozzle=clamp(brush*delta*20.0*(.72+.28*sin(clock*47.0))*fuelProfile.x,0.0,1.0);
    fuel=mix(fuel,.22,gasFeed);
    oxygen=mix(oxygen,.80,gasFeed);
    temp=mix(temp,.80,gasFeed);
    fuel=mix(fuel,emitterKind==6?1.6:.95,nozzle);
    oxygen*=1.0-nozzle*.85;
    temp=mix(temp,emitterKind==6?1.9:.85,nozzle);
    jet/=vec3(14.,7.875,1.8);
'''+s[b:]
s=s.replace('float sootYield=mix(.45,1.55,1.0-oxygen);','float sootYield=mix(.45,1.55,1.0-oxygen)*fuelProfile.y;')
s=s.replace('vec3 emission=fireEmission(reaction,temp);','vec3 emission=fireEmission(reaction,temp)+sootEmission(soot,temp);')
s=s.replace('light+=transmittance*(emission+soot*.22*scatter)*opacity/max(sigma,.0001);', '''// A modest scattering albedo gives soot illuminated rims while its
      // extinction still silhouettes the dense core against the room.
      float scattering=roomEnabled>.5?sootExtinction(soot)*.14:soot*.22;
      light+=transmittance*(emission+scattering*scatter)*opacity/max(sigma,.0001);''')
s=s.replace('vorticity.update(from.vf,from.chem,brush,freeMode);','vorticity.update(from.vf,from.chem,brush,freeMode && emitterKind<3);')
s=s.replace("    gl.uniform1f(uniform(simProgram, 'clock'), elapsed);", """    gl.uniform1i(uniform(simProgram,'emitterKind'),emitterKind);
    gl.uniform1f(uniform(simProgram,'burstAge'),elapsed-burstStart);
    gl.uniform3fv(uniform(simProgram,'fuelProfile'),fuelProfiles[fuelControl.value]);
    gl.uniform1f(uniform(simProgram, 'clock'), elapsed);""")
s=s.replace('  let freeMode = false;', '''  let freeMode = false;
  let emitterKind=0, burstStart=-100;
  const presetControl=document.querySelector('#preset');
  const fuelControl=document.querySelector('#fuel');
  const burstButton=document.querySelector('#burst');
  const fuelProfiles={wood:[1,1,1],gas:[.85,.22,1.25],oil:[1.15,2.4,.85]};
  const presets={sigil:0,free:0,campfire:1,torch:2,ring:3,sphere:4,wall:5,explosion:6};
  function describeSource(){
    const name=presetControl.selectedOptions[0].textContent;
    message.textContent=emitterKind===6?'Explosion · click to burst again':`${name} · drag to move the source`;
    help.textContent=emitterKind===6
      ? 'Click to detonate at the cursor, or use Trigger burst. Each burst adds to the live smoke. Pause to inspect the expansion.'
      : 'Click or drag to place the source. Release to keep burning. Stop fuel lets the flame die while its smoke drifts.';
    canvas.setAttribute('aria-label',`${name}. ${help.textContent}`);
  }
  function ignite(){
    brush.active=true;burstStart=elapsed;
    focusButton.disabled=false;extinguishButton.disabled=false;
    paused=false;captureAt=0;lastFrame=performance.now();
    document.querySelector('#pause').textContent='Pause';
    describeSource();
  }
  function selectPreset(key){
    presetControl.value=key;emitterKind=presets[key];freeMode=key!=='sigil';
    pointer.down=false;pointer.id=null;pointer.active=false;endPan();setTool(false);
    reset();burstStart=-100;
    modeButton.hidden=!freeMode;extinguishButton.hidden=!freeMode;
    burstButton.hidden=emitterKind!==6;
    restartButton.textContent=key==='free'?'Clear fire':'Restart';
    focusButton.disabled=true;
    brush.x=brush.fromX=.5;
    const height=key==='ring'?1.65:key==='sphere'?1.0:key==='explosion'?1.0:key==='torch'?1.1:.2;
    brush.y=brush.fromY=(height+1.05)/7.875;
    paused=false;document.querySelector('#pause').textContent='Pause';lastFrame=performance.now();
    if(freeMode && key!=='free')ignite();
    else if(freeMode){extinguishButton.disabled=true;describeSource();message.textContent='Free fire · click to ignite';}
    else {
      message.textContent='Live GPU sigil · click to create fire';
      help.textContent='Choose a source above, or click the canvas to create and drag your own fire.';
    }
    needsDraw=true;
  }
  presetControl.onchange=()=>selectPreset(presetControl.value);
  burstButton.onclick=()=>{if(emitterKind===6)ignite();};
''')
s=s.replace("      freeMode = true;\n      reset();", "      freeMode = true;emitterKind=0;presetControl.value='free';\n      reset();")
a=s.index('    brush.active = true;\n    focusButton.disabled=false;',s.index("view.addEventListener('pointerdown'"))
b=s.index('\n  });',a)
s=s[:a]+'''    ignite();'''+s[b:]
a=s.index('  restartButton.onclick = () => {')
b=s.index("  window.addEventListener('keydown'",a)
s=s[:a]+'''  restartButton.onclick = () => selectPreset(presetControl.value);
  modeButton.onclick = () => selectPreset('sigil');
'''+s[b:]
# Bursts can be positioned by a click but should not paint a continuous charge on drag.
s=s.replace('if (freeMode && pointer.down) {', 'if (freeMode && pointer.down && emitterKind!==6) {')
s=s.replace('if (freeMode) { brush.x = pointer.x; brush.y = pointer.y; }', 'if (freeMode && emitterKind!==6) { brush.x = pointer.x; brush.y = pointer.y; }')
f.write_text(s,encoding='utf-8')

f=p/'fire-optics.js';s=f.read_text(encoding='utf-8')
s=s.replace('  vec3 fireEmission', '''  vec3 sootEmission(float soot,float temperature){
    float heat=max(temperature-.65,0.);
    return vec3(1.,.12,.015)*max(soot,0.)*heat*heat*.30;
  }
  vec3 fireEmission''')
f.write_text(s,encoding='utf-8')

f=p/'fire-room.js';s=f.read_text(encoding='utf-8')
s=s.replace('vec3 e=fireEmission(reaction,chem.b);','vec3 e=fireEmission(reaction,chem.b)+sootEmission(chem.a,chem.b);')
s=s.replace('density=vec4(sootExtinction(chem.a),0.,0.,1.);','''// Four subcell samples retain thin advected soot in the shadow grid.
        vec3 h=vec3(.25/128.,.25/64.,.25/15.);
        float soot=.25*(sampleVolume(chemistry,p+h).a+sampleVolume(chemistry,p-h).a
          +sampleVolume(chemistry,p+h*vec3(1,-1,-1)).a+sampleVolume(chemistry,p+h*vec3(-1,1,1)).a);
        density=vec4(sootExtinction(soot),0.,0.,1.);''')
s=s.replace('float stride=(leave-enter)/8.', 'float stride=(leave-enter)/12.').replace('for(int j=0;j<8;j++)tau', 'for(int j=0;j<12;j++)tau')
f.write_text(s,encoding='utf-8')

f=p/'index.html';s=f.read_text(encoding='utf-8')
s=s.replace('button:focus-visible, a:focus-visible,', 'button:focus-visible, select:focus-visible, a:focus-visible,')
s=s.replace('    input { accent-color:', '    .source-controls { margin:0 0 12px; }\n    select { background:#111; color:#ddd; border:1px solid #454545; padding:8px; font:inherit; }\n    input { accent-color:')
s=s.replace('    <div class="view"', '''    <div class="scene-controls source-controls" aria-label="Fire sources">
      <label for="preset">Source <select id="preset"><option value="sigil">Cybrdelic sigil</option><option value="free">Free fire</option><option value="campfire">Campfire</option><option value="torch">Torch jet</option><option value="ring">Burning ring</option><option value="sphere">Fire sphere</option><option value="wall">Fire wall</option><option value="explosion">Explosion</option></select></label>
      <label for="fuel">Fire type <select id="fuel"><option value="wood">Wood · rolling flame</option><option value="gas">Gas · cleaner jet</option><option value="oil">Oil · heavy soot</option></select></label>
      <button id="burst" type="button" hidden>Trigger burst</button>
    </div>
    <div class="view"''')
s=s.replace('    main:fullscreen .view { width:min(100%,calc((100dvh - 220px)*16/9));','    main:fullscreen .view { width:min(100%,calc((100dvh - 280px)*16/9));')
s=s.replace('  <script src="fire.js?v=view-4"></script>', '  <script src="fire-emitters.js?v=presets-1"></script>\n  <script src="fire.js?v=presets-1"></script>')
s=s.replace('fire-optics.js?v=quality-3','fire-optics.js?v=smoke-5').replace('fire-room.js?v=view-1','fire-room.js?v=smoke-5')
f.write_text(s,encoding='utf-8')
print('Updated fire runtime, emitters, optics, room shadows and controls.')
