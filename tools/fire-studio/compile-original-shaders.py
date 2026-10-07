"""Compile the Original source and render shaders in a hidden OpenGL ES 3 context.

This checks shader syntax without loading the browser application. It does not
measure browser performance or validate the full assembled render pipeline.
"""

import json
import subprocess
from pathlib import Path

import glfw
from OpenGL import GL


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live"
JS = """
import {pathToFileURL} from 'node:url';
const options=JSON.parse(process.argv[2]||'{}'),root=process.argv[1];
const url=name=>pathToFileURL(root+'/'+name).href;
globalThis.window={};
const nx=options.nx??640,ny=options.ny??360,depth=options.depth??32;
const extent=options.extent??[14,7.875,options.objectSource?3:1.8];
const minimum=options.minimum??[-7,-1.05,-extent[2]/2];
const vector=v=>'vec3('+v.map(x=>Number(x).toFixed(5)).join(',')+')';
window.FireDomain={nx,ny,depth,extent,minimum,extentGLSL:vector(extent),minimumGLSL:vector(minimum),object:!!options.objectSource,blast:!!options.blast};
for(const file of ['fire-emitters.js','fire-props.js','fire-optics.js','fire-room.js','corrected-advection.js'])await import(url(file));
window.FireOptics=window.createFireOptics();window.createFireRoom();
const {woodMaterialGLSL}=await import(url('wood-material.js'));
const {POWER_DEFINITIONS}=await import(url('fire-powers.js'));
const {createOriginalShaders}=await import(url('original-shaders.js'));
const {woodCapacityGLSL,woodUpdateGLSL}=await import(url('wood-state-gl.js'));
const max=21+Math.max(...POWER_DEFINITIONS.map(p=>p.kind));
const emitters=window.createFireEmitters(max-21,4);
const shaders=createOriginalShaders({domain:window.FireDomain,hasPowers:options.powerKind!=null,hasWood:!!options.hasWood,initialPowerKind:options.powerKind??null,
 MAX_POWER_EMITTER:max,renderSize:[options.renderWidth??896,options.renderHeight??504],emittersGLSL:emitters,propsGLSL:window.FireProps,woodMaterialGLSL});
const fragments=[];
const gl=new Proxy({VERTEX_SHADER:35633,FRAGMENT_SHADER:35632,FRAMEBUFFER_COMPLETE:36053,
 createShader:type=>type,getShaderParameter:()=>true,getProgramParameter:()=>true,checkFramebufferStatus:()=>36053,
 shaderSource:(type,source)=>{if(type===35632)fragments.push(source)}
},{get(target,key){return key in target?target[key]:(...args)=>1}});
const room=window.FireRoom.setup(gl,{nx,nz:ny,depth,tilesX:8});
const advection=Object.create(window.MacCormackAdvection.prototype);
Object.assign(advection,{nx,nz:ny,depth,tilesX:8,tilesY:depth/8,width:nx*8,height:ny*depth/8});
const pressureGLSL=options.pressureGLSL??'vec3 samplePressureCorrection(vec3 p){return vec3(0);}';
const vorticityGLSL=options.vorticityGLSL??'vec3 vortexForce(vec3 p){return vec3(0);}';
const simulation=shaders.simulation(options.powerKind??null,{pressureGLSL,vorticityGLSL,advectionGLSL:advection.makeCorrectionGLSL()});
process.stdout.write(JSON.stringify({powerKinds:POWER_DEFINITIONS.map(d=>[d.kind,d.name]),emitters,props:window.FireProps,simulation,rendering:shaders.rendering(room.surfaceGLSL),
 predictor:advection.makePredictorFragment(pressureGLSL),fragments,vertex:shaders.vertex,presentation:shaders.presentation,diffusion:shaders.diffusion,
 woodCapacity:woodCapacityGLSL(shaders.shared),woodUpdate:woodUpdateGLSL(shaders.shared)}));
"""


def assemble_sources(**options):
    """Use the production shader factory; never extract templates from runtime text."""
    result = subprocess.run(["node", "--input-type=module", "-e", JS,
                             str(SOURCE), json.dumps(options)],
                            check=True, capture_output=True, text=True, encoding="utf-8")
    return json.loads(result.stdout)



def compile_fragment(label: str, source: str) -> None:
    shader = GL.glCreateShader(GL.GL_FRAGMENT_SHADER)
    GL.glShaderSource(shader, source)
    GL.glCompileShader(shader)
    ok = GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS)
    log = GL.glGetShaderInfoLog(shader)
    if isinstance(log, bytes):
        log = log.decode("utf-8", "replace")
    if not ok:
        GL.glDeleteShader(shader)
        raise RuntimeError(f"{label} failed GLSL compilation:\n{log[:12000]}")
    # Compilation alone misses interface and sampler-budget startup failures.
    vertex = GL.glCreateShader(GL.GL_VERTEX_SHADER)
    GL.glShaderSource(vertex, '#version 300 es\nprecision highp float;out vec2 uv;void main(){uv=vec2(0);gl_Position=vec4(0,0,0,1);}')
    GL.glCompileShader(vertex)
    program = GL.glCreateProgram()
    try:
        GL.glAttachShader(program, vertex); GL.glAttachShader(program, shader); GL.glLinkProgram(program)
        if not GL.glGetProgramiv(program, GL.GL_LINK_STATUS):
            raise RuntimeError(f'{label} failed linking: {GL.glGetProgramInfoLog(program)}')
        types = {GL.GL_SAMPLER_2D, GL.GL_SAMPLER_3D, GL.GL_SAMPLER_CUBE, GL.GL_SAMPLER_2D_SHADOW}
        samplers = sum(int(size) for name,size,kind in (GL.glGetActiveUniform(program,i) for i in range(GL.glGetProgramiv(program,GL.GL_ACTIVE_UNIFORMS))) if kind in types)
        if samplers > 16:
            raise RuntimeError(f'{label} uses {samplers} samplers; WebGL baseline limit is 16')
    finally:
        GL.glDeleteProgram(program); GL.glDeleteShader(vertex); GL.glDeleteShader(shader)
    print(f"{label}: compiled and linked ({samplers} samplers)")


def real_room_sources(object_source=False):
    sources = assemble_sources(objectSource=object_source)
    if len(sources["fragments"]) != 4:
        raise RuntimeError("Expected four production room lighting shaders")
    return sources


def main() -> None:
    snippets = assemble_sources()
    if not glfw.init():
        raise RuntimeError("GLFW could not initialize")
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CLIENT_API, glfw.OPENGL_ES_API)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 0)
    window = glfw.create_window(16, 16, "Fire shader check", None, None)
    if window is None:
        glfw.terminate()
        raise RuntimeError("Hidden GL context unavailable")
    try:
        glfw.make_context_current(window)
        compile_fragment("simulation", snippets["simulation"])
        compile_fragment("rendering", snippets["rendering"])
        compile_fragment("presentation", snippets["presentation"])
        for kind, name in snippets["powerKinds"]:
            power = assemble_sources(powerKind=kind, blast=True, nx=384, ny=384, depth=64,
                                     extent=[8,8,4], minimum=[-4,-1.05,-2])
            compile_fragment(name + " simulation", power["simulation"])
            if kind == 2:
                compile_fragment("power rendering", power["rendering"])
        actual = real_room_sources()
        for i, fragment in enumerate(actual["fragments"]):
            compile_fragment(f"room lighting {i + 1}", fragment)
        compile_fragment("conservative mixing", actual["diffusion"])
        compile_fragment("assembled room rendering", actual["rendering"])
        objects = real_room_sources(object_source=True)
        compile_fragment("assembled object room rendering", objects["rendering"])
        wood = assemble_sources(objectSource=True,hasWood=True)
        for name in ['simulation','woodCapacity','woodUpdate','rendering']:
            compile_fragment('wood '+name,wood[name])
    finally:
        glfw.destroy_window(window)
        glfw.terminate()


if __name__ == "__main__":
    main()
