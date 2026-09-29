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
import {readFileSync} from 'node:fs';
globalThis.window={};
await import(process.argv[1]);
await import(process.argv[2]);
const fire=readFileSync(new URL(process.argv[3]),'utf8');
function body(marker){const start=fire.indexOf(marker)+marker.length;if(start<marker.length)throw Error('Missing '+marker);return fire.slice(start,fire.indexOf('`;',start));}
const domain={extentGLSL:'vec3(14.,7.875,1.8)',minimumGLSL:'vec3(-7.,-1.05,-.9)'};
const NX=640,NZ=360,DEPTH=32,TILES_X=8,TILES_Y=4,AW=NX*TILES_X,AH=NZ*TILES_Y;
const shared=Function('domain','NX','NZ','DEPTH','TILES_X','AW','AH','return `'+body('const shared = `')+'`;')(domain,NX,NZ,DEPTH,TILES_X,AW,AH);
const pressure={samplingGLSL:'vec3 samplePressureCorrection(vec3 p){return vec3(0);}'},vorticity={samplingGLSL:'vec3 vortexForce(vec3 p){return vec3(0);}'},advection={correctionGLSL:'vec4 maccormackScalars(vec3 a,vec3 b,vec3 v,bool freeMode){return vec4(0,1,0,0);}'};
const simulation=Function('shared','pressure','vorticity','advection','window','NX','NZ','TILES_X','return `'+body('const simulation = () => `')+'`;')(shared,pressure,vorticity,advection,window,NX,NZ,TILES_X);
const room={surfaceGLSL:`
const vec3 fireExtent=vec3(14.,7.875,1.8),fireMin=vec3(-7.,-1.05,-.9);
const float domainBlast=0.;
uniform vec3 cameraEye,ambientLight;
vec3 roomRay(vec2 uv){return vec3(0,0,-1);}
float roomHit(vec3 eye,vec3 ray,out vec3 normal){normal=vec3(0,1,0);return 100.;}
vec3 roomSurface(vec3 at,vec3 normal,vec3 incoming){return vec3(0);}
vec3 smokeIrradiance(vec3 at){return vec3(1);}
float sootExtinction(float soot){return soot*4.;}
vec3 fireEmission(float reaction,float temperature){return vec3(reaction);}
vec3 sootEmission(float soot,float temperature){return vec3(0);}
void roomLight(int index,out vec3 light,out vec3 power){light=vec3(0,2,0);power=vec3(1);}
void spotSample(int index,vec3 point,out vec3 direction,out vec3 power){direction=vec3(0,1,0);power=vec3(1);}
`};
const rendering=Function('shared','room','window','DEPTH','TILES_Y','return `'+body('const rendering = () => `')+'`;')(shared,room,window,DEPTH,TILES_Y);
process.stdout.write(JSON.stringify({emitters:window.FireEmitters,props:window.FireProps,simulation,rendering}));
"""


def compile_fragment(label: str, source: str) -> None:
    shader = GL.glCreateShader(GL.GL_FRAGMENT_SHADER)
    GL.glShaderSource(shader, source)
    GL.glCompileShader(shader)
    ok = GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS)
    log = GL.glGetShaderInfoLog(shader)
    if isinstance(log, bytes):
        log = log.decode("utf-8", "replace")
    GL.glDeleteShader(shader)
    if not ok:
        raise RuntimeError(f"{label} failed GLSL compilation:\n{log[:12000]}")
    print(f"{label}: compiled")


def real_room_sources() -> dict:
    """Assemble real lighting shaders through the production room constructor."""
    js = JS.replace("await import(process.argv[2]);", "await import(process.argv[2]);await import(process.argv[4]);await import(process.argv[5]);")
    begin, end = js.index("const room={surfaceGLSL:"), js.index("const rendering=")
    js = js[:begin] + """
window.FireDomain=domain;window.FireOptics=window.createFireOptics();window.createFireRoom();
const fragments=[];
const gl=new Proxy({
 VERTEX_SHADER:35633,FRAGMENT_SHADER:35632,FRAMEBUFFER_COMPLETE:36053,
 createShader:type=>type,getShaderParameter:()=>true,getProgramParameter:()=>true,
 checkFramebufferStatus:()=>36053,
 shaderSource:(type,source)=>{if(type===35632)fragments.push(source)}
},{get(target,key){return key in target?target[key]:(...args)=>1}});
const room=window.FireRoom.setup(gl,{nx:NX,nz:NZ,depth:DEPTH,tilesX:TILES_X});
""" + js[end:]
    js = js.replace("{emitters:window.FireEmitters,props:window.FireProps,simulation,rendering}", "{fragments,rendering}")
    result = subprocess.run([
        "node", "--input-type=module", "-e", js,
        (SOURCE / "fire-emitters.js").as_uri(), (SOURCE / "fire-props.js").as_uri(),
        (SOURCE / "fire.js").as_uri(), (SOURCE / "fire-optics.js").as_uri(),
        (SOURCE / "fire-room.js").as_uri(),
    ], check=True, capture_output=True, text=True)
    sources = json.loads(result.stdout)
    if len(sources["fragments"]) != 4:
        raise RuntimeError("Expected four production room lighting shaders")
    return sources


def main() -> None:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", JS, (SOURCE / "fire-emitters.js").as_uri(), (SOURCE / "fire-props.js").as_uri(), (SOURCE / "fire.js").as_uri()],
        check=True, capture_output=True, text=True,
    )
    snippets = json.loads(result.stdout)
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
        preamble = """#version 300 es
precision highp float;
precision highp sampler2D;
precision highp sampler3D;
uniform sampler2D noiseTex;
uniform sampler2D chemTex;
uniform float clock;
uniform vec2 brushTo;
const vec3 simExtent=vec3(14.,7.875,3.);
const vec3 simMin=vec3(-7.,-1.05,-1.5);
vec4 field(sampler2D tex,vec3 pos){return vec4(pos,0.);}
"""
        compile_fragment("emitters", preamble + snippets["emitters"] + "\nout vec4 result; void main(){float density;vec3 jet;emitter(vec2(.1),.2,density,jet);result=vec4(jet,density);}")
        props_header = """#version 300 es
precision highp float;
precision highp sampler3D;
uniform vec3 ambientLight;
void roomLight(int index,out vec3 light,out vec3 power){light=vec3(0,2,0);power=vec3(1);}
void spotSample(int index,vec3 point,out vec3 direction,out vec3 power){direction=vec3(0,1,0);power=vec3(1);}
"""
        compile_fragment("props", props_header + snippets["props"] + "\nout vec4 result; void main(){float d=100.;vec3 c;bool hit=sourceProp(vec3(0,0,4),vec3(0,0,-1),d,c);result=vec4(c,hit?1.:0.);}")
        compile_fragment("simulation", snippets["simulation"])
        compile_fragment("rendering", snippets["rendering"])
        actual = real_room_sources()
        for i, fragment in enumerate(actual["fragments"]):
            compile_fragment(f"room lighting {i + 1}", fragment)
        compile_fragment("assembled room rendering", actual["rendering"])
    finally:
        glfw.destroy_window(window)
        glfw.terminate()


if __name__ == "__main__":
    main()
