"""Capture Original's actual volume shader over a fixed synthetic fire field.

This isolates rendering changes from solver changes. It is an offscreen GLES 3
visual gate, not a live-browser performance measurement or simulated animation.
"""

import argparse
import importlib.util
import json
import statistics
import subprocess
import time
from pathlib import Path

import glfw
import numpy as np
from OpenGL import GL
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live"
WIDTH, HEIGHT, DEPTH = 256, 144, 32
TILES_X, TILES_Y = 8, 4
ATLAS_W, ATLAS_H = WIDTH * TILES_X, HEIGHT * TILES_Y
OUT_W, OUT_H = 800, 450
VERTEX = """#version 300 es
out vec2 uv;
void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);uv=p;gl_Position=vec4(p*2.-1.,0.,1.);}
"""
PRESENT = f"""#version 300 es
precision highp float;
in vec2 uv;
uniform sampler2D projection;
layout(location=0) out vec4 outColor;
vec3 aces(vec3 x){{return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.);}}
void main(){{
  vec2 stepSize=1./vec2({OUT_W}.,{OUT_H}.);
  vec3 linear=texture(projection,uv).rgb;
  vec3 glow=(texture(projection,uv+vec2(stepSize.x*3.,0.)).rgb+
             texture(projection,uv-vec2(stepSize.x*3.,0.)).rgb+
             texture(projection,uv+vec2(0.,stepSize.y*3.)).rgb+
             texture(projection,uv-vec2(0.,stepSize.y*3.)).rgb)*.25;
  linear=(linear+max(glow-vec3(1.),vec3(0))*.012)*.60;
  float luminance=dot(linear,vec3(.2126,.7152,.0722));
  vec3 huePreserving=linear*aces(vec3(luminance)).x/max(luminance,.00001);
  vec3 mapped=mix(aces(linear),clamp(huePreserving,0.,1.),.45);
  mapped=mix(mapped*12.92,1.055*pow(mapped,vec3(1./2.4))-.055,step(vec3(.0031308),mapped));
  outColor=vec4(mapped,1.);
}}
"""


def shader(kind, source):
    handle = GL.glCreateShader(kind)
    GL.glShaderSource(handle, source)
    GL.glCompileShader(handle)
    if not GL.glGetShaderiv(handle, GL.GL_COMPILE_STATUS):
        raise RuntimeError(GL.glGetShaderInfoLog(handle).decode("utf-8", "replace"))
    return handle


def program(fragment):
    vs, fs = shader(GL.GL_VERTEX_SHADER, VERTEX), shader(GL.GL_FRAGMENT_SHADER, fragment)
    handle = GL.glCreateProgram()
    GL.glAttachShader(handle, vs)
    GL.glAttachShader(handle, fs)
    GL.glLinkProgram(handle)
    if not GL.glGetProgramiv(handle, GL.GL_LINK_STATUS):
        raise RuntimeError(GL.glGetProgramInfoLog(handle).decode("utf-8", "replace"))
    GL.glDeleteShader(vs)
    GL.glDeleteShader(fs)
    return handle


def assembled_rendering():
    spec = importlib.util.spec_from_file_location("original_compile", ROOT / "tools/fire-studio/compile-original-shaders.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    js = module.JS.replace(
        "const NX=640,NZ=360,DEPTH=32,TILES_X=8,TILES_Y=4",
        f"const NX={WIDTH},NZ={HEIGHT},DEPTH={DEPTH},TILES_X={TILES_X},TILES_Y={TILES_Y}",
    )
    js = js.replace("await import(process.argv[2]);", "await import(process.argv[2]);await import(process.argv[4]);")
    begin = js.index("const room={surfaceGLSL:")
    end = js.index("const rendering=", begin)
    js = js[:begin] + """const room={surfaceGLSL:window.FireOptics+`
uniform vec3 cameraEye,ambientLight;
vec3 roomRay(vec2 uv){return vec3(0,0,-1);}
float roomHit(vec3 eye,vec3 ray,out vec3 normal){normal=vec3(0,1,0);return 100.;}
vec3 roomSurface(vec3 at,vec3 normal,vec3 incoming){return vec3(0);}
vec3 smokeIrradiance(vec3 at){return vec3(1);}
void roomLight(int index,out vec3 light,out vec3 power){light=vec3(0,2,0);power=vec3(1);}
void spotSample(int index,vec3 point,out vec3 direction,out vec3 power){direction=vec3(0,1,0);power=vec3(1);}
`};
""" + js[end:]
    command = ["node", "--input-type=module", "-e", js,
               (SOURCE / "fire-emitters.js").as_uri(),
               (SOURCE / "fire-props.js").as_uri(),
               (SOURCE / "fire.js").as_uri(),
               (SOURCE / "fire-optics.js").as_uri()]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)["rendering"]


def fire_atlas():
    xx = np.linspace(-7., 7., WIDTH, dtype=np.float32)[None, None, :]
    zz = np.linspace(-1.05, 6.825, HEIGHT, dtype=np.float32)[None, :, None]
    dd = np.linspace(-.9, .9, DEPTH, dtype=np.float32)[:, None, None]
    tongues = np.zeros((DEPTH, HEIGHT, WIDTH), np.float32)
    for x0, top, phase in [(-.9, 2.0, 0.), (-.15, 2.8, 1.8), (.75, 2.35, 3.1)]:
        center = x0 + .20 * np.sin(2.5 * zz + 2.8 * dd + phase) + .09 * np.sin(8. * zz - 4. * dd + phase)
        width = np.maximum(.14, .49 - .07 * zz)
        body = np.exp(-((xx - center) / width) ** 4)
        bottom = np.clip((zz + .02) / .18, 0., 1.)
        cap = np.clip((top + .20 * np.sin(5. * xx + phase + 3. * dd) - zz) / .45, 0., 1.)
        tongues += body * bottom * cap
    depth_shape = np.exp(-(dd / .42) ** 4)
    internal = np.clip(.62 + .23 * np.sin(14. * xx + 8. * zz + 9. * dd)
                       + .16 * np.sin(25. * xx - 15. * zz + 4. * dd), .13, 1.0)
    flame = np.clip(tongues * depth_shape * internal, 0., 1.)
    soot = np.clip(tongues * depth_shape * (.07 + .13 * np.clip(zz / 2.8, 0., 1.)), 0., 1.)
    chem = np.empty((DEPTH, HEIGHT, WIDTH, 4), np.float16)
    chem[..., 0] = flame * .25
    chem[..., 1] = 1. - flame * .4
    chem[..., 2] = .15 + flame * 2.35
    chem[..., 3] = soot
    chem[..., 2] = np.where(flame > .025, chem[..., 2], 0.)
    vf = np.zeros_like(chem)
    vf[..., 3] = flame * 1.3
    def pack(volume):
        return volume.reshape(TILES_Y, TILES_X, HEIGHT, WIDTH, 4).transpose(0, 2, 1, 3, 4).reshape(ATLAS_H, ATLAS_W, 4).copy()
    return pack(chem), pack(vf)


def texture(data, *, float_texture=True):
    handle = GL.glGenTextures(1)
    GL.glBindTexture(GL.GL_TEXTURE_2D, handle)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
    if float_texture:
        h, w = data.shape[:2]
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA16F, w, h, 0, GL.GL_RGBA, GL.GL_HALF_FLOAT, data)
    else:
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, 8, 4, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, np.zeros((4, 8, 4), np.uint8))
    return handle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    fragment = assembled_rendering()
    if not glfw.init():
        raise RuntimeError("GLFW initialization failed")
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CLIENT_API, glfw.OPENGL_ES_API)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 0)
    window = glfw.create_window(OUT_W, OUT_H, "Original volume QA", None, None)
    if not window:
        glfw.terminate()
        raise RuntimeError("Hidden GLES 3 context unavailable")
    try:
        glfw.make_context_current(window)
        GL.glGetString(GL.GL_VERSION)
        prog = program(fragment)
        present = program(PRESENT)
        GL.glUseProgram(prog)
        chem, vf = fire_atlas()
        textures = {"chemTex": texture(chem), "vfTex": texture(vf), "smokeLightTex": texture(None, float_texture=False)}
        for unit, (name, tex) in enumerate(textures.items()):
            GL.glActiveTexture(GL.GL_TEXTURE0 + unit)
            GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
            GL.glUniform1i(GL.glGetUniformLocation(prog, name), unit)
        for name, value in {"viewZoom": 1.6, "roomEnabled": 0., "customLighting": 0.,
                            "visibleEmitter": 0, "gasFlame": 0., "tintStrength": 0.}.items():
            loc = GL.glGetUniformLocation(prog, name)
            if loc >= 0:
                (GL.glUniform1i if isinstance(value, int) else GL.glUniform1f)(loc, value)
        GL.glUniform3f(GL.glGetUniformLocation(prog, "flameTint"), 1., 1., 1.)
        GL.glUniform2f(GL.glGetUniformLocation(prog, "viewPan"), 0., -1.)
        GL.glUniform3f(GL.glGetUniformLocation(prog, "cameraEye"), 0., 2., 4.)
        GL.glBindVertexArray(GL.glGenVertexArrays(1))
        GL.glViewport(0, 0, OUT_W, OUT_H)
        projected = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, projected)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA16F, OUT_W, OUT_H, 0, GL.GL_RGBA, GL.GL_HALF_FLOAT, None)
        fbo = GL.glGenFramebuffers(1)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
        GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, projected, 0)
        if GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) != GL.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("Projection framebuffer incomplete")
        GL.glFinish()
        timings = []
        for _ in range(5):
            start = time.perf_counter()
            GL.glUseProgram(prog)
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
            for unit, tex in enumerate(textures.values()):
                GL.glActiveTexture(GL.GL_TEXTURE0 + unit)
                GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
            GL.glUseProgram(present)
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
            GL.glActiveTexture(GL.GL_TEXTURE0)
            GL.glBindTexture(GL.GL_TEXTURE_2D, projected)
            GL.glUniform1i(GL.glGetUniformLocation(present, "projection"), 0)
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
            GL.glFinish()
            timings.append((time.perf_counter() - start) * 1000)
        data = GL.glReadPixels(0, 0, OUT_W, OUT_H, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        Image.frombytes("RGBA", (OUT_W, OUT_H), data).transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(args.output)
        print(json.dumps({"path": str(args.output), "dimensions": [OUT_W, OUT_H],
                          "render_ms_median": round(statistics.median(timings[1:]), 2),
                          "gl_error": int(GL.glGetError())}))
    finally:
        glfw.destroy_window(window)
        glfw.terminate()


if __name__ == "__main__":
    main()
