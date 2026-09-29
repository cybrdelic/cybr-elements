"""Render the Original wood-flame emission curve in a hidden GLES 3 context.

The image is a controlled optical probe, not a capture of the running solver.
It helps catch washed-out colors without relying on a browser session.
"""

import argparse
import subprocess
from pathlib import Path

import glfw
from OpenGL import GL
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
OPTICS = ROOT / "outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/fire-optics.js"
VERTEX = """#version 300 es
void main(){
  vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);
  gl_Position=vec4(p*2.-1.,0.,1.);
}
"""


def compile_shader(kind, source):
    shader = GL.glCreateShader(kind)
    GL.glShaderSource(shader, source)
    GL.glCompileShader(shader)
    if not GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS):
        raise RuntimeError(GL.glGetShaderInfoLog(shader).decode("utf-8", "replace"))
    return shader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    optics = subprocess.run(
        ["node", "--input-type=module", "-e",
         "globalThis.window={};await import(process.argv[1]);process.stdout.write(window.FireOptics);",
         OPTICS.as_uri()],
        check=True, capture_output=True, text=True,
    ).stdout
    width, height = 800, 480
    if not glfw.init():
        raise RuntimeError("GLFW initialization failed")
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CLIENT_API, glfw.OPENGL_ES_API)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 0)
    window = glfw.create_window(width, height, "Original optics QA", None, None)
    if not window:
        glfw.terminate()
        raise RuntimeError("Hidden GLES 3 context unavailable")
    try:
        glfw.make_context_current(window)
        fragment = """#version 300 es
precision highp float;
uniform vec2 resolution;
layout(location=0) out vec4 outColor;
""" + optics + """
vec3 aces(vec3 x){return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.);}
void main(){
  vec2 uv=gl_FragCoord.xy/resolution;
  float temp=mix(.28,3.,uv.y);
  float reaction=mix(.06,2.0,uv.x);
  vec3 linear=fireEmission(reaction,temp)*.22*.60;
  float luminance=dot(linear,vec3(.2126,.7152,.0722));
  vec3 huePreserving=linear*aces(vec3(luminance)).x/max(luminance,.00001);
  vec3 mapped=mix(aces(linear),clamp(huePreserving,0.,1.),.45);
  mapped=mix(mapped*12.92,1.055*pow(mapped,vec3(1./2.4))-.055,step(vec3(.0031308),mapped));
  outColor=vec4(mapped,1.);
}
"""
        vs = compile_shader(GL.GL_VERTEX_SHADER, VERTEX)
        fs = compile_shader(GL.GL_FRAGMENT_SHADER, fragment)
        program = GL.glCreateProgram()
        GL.glAttachShader(program, vs)
        GL.glAttachShader(program, fs)
        GL.glLinkProgram(program)
        if not GL.glGetProgramiv(program, GL.GL_LINK_STATUS):
            raise RuntimeError(GL.glGetProgramInfoLog(program).decode("utf-8", "replace"))
        GL.glUseProgram(program)
        GL.glUniform2f(GL.glGetUniformLocation(program, "resolution"), width, height)
        GL.glUniform1f(GL.glGetUniformLocation(program, "gasFlame"), 0.)
        GL.glUniform3f(GL.glGetUniformLocation(program, "flameTint"), 1., 1., 1.)
        GL.glUniform1f(GL.glGetUniformLocation(program, "tintStrength"), 0.)
        vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(vao)
        GL.glViewport(0, 0, width, height)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        pixels = GL.glReadPixels(0, 0, width, height, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        Image.frombytes("RGBA", (width, height), pixels).transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(args.output)
        print(f"{args.output} {width}x{height}")
    finally:
        glfw.destroy_window(window)
        glfw.terminate()


if __name__ == "__main__":
    main()
