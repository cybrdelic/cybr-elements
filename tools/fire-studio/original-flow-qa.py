"""Run Original's source, transport, combustion, pressure and vorticity offscreen.

The deterministic campfire probe defaults to 256x144x32; --full uses the live
640x360x32 grid. It isolates flow on black without room lighting or props.
Synchronous native step timings do not certify browser frame pacing.
"""

import argparse
import hashlib
import importlib.util
import json
import statistics
import subprocess
import time
from pathlib import Path

import glfw
import numpy as np
from OpenGL import GL
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live"
SPEC = importlib.util.spec_from_file_location("volume_qa", ROOT / "tools/fire-studio/original-volume-qa.py")
VOLUME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VOLUME)
W, H = VOLUME.ATLAS_W, VOLUME.ATLAS_H
PRESSURE_X, PRESSURE_Z = 64, 36


def pressure_sources():
    js = """globalThis.window={};await import(process.argv[1]);
const fragments=[];
const gl=new Proxy({
  getExtension:()=>({}),getParameter:()=>16384,
  getShaderParameter:()=>true,getProgramParameter:()=>true,
  checkFramebufferStatus:()=>1,FRAMEBUFFER_COMPLETE:1,
  shaderSource:(kind,source)=>{if(source.includes('out vec4 outValue'))fragments.push(source)}
},{get(target,key){return key in target?target[key]:(...args)=>1}});
const projector=window.CoarsePressure.setup(gl,{
 nx:WIDTH,nz:HEIGHT,depth:32,tilesX:8,tilesY:4,
 coarseX:PRESSURE_X,coarseZ:PRESSURE_Z,coarseDepth:8,iterations:18,
 worldX:14,worldZ:7.875,worldY:1.8
});
process.stdout.write(JSON.stringify({fragments,samplingGLSL:projector.samplingGLSL}));
""".replace("WIDTH", str(VOLUME.WIDTH)).replace("HEIGHT", str(VOLUME.HEIGHT)).replace("PRESSURE_X", str(PRESSURE_X)).replace("PRESSURE_Z", str(PRESSURE_Z))
    result = subprocess.run(
        ["node", "--input-type=module", "-e", js, (SOURCE / "coarse-pressure.js").as_uri()],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    if len(data["fragments"]) != 3:
        raise RuntimeError(f"Expected three pressure shaders, got {len(data['fragments'])}")
    return data


def vorticity_sources():
    js = """globalThis.window={};await import(process.argv[1]);
const fragments=[];
const gl=new Proxy({
 getShaderParameter:()=>true,getProgramParameter:()=>true,
 checkFramebufferStatus:()=>1,FRAMEBUFFER_COMPLETE:1,
 shaderSource:(kind,source)=>{if(source.includes('out vec4 result'))fragments.push(source)}
},{get(target,key){return key in target?target[key]:(...args)=>1}});
const vortex=window.FireVorticity.setup(gl,{nx:WIDTH,nz:HEIGHT,depth:32,tilesX:8});
process.stdout.write(JSON.stringify({fragments,samplingGLSL:vortex.samplingGLSL}));
""".replace("WIDTH", str(VOLUME.WIDTH)).replace("HEIGHT", str(VOLUME.HEIGHT))
    result = subprocess.run(
        ["node", "--input-type=module", "-e", js, (SOURCE / "vorticity.js").as_uri()],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    if len(data["fragments"]) != 2:
        raise RuntimeError(f"Expected two vorticity shaders, got {len(data['fragments'])}")
    return data


def smoke_light_sources():
    js = """globalThis.window={};await import(process.argv[1]);
window.FireOptics=window.createFireOptics();await import(process.argv[2]);
const fragments=[];
const gl=new Proxy({
 VERTEX_SHADER:35633,FRAGMENT_SHADER:35632,FRAMEBUFFER_COMPLETE:36053,
 createShader:type=>type,getShaderParameter:()=>true,getProgramParameter:()=>true,
 checkFramebufferStatus:()=>36053,
 shaderSource:(type,source)=>{if(type===35632)fragments.push(source)}
},{get(target,key){return key in target?target[key]:(...args)=>1}});
window.SmokeLight.setup(gl,{nx:WIDTH,nz:HEIGHT,depth:32,tilesX:8});
process.stdout.write(JSON.stringify(fragments));
""".replace("WIDTH", str(VOLUME.WIDTH)).replace("HEIGHT", str(VOLUME.HEIGHT))
    result = subprocess.run(["node", "--input-type=module", "-e", js,
                             (SOURCE / "fire-optics.js").as_uri(),
                             (SOURCE / "smoke-light.js").as_uri()],
                            check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    if len(data) != 2:
        raise RuntimeError("Expected the production smoke gather and prefix shaders")
    return data


def shaders(pressure_glsl, vorticity_glsl):
    spec = importlib.util.spec_from_file_location("compile_qa", ROOT / "tools/fire-studio/compile-original-shaders.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    js = module.JS.replace(
        "const NX=640,NZ=360,DEPTH=32,TILES_X=8,TILES_Y=4",
        f"const NX={VOLUME.WIDTH},NZ={VOLUME.HEIGHT},DEPTH={VOLUME.DEPTH},TILES_X={VOLUME.TILES_X},TILES_Y={VOLUME.TILES_Y}",
    )
    js = js.replace("await import(process.argv[2]);", "await import(process.argv[2]);await import(process.argv[4]);")
    original = "const pressure={samplingGLSL:'vec3 samplePressureCorrection(vec3 p){return vec3(0);}'},vorticity={samplingGLSL:'vec3 vortexForce(vec3 p){return vec3(0);}'},advection={correctionGLSL:'vec4 maccormackScalars(vec3 a,vec3 b,vec3 v,bool freeMode){return vec4(0,1,0,0);}'};"
    replacement = """const pressure={samplingGLSL:PRESSURE_SAMPLING},vorticity={samplingGLSL:VORTICITY_SAMPLING},advection=Object.create(window.MacCormackAdvection.prototype);
Object.assign(advection,{nx:NX,nz:NZ,depth:DEPTH,tilesX:TILES_X,tilesY:TILES_Y,width:AW,height:AH});
advection.correctionGLSL=advection.makeCorrectionGLSL();
const predictor=advection.makePredictorFragment(pressure.samplingGLSL);
""".replace("PRESSURE_SAMPLING", json.dumps(pressure_glsl)).replace("VORTICITY_SAMPLING", json.dumps(vorticity_glsl))
    if original not in js:
        raise RuntimeError("Shader extraction marker changed")
    js = js.replace(original, replacement)
    js = js.replace("simulation,rendering}));", "simulation,rendering,predictor}));")
    result = subprocess.run(
        ["node", "--input-type=module", "-e", js,
         (SOURCE / "fire-emitters.js").as_uri(),
         (SOURCE / "fire-props.js").as_uri(),
         (SOURCE / "fire.js").as_uri(),
         (SOURCE / "corrected-advection.js").as_uri()],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def float_texture(width, height):
    tex = GL.glGenTextures(1)
    GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
    for pname in (GL.GL_TEXTURE_MIN_FILTER, GL.GL_TEXTURE_MAG_FILTER):
        GL.glTexParameteri(GL.GL_TEXTURE_2D, pname, GL.GL_LINEAR)
    for pname in (GL.GL_TEXTURE_WRAP_S, GL.GL_TEXTURE_WRAP_T):
        GL.glTexParameteri(GL.GL_TEXTURE_2D, pname, GL.GL_CLAMP_TO_EDGE)
    GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA16F, width, height, 0, GL.GL_RGBA, GL.GL_HALF_FLOAT, None)
    return tex


def red_texture(width, height):
    tex = GL.glGenTextures(1)
    GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
    for pname in (GL.GL_TEXTURE_MIN_FILTER, GL.GL_TEXTURE_MAG_FILTER):
        GL.glTexParameteri(GL.GL_TEXTURE_2D, pname, GL.GL_NEAREST)
    for pname in (GL.GL_TEXTURE_WRAP_S, GL.GL_TEXTURE_WRAP_T):
        GL.glTexParameteri(GL.GL_TEXTURE_2D, pname, GL.GL_CLAMP_TO_EDGE)
    GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_R32F, width, height, 0, GL.GL_RED, GL.GL_FLOAT, None)
    return tex


def fbo(*textures):
    result = GL.glGenFramebuffers(1)
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, result)
    for i, tex in enumerate(textures):
        GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0 + i, GL.GL_TEXTURE_2D, tex, 0)
    GL.glDrawBuffers([GL.GL_COLOR_ATTACHMENT0 + i for i in range(len(textures))])
    if GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) != GL.GL_FRAMEBUFFER_COMPLETE:
        raise RuntimeError("Floating simulation framebuffer incomplete")
    return result


def bind(prog, name, texture, unit):
    loc = GL.glGetUniformLocation(prog, name)
    if loc < 0:
        return
    GL.glActiveTexture(GL.GL_TEXTURE0 + unit)
    GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
    GL.glUniform1i(loc, unit)


def bind3d(prog, name, texture, unit):
    loc = GL.glGetUniformLocation(prog, name)
    if loc < 0:
        return
    GL.glActiveTexture(GL.GL_TEXTURE0 + unit)
    GL.glBindTexture(GL.GL_TEXTURE_3D, texture)
    GL.glUniform1i(loc, unit)


def volume_texture(data, floating=False):
    """Bind production 3D sampler types even when the campfire does not sample them."""
    depth, height, width, _ = data.shape
    tex = GL.glGenTextures(1)
    GL.glBindTexture(GL.GL_TEXTURE_3D, tex)
    for pname in (GL.GL_TEXTURE_MIN_FILTER, GL.GL_TEXTURE_MAG_FILTER):
        GL.glTexParameteri(GL.GL_TEXTURE_3D, pname, GL.GL_LINEAR if not floating else GL.GL_NEAREST)
    for pname in (GL.GL_TEXTURE_WRAP_S, GL.GL_TEXTURE_WRAP_T, GL.GL_TEXTURE_WRAP_R):
        GL.glTexParameteri(GL.GL_TEXTURE_3D, pname, GL.GL_REPEAT if not floating else GL.GL_CLAMP_TO_EDGE)
    GL.glTexImage3D(GL.GL_TEXTURE_3D, 0, GL.GL_RGBA16F if floating else GL.GL_RGBA8,
                   width, height, depth, 0, GL.GL_RGBA,
                   GL.GL_FLOAT if floating else GL.GL_UNSIGNED_BYTE, data)
    return tex


def setf(prog, name, value):
    loc = GL.glGetUniformLocation(prog, name)
    if loc >= 0:
        GL.glUniform1f(loc, value)


def seti(prog, name, value):
    loc = GL.glGetUniformLocation(prog, name)
    if loc >= 0:
        GL.glUniform1i(loc, value)


def smooth_noise():
    """Use production JS integer hash, valueNoise, rounding and turbulence bytes."""
    source = (SOURCE / "fire.js").read_text(encoding="utf-8")
    start = source.index("const n = new Uint8Array(256 * 256 * 4);")
    end = source.index("noiseTexture = texture(256, 256, n);", start)
    turbulence_start = source.index("const turbulence=new Uint8Array(64*64*64*4);", end)
    turbulence_end = source.index("gl.texImage3D(", turbulence_start)
    js = source[start:end] + source[turbulence_start:turbulence_end]
    js += "process.stdout.write(Buffer.concat([Buffer.from(n),Buffer.from(turbulence)]));"
    result = subprocess.run(["node", "-e", js], check=True, capture_output=True)
    noise_size, turbulence_size = 256 * 256 * 4, 64 * 64 * 64 * 4
    if len(result.stdout) != noise_size + turbulence_size:
        raise RuntimeError("Production noise generator returned incorrect byte count")
    data = np.frombuffer(result.stdout, dtype=np.uint8)
    noise = data[:noise_size].reshape((256, 256, 4))
    turbulence = data[noise_size:].reshape((64, 64, 64, 4))
    return noise, turbulence


def present_frame(render_prog, present_prog, projected_fbo, projected_tex, src, empty, object_tex, zoom, source_scale=1., smoke_light=None):
    """Render one solver state through the production projection/presentation shaders."""
    begin = time.perf_counter()
    smoke_texture = empty
    if smoke_light:
        programs, textures, framebuffers = smoke_light
        GL.glViewport(0, 0, 128 * 8, 72 * 4)
        GL.glUseProgram(programs[0])
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, framebuffers[0])
        bind(programs[0], "source", src[1], 8)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        read = 0
        for stride in (1, 2, 4, 8, 16, 32, 64):
            write = 1 - read
            GL.glUseProgram(programs[1])
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, framebuffers[write])
            bind(programs[1], "source", textures[read], 8)
            seti(programs[1], "stride", stride)
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
            read = write
        smoke_texture = textures[read]
    GL.glUseProgram(render_prog)
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, projected_fbo)
    GL.glViewport(0, 0, VOLUME.OUT_W, VOLUME.OUT_H)
    bind(render_prog, "chemTex", src[1], 0)
    bind(render_prog, "vfTex", src[0], 1)
    bind(render_prog, "smokeLightTex", smoke_texture, 2)
    bind3d(render_prog, "objectTex", object_tex, 14)
    setf(render_prog, "viewZoom", zoom)
    setf(render_prog, "sourceScale", source_scale)
    GL.glUniform2f(GL.glGetUniformLocation(render_prog, "sourcePosition"), .5, 1.05 / 7.875)
    setf(render_prog, "roomEnabled", 0.)
    GL.glUniform2f(GL.glGetUniformLocation(render_prog, "viewPan"), 0., -1.)
    GL.glUniform3f(GL.glGetUniformLocation(render_prog, "flameTint"), 1., 1., 1.)
    GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
    GL.glUseProgram(present_prog)
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
    bind(present_prog, "projection", projected_tex, 0)
    GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
    GL.glFinish()
    render_ms = (time.perf_counter() - begin) * 1000
    data = GL.glReadPixels(0, 0, VOLUME.OUT_W, VOLUME.OUT_H, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
    frame = Image.frombytes("RGBA", (VOLUME.OUT_W, VOLUME.OUT_H), data).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return frame, render_ms


def sequence_artifacts(directory, frame_records, capture_fps):
    """Keep a complete disk sequence and small review artifacts; never inline frames."""
    selected = np.linspace(0, len(frame_records) - 1, min(12, len(frame_records)), dtype=int)
    cols, thumb_width, thumb_height, caption_height = 4, 400, 225, 24
    rows = (len(selected) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_width, rows * (thumb_height + caption_height)), (14, 14, 16))
    draw = ImageDraw.Draw(sheet)
    for i, index in enumerate(selected):
        record = frame_records[int(index)]
        with Image.open(directory / record["file"]) as frame:
            thumb = frame.convert("RGB").resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        x, y = i % cols * thumb_width, i // cols * (thumb_height + caption_height)
        sheet.paste(thumb, (x, y))
        draw.text((x + 8, y + thumb_height + 4), f"{record['time_s']:.2f} s / step {record['step']}", fill=(216, 216, 220))
    sheet_path = directory / "contact-sheet.png"
    sheet.save(sheet_path)
    gif_frames = []
    for record in frame_records:
        with Image.open(directory / record["file"]) as frame:
            gif_frames.append(frame.convert("RGB").resize((400, 225), Image.Resampling.LANCZOS))
    # One fixed palette prevents a different quantization pattern on each frame.
    palette_sample = Image.new("RGB", (400, 225 * len(selected)))
    for i, index in enumerate(selected):
        palette_sample.paste(gif_frames[int(index)], (0, 225 * i))
    palette = palette_sample.quantize(colors=128)
    quantized = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in gif_frames]
    gif_path = directory / "motion.gif"
    quantized[0].save(gif_path, save_all=True, append_images=quantized[1:],
                      duration=round(1000 / capture_fps), loop=0, optimize=True, disposal=2)
    return {"contact_sheet": str(sheet_path), "gif": str(gif_path),
            "contact_sheet_bytes": sheet_path.stat().st_size, "gif_bytes": gif_path.stat().st_size}


def main():
    global SOURCE, W, H, PRESSURE_X, PRESSURE_Z
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--steps", type=int, default=90)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--expansion", type=float, default=0.)
    parser.add_argument("--source-scale", type=float, default=1.)
    parser.add_argument("--source-lift", type=float, default=1.)
    parser.add_argument("--source-feed", type=float, default=1.)
    parser.add_argument("--zoom", type=float, default=1.6)
    parser.add_argument("--source-root", type=Path, help="Execute an isolated runtime snapshot for a matched regression comparison")
    parser.add_argument("--preset", choices=("campfire", "sigil"), default="campfire")
    parser.add_argument("--source-heat", type=float, default=1.)
    parser.add_argument("--cooling-scale", type=float, default=1.)
    parser.add_argument("--ambient-forces", action="store_true", help="Compare the former empty-air force path")
    parser.add_argument("--unfiltered-noise", action="store_true", help="Compare the former non-mipmapped noise sampler")
    parser.add_argument("--force-object-shader", action="store_true", help="Measure the otherwise unreachable object branch in a normal-source shader")
    parser.add_argument("--sequence-dir", type=Path, help="Save intermediate frames, contact sheet, GIF and metadata")
    parser.add_argument("--report", type=Path, help="Save complete timing, shader hashes and capture metadata as JSON")
    parser.add_argument("--capture-fps", type=int, default=10, help="Intermediate capture rate, a divisor of 30 (default 10)")
    args = parser.parse_args()
    if args.source_root:
        SOURCE = args.source_root.resolve()
        VOLUME.SOURCE = SOURCE
    uses_mipmapped_noise = not args.unfiltered_noise and "gl.LINEAR_MIPMAP_LINEAR" in (SOURCE / "fire.js").read_text(encoding="utf-8")
    if not 1 <= args.steps <= 900:
        parser.error("--steps must be between 1 and 900")
    if args.capture_fps not in (1, 2, 3, 5, 6, 10, 15, 30):
        parser.error("--capture-fps must be a divisor of the 30 Hz solver rate")
    if args.sequence_dir:
        args.sequence_dir.mkdir(parents=True, exist_ok=True)
        if any(args.sequence_dir.glob("frame-*.png")):
            parser.error("--sequence-dir already contains frames; choose a new directory for a complete run")
    source_hashes = {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest()
                     for name in ("fire.js", "fire-optics.js", "fire-emitters.js", "fire-props.js",
                                  "coarse-pressure.js", "corrected-advection.js", "vorticity.js", "smoke-light.js")}
    if args.full:
        VOLUME.WIDTH, VOLUME.HEIGHT = 640, 360
        VOLUME.ATLAS_W, VOLUME.ATLAS_H = 5120, 1440
        W, H = VOLUME.ATLAS_W, VOLUME.ATLAS_H
        PRESSURE_X, PRESSURE_Z = 128, 72
    pressure_glsl = pressure_sources()
    vorticity_glsl = vorticity_sources()
    smoke_glsl = smoke_light_sources()
    snippets = shaders(pressure_glsl["samplingGLSL"], vorticity_glsl["samplingGLSL"])
    if args.ambient_forces:
        if "if(fuel+temp+soot<=.00001 && oxygen>=.99999){" not in snippets["simulation"]:
            raise RuntimeError("Empty-air comparison marker changed")
        snippets["simulation"] = snippets["simulation"].replace(
            "if(fuel+temp+soot<=.00001 && oxygen>=.99999){", "if(false){", 1)
    render_source = VOLUME.assembled_rendering()
    if args.force_object_shader:
        render_source = render_source.replace("#define FIRE_OBJECT_SOURCE 0", "#define FIRE_OBJECT_SOURCE 1")
    if not glfw.init():
        raise RuntimeError("GLFW initialization failed")
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CLIENT_API, glfw.OPENGL_ES_API)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 0)
    window = glfw.create_window(VOLUME.OUT_W, VOLUME.OUT_H, "Original flow QA", None, None)
    if not window:
        glfw.terminate()
        raise RuntimeError("Hidden GLES 3 context unavailable")
    try:
        glfw.make_context_current(window)
        GL.glBindVertexArray(GL.glGenVertexArrays(1))
        predictor_prog = VOLUME.program(snippets["predictor"])
        sim_prog = VOLUME.program(snippets["simulation"])
        pressure_progs = [VOLUME.program(fragment) for fragment in pressure_glsl["fragments"]]
        vorticity_progs = [VOLUME.program(fragment) for fragment in vorticity_glsl["fragments"]]
        render_prog = VOLUME.program(render_source)
        present_prog = VOLUME.program(VOLUME.PRESENT)
        smoke_programs = [VOLUME.program(fragment) for fragment in smoke_glsl]
        smoke_textures = [red_texture(128 * 8, 72 * 4) for _ in range(2)]
        for tex in smoke_textures:
            GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_R16F, 128 * 8, 72 * 4, 0, GL.GL_RED, GL.GL_HALF_FLOAT, None)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        smoke_light = (smoke_programs, smoke_textures, [fbo(tex) for tex in smoke_textures])
        states = []
        for _ in range(2):
            vel, chem = float_texture(W, H), float_texture(W, H)
            states.append((vel, chem, fbo(vel, chem)))
        predictor_tex = float_texture(W, H)
        predictor_fbo = fbo(predictor_tex)
        pressure_width, pressure_height = PRESSURE_X * 4, PRESSURE_Z * 2
        divergence_tex = red_texture(pressure_width, pressure_height)
        divergence_fbo = fbo(divergence_tex)
        pressure_tex = [red_texture(pressure_width, pressure_height) for _ in range(2)]
        pressure_fbo = [fbo(tex) for tex in pressure_tex]
        correction_tex = float_texture(pressure_width, pressure_height)
        correction_fbo = fbo(correction_tex)
        vortex_width, vortex_height = 192 * 4, 144 * 4
        curl_tex = float_texture(vortex_width, vortex_height)
        curl_fbo = fbo(curl_tex)
        vortex_tex = float_texture(vortex_width, vortex_height)
        vortex_fbo = fbo(vortex_tex)
        for framebuffer in pressure_fbo:
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, framebuffer)
            GL.glViewport(0, 0, pressure_width, pressure_height)
            GL.glClearBufferfv(GL.GL_COLOR, 0, [0., 0., 0., 0.])
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, correction_fbo)
        GL.glClearBufferfv(GL.GL_COLOR, 0, [0., 0., 0., 0.])
        projected_tex = float_texture(VOLUME.OUT_W, VOLUME.OUT_H)
        projected_fbo = fbo(projected_tex)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, states[0][2])
        GL.glViewport(0, 0, W, H)
        GL.glClearBufferfv(GL.GL_COLOR, 0, [0., 0., 0., 0.])
        GL.glClearBufferfv(GL.GL_COLOR, 1, [0., 1., 0., 0.])
        empty = VOLUME.texture(None, float_texture=False)
        noise_data, turbulence_data = smooth_noise()
        noise = VOLUME.texture(noise_data, float_texture=False)
        # The volume helper's dummy texture is 8x4; create the 256x256 noise explicitly.
        GL.glBindTexture(GL.GL_TEXTURE_2D, noise)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, 256, 256, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, noise_data)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_REPEAT)
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER,
                           GL.GL_LINEAR_MIPMAP_LINEAR if uses_mipmapped_noise else GL.GL_LINEAR)
        turbulence = volume_texture(turbulence_data)
        object_tex = volume_texture(np.array([[[[10., 0., 0., 0.]]]], dtype=np.float32), floating=True)
        GL.glUseProgram(sim_prog)
        seti(sim_prog, "emitterKind", 1 if args.preset == "campfire" else 0)
        GL.glUseProgram(render_prog)
        seti(render_prog, "visibleEmitter", 1 if args.preset == "campfire" else 0)
        GL.glUseProgram(sim_prog)
        setf(sim_prog, "sourceEnabled", 0. if args.preset == "campfire" else 1.)
        setf(sim_prog, "brushActive", 1. if args.preset == "campfire" else 0.)
        setf(sim_prog, "sourceScale", args.source_scale)
        setf(sim_prog, "sourceLift", args.source_lift)
        setf(sim_prog, "sourceHeat", args.source_heat)
        setf(sim_prog, "coolingScale", args.cooling_scale)
        setf(sim_prog, "presetBuoyancy", 4.)
        setf(sim_prog, "delta", 1. / 30.)
        GL.glUniform3f(GL.glGetUniformLocation(sim_prog, "fuelProfile"), args.source_feed, 1., 1.)
        for name in ("brushFrom", "brushTo"):
            GL.glUniform2f(GL.glGetUniformLocation(sim_prog, name), .5, 1.05 / 7.875)
        GL.glUniform2f(GL.glGetUniformLocation(sim_prog, "pointer"), .5, 1.05 / 7.875)
        GL.glUniform2f(GL.glGetUniformLocation(sim_prog, "pointerMotion"), 0., 0.)
        source_tex, width_tex = empty, empty
        if args.preset == "sigil":
            source_data = np.frombuffer((SOURCE / "source/source-native.rgba8.bin").read_bytes(), dtype=np.uint8).reshape((504, 896, 4))
            source_tex = VOLUME.texture(None, float_texture=False)
            GL.glBindTexture(GL.GL_TEXTURE_2D, source_tex)
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, 896, 504, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, source_data)
            width_data = np.frombuffer((SOURCE / "source/halfwidth-native.r8.bin").read_bytes(), dtype=np.uint8).reshape((504, 896))
            width_tex = VOLUME.texture(None, float_texture=False)
            GL.glBindTexture(GL.GL_TEXTURE_2D, width_tex)
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_R8, 896, 504, 0, GL.GL_RED, GL.GL_UNSIGNED_BYTE, width_data)
        bind(sim_prog, "sourceTex", source_tex, 2)
        bind(sim_prog, "widthTex", width_tex, 4)
        bind(sim_prog, "noiseTex", noise, 3)
        bind3d(sim_prog, "objectTex", object_tex, 14)
        bind3d(sim_prog, "turbulenceTex", turbulence, 15)
        step_ms = []
        render_ms = []
        frame_records = []
        errors = []
        capture_every = 30 // args.capture_fps
        current = 0
        for step in range(args.steps):
            begin = time.perf_counter()
            src = states[current]
            dst = states[1 - current]
            vortex_origin = [.5 - 2. / 14., 1.05 / 7.875 - .45 / 7.875, 0.] if args.preset == "campfire" else [0., 0., 0.]
            vortex_span = [4. / 14., 5.6 / 7.875, 1.] if args.preset == "campfire" else [1., 1., 1.]
            GL.glViewport(0, 0, vortex_width, vortex_height)
            GL.glUseProgram(vorticity_progs[0])
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, curl_fbo)
            bind(vorticity_progs[0], "velocity", src[0], 0)
            bind(vorticity_progs[0], "chemistry", src[1], 1)
            GL.glUniform3f(GL.glGetUniformLocation(vorticity_progs[0], "sourceOrigin"), *vortex_origin)
            GL.glUniform3f(GL.glGetUniformLocation(vorticity_progs[0], "span"), *vortex_span)
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
            GL.glUseProgram(vorticity_progs[1])
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, vortex_fbo)
            bind(vorticity_progs[1], "curlField", curl_tex, 0)
            GL.glUniform3f(GL.glGetUniformLocation(vorticity_progs[1], "span"), *vortex_span)
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
            GL.glViewport(0, 0, W, H)
            GL.glUseProgram(predictor_prog)
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, predictor_fbo)
            bind(predictor_prog, "vfTex", src[0], 0)
            bind(predictor_prog, "chemTex", src[1], 1)
            bind(predictor_prog, "pressureCorrectionTex", correction_tex, 5)
            setf(predictor_prog, "delta", 1. / 30.)
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
            GL.glUseProgram(sim_prog)
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, dst[2])
            bind(sim_prog, "vfTex", src[0], 0)
            bind(sim_prog, "chemTex", src[1], 1)
            bind(sim_prog, "mcPredictorTex", predictor_tex, 6)
            bind(sim_prog, "pressureCorrectionTex", correction_tex, 5)
            bind(sim_prog, "sourceTex", source_tex, 2)
            bind(sim_prog, "widthTex", width_tex, 4)
            bind(sim_prog, "noiseTex", noise, 3)
            bind3d(sim_prog, "objectTex", object_tex, 14)
            bind3d(sim_prog, "turbulenceTex", turbulence, 15)
            bind(sim_prog, "vortexTex", vortex_tex, 7)
            GL.glUniform3f(GL.glGetUniformLocation(sim_prog, "vortexOrigin"), *vortex_origin)
            GL.glUniform3f(GL.glGetUniformLocation(sim_prog, "vortexSpan"), *vortex_span)
            setf(sim_prog, "clock", step / 30.)
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
            GL.glViewport(0, 0, pressure_width, pressure_height)
            GL.glUseProgram(pressure_progs[0])
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, divergence_fbo)
            bind(pressure_progs[0], "uVf", dst[0], 0)
            setf(pressure_progs[0], "uExpansion", args.expansion)
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, pressure_fbo[0])
            GL.glClearBufferfv(GL.GL_COLOR, 0, [0., 0., 0., 0.])
            GL.glUseProgram(pressure_progs[1])
            bind(pressure_progs[1], "uDiv", divergence_tex, 1)
            read = 0
            for _ in range(18):
                write = 1 - read
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, pressure_fbo[write])
                bind(pressure_progs[1], "uP", pressure_tex[read], 0)
                GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
                read = write
            GL.glUseProgram(pressure_progs[2])
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, correction_fbo)
            bind(pressure_progs[2], "uP", pressure_tex[read], 0)
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
            GL.glFinish()
            step_ms.append((time.perf_counter() - begin) * 1000)
            current = 1 - current
            if args.sequence_dir and ((step + 1) % capture_every == 0 or step + 1 == args.steps):
                frame, elapsed = present_frame(render_prog, present_prog, projected_fbo,
                                               projected_tex, states[current], empty, object_tex, args.zoom, args.source_scale, smoke_light)
                render_ms.append(elapsed)
                name = f"frame-{len(frame_records) + 1:04d}.png"
                frame.save(args.sequence_dir / name)
                frame_records.append({"file": name, "step": step + 1, "time_s": (step + 1) / 30.})
            error = int(GL.glGetError())
            if error:
                errors.append({"step": step + 1, "code": error})
        frame, elapsed = present_frame(render_prog, present_prog, projected_fbo,
                                       projected_tex, states[current], empty, object_tex, args.zoom, args.source_scale, smoke_light)
        render_ms.append(elapsed)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        frame.save(args.output)
        renderer = GL.glGetString(GL.GL_RENDERER).decode("utf-8", "replace")
        final_error = int(GL.glGetError())
        if final_error:
            errors.append({"step": args.steps, "code": final_error})
        measured = step_ms[min(args.steps // 5, len(step_ms) - 1):]
        report = {"path": str(args.output), "dimensions": [VOLUME.OUT_W, VOLUME.OUT_H],
                  "steps": args.steps, "simulated_seconds": args.steps / 30.,
                  "expansion": args.expansion, "ambient_forces": args.ambient_forces,
                  "mipmapped_noise": uses_mipmapped_noise, "force_object_shader": args.force_object_shader,
                  "source_scale": args.source_scale, "source_lift": args.source_lift,
                  "source_feed": args.source_feed, "zoom": args.zoom,
                  "preset": args.preset, "source_heat": args.source_heat, "cooling_scale": args.cooling_scale,
                  "grid": [VOLUME.WIDTH, VOLUME.HEIGHT, VOLUME.DEPTH], "gpu": renderer,
                  "step_ms_median": round(statistics.median(measured), 2),
                  "step_ms_mean": round(statistics.mean(measured), 2),
                  "step_ms_p95": round(float(np.percentile(measured, 95)), 2),
                  "step_ms_max": round(max(measured), 2),
                  "render_ms_median": round(statistics.median(render_ms), 2),
                  "render_ms_mean": round(statistics.mean(render_ms), 2),
                  "render_ms_p95": round(float(np.percentile(render_ms, 95)), 2),
                  "render_ms_max": round(max(render_ms), 2),
                  "render_ms_samples": render_ms, "step_ms_samples": step_ms,
                  "gl_error": final_error, "gl_error_count": len(errors), "errors": errors,
                  "source_sha256": source_hashes,
                  "fixture_uniforms": {"emitterKind": 1 if args.preset == "campfire" else 0,
                    "sourceEnabled": args.preset == "sigil", "brushActive": args.preset == "campfire",
                    "sourceScale": args.source_scale, "sourceLift": args.source_lift,
                    "sourceHeat": args.source_heat, "coolingScale": args.cooling_scale,
                    "fuelProfile": [args.source_feed, 1., 1.], "visibleEmitter": 1 if args.preset == "campfire" else 0,
                    "vortexOrigin": vortex_origin, "vortexSpan": vortex_span,
                    "sourcePosition": [.5, 1.05 / 7.875], "viewZoom": args.zoom,
                    "viewPan": [0., -1.], "roomEnabled": 0, "flameTint": [1., 1., 1.], "tintStrength": 0},
                  "noise_basis": "production fire.js hash/valueNoise and 64-cubed turbulence, exact JS byte generation",
                  "noise_sha256": hashlib.sha256(noise_data.tobytes()).hexdigest(),
                  "turbulence_sha256": hashlib.sha256(turbulence_data.tobytes()).hexdigest(),
                  "scope": "Native GLES 3 fixed-step solver, actual overhead soot shadow gather/prefix passes and isolated black-room projection/props; no actual room light, browser pacing, presentation composition or mobile cost."}
        if args.sequence_dir:
            report.update(sequence_artifacts(args.sequence_dir, frame_records, args.capture_fps))
            report["capture_fps"] = args.capture_fps
            report["frame_count"] = len(frame_records)
            report["frames"] = frame_records
            (args.sequence_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
            report["report"] = str(args.report)
        # The complete trace stays on disk; return only bounded artifact metadata.
        summary = {key: value for key, value in report.items() if key not in ("frames", "errors", "source_sha256", "render_ms_samples", "step_ms_samples")}
        print(json.dumps(summary))
        if errors:
            raise RuntimeError(f"OpenGL reported {len(errors)} errors; inspect the saved report")
    finally:
        glfw.destroy_window(window)
        glfw.terminate()


if __name__ == "__main__":
    main()
