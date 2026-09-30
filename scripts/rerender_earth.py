"""Fresh Blender rendering of the current Earth 02 film's physical scene.

The original r6 edit reverses a Bullet breakup for its entrance. This script
rebuilds the original geometry/material/physics scene, renders its physical
poses again, and applies that documented 300-frame editorial mapping. It never
reads the old MP4. Benchmarking is the default; use --mode full deliberately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "sigil_02_ground_earth_render.py"
INPUTS = {
    "sigil-02-coherent/earth-geometry.json": "88ac8f154e55766ecace29c87cf9739ffe120c6c35eb74e9357fe15f0de38eaa",
    "sigil-02-repair/scans/rock_09/textures/rock_09_arm_2k.jpg": "eaedeb8428079a27bc5e290a61375454035b5fcfb1e9c7d16ce4bc85313789da",
    "sigil-02-repair/scans/rock_09/textures/rock_09_diff_2k.jpg": "657406a77530db692061b475681f98cbf1c67be81a5c422830dbe6eb36df813a",
    "sigil-02-repair/scans/rock_09/textures/rock_09_nor_gl_2k.jpg": "944b7763b6431671e07b4e7ebe082cf747e791513e27c830a3bb2dbee0246614",
}
FRAME_MAP = list(range(330, 209, -1)) + list(range(211, 390))
assert len(FRAME_MAP) == 300
assert FRAME_MAP[:121] == list(range(330, 209, -1))
assert FRAME_MAP[121:] == list(range(211, 390))
assert FRAME_MAP[153:] == list(range(243, 390))
assert set(FRAME_MAP) == set(range(210, 390))


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def parse_film_frames(value: str) -> list[int]:
    """Validate final film IDs before creating files or importing Blender."""
    fields = value.split(",")
    if any(not field.strip() for field in fields):
        raise argparse.ArgumentTypeError("film frames must be a nonempty comma-separated list")
    try:
        frames = [int(field.strip()) for field in fields]
    except ValueError as error:
        raise argparse.ArgumentTypeError("film frames must be integer IDs") from error
    if any(frame < 0 or frame >= len(FRAME_MAP) for frame in frames):
        raise argparse.ArgumentTypeError("film frames must lie between 0 and 299")
    if len(set(frames)) != len(frames):
        raise argparse.ArgumentTypeError("film frames must not contain duplicate IDs")
    return sorted(frames)


def output_frame_ids(args) -> list[int]:
    return list(range(len(FRAME_MAP))) if args.film_frames is None else args.film_frames


def scene_frames_for_output(indices) -> set[int]:
    return {FRAME_MAP[index] + 1 for index in indices}


def arguments(values=None):
    if values is None:
        values = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=ROOT / "work/element-motion")
    parser.add_argument("--input-root", type=Path, default=ROOT / "work/element-motion")
    parser.add_argument("--output", type=Path, default=ROOT / "work/rerenders/earth")
    parser.add_argument("--mode", choices=("benchmark", "full"), default="benchmark")
    parser.add_argument("--engine", choices=("cycles", "eevee"), default="cycles")
    parser.add_argument("--benchmark-frames", type=int, nargs="+", default=[241, 300], help="One-based scene frames, 1..390.")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--no-motion-blur", action="store_true")
    parser.add_argument("--skip-encode", action="store_true")
    parser.add_argument("--film-frames", type=parse_film_frames,
                        help="Selected zero-based final film IDs, e.g. 0,120,299; requires --mode full --skip-encode.")
    parser.add_argument("--film-name", default="earth-02-r7-cpu720.mp4")
    parser.add_argument("--preflight", action="store_true", help="Verify inputs without importing Blender.")
    args = parser.parse_args(values)
    for name in ("width", "height", "samples", "threads"):
        if getattr(args, name) <= 0:
            parser.error(f"{name} must be positive")
    if any(frame < 1 or frame > 390 for frame in args.benchmark_frames):
        parser.error("benchmark frames must lie between 1 and 390")
    if Path(args.film_name).name != args.film_name or not args.film_name.endswith(".mp4"):
        parser.error("film name must be a local .mp4 filename")
    if args.film_frames is not None:
        if args.mode != "full":
            parser.error("--film-frames requires --mode full")
        if not args.skip_encode:
            parser.error("--film-frames requires --skip-encode; selected frames cannot be encoded as a complete film")
    return args


def preflight(args):
    source_path = args.source_root / SOURCE_NAME
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    verified = {}
    for relative, expected in INPUTS.items():
        path = args.input_root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = digest(path)
        if actual != expected:
            raise RuntimeError(f"Input digest differs: {relative}")
        verified[relative] = actual
    geometry = json.loads((args.input_root / "sigil-02-coherent/earth-geometry.json").read_text())
    return source_path, verified, len(geometry["pieces"])


def iter_action_fcurves(obj):
    """Keep the source's interpolation settings across legacy/layered actions."""
    action = obj.animation_data.action
    curves = getattr(action, "fcurves", None)
    if curves is not None:
        return curves
    result = []
    slot = obj.animation_data.action_slot
    for layer in action.layers:
        for strip in layer.strips:
            bag = strip.channelbag(slot)
            if bag is not None:
                result.extend(bag.fcurves)
    return result


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f"Original renderer contract changed: {old[:70]!r}")
    return text.replace(old, new, 1)


def ensure_render_settings(output: Path, mode: str, image_directory: Path, settings: dict):
    """Prevent resuming images produced by a different renderer or quality."""
    receipt = output / f"{mode}-settings.json"
    if receipt.exists():
        if json.loads(receipt.read_text(encoding="utf-8")) != settings:
            raise RuntimeError("Existing images use different render settings; choose a fresh --output directory.")
    elif any(image_directory.glob("*.png")):
        raise RuntimeError("Existing images have no settings receipt; choose a fresh --output directory.")
    else:
        receipt.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def build_scene(args, source_path):
    import bpy

    source = source_path.read_text(encoding="utf-8")
    marker = "s.render.use_motion_blur=True;s.render.motion_blur_shutter=.35;start=time.time();rows=[]"
    if source.count(marker) != 1:
        raise RuntimeError("Original scene/render loop boundary was not found")
    setup = source.split(marker, 1)[0]
    setup = replace_once(setup,
                         "R=Path(__file__).resolve().parent;O=R/'sigil-02-bending-ground';full='--full' in sys.argv",
                         "R=args.input_root.resolve();O=args.output.resolve();full=False")
    setup = replace_once(setup, "s.cycles.denoiser='OPTIX'", "s.cycles.denoiser='OPENIMAGEDENOISE'")
    setup = replace_once(setup,
                         "prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()\nfor device in prefs.devices:device.use=device.type=='OPTIX'\n",
                         "")
    setup = setup.replace("o.animation_data.action.fcurves", "iter_action_fcurves(o)")
    setup = setup.replace("out.mkdir(exist_ok=True)", "out.mkdir(parents=True,exist_ok=True)")
    if bpy.context.scene.world is None:
        bpy.context.scene.world = bpy.data.worlds.new("Earth studio world")
    namespace = {"__file__": str(source_path), "args": args, "iter_action_fcurves": iter_action_fcurves}
    exec(compile(setup, str(source_path), "exec"), namespace)
    scene = namespace["s"]
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.adaptive_threshold = .02
    if args.engine == "eevee":
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.eevee.taa_render_samples = args.samples
        scene.eevee.use_gtao = True
        scene.eevee.gtao_distance = .75
        scene.eevee.gtao_quality = 1.0
        scene.eevee.use_raytracing = False
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.threads_mode = "FIXED"
    scene.render.threads = args.threads
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 15
    scene.render.use_motion_blur = not args.no_motion_blur
    scene.render.motion_blur_shutter = .35
    scene.frame_start = 1
    scene.frame_end = 390
    return bpy, scene, namespace["objects"]


def checked_run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:])
    return result.stdout


def update_trajectory_digest(trajectory, frame: int, transforms):
    """Hash canonical float32 translations/quaternions in creation order."""
    trajectory.update(struct.pack("<I", frame))
    for matrix in transforms:
        quaternion = list(matrix.to_quaternion())
        # q and -q represent the same rotation. Give the first nonzero
        # component a positive sign, including exact half-turns.
        first = next((value for value in quaternion if value != 0), 0)
        if first < 0:
            quaternion = [-value for value in quaternion]
        values = list(matrix.translation) + quaternion
        values = [0.0 if value == 0 else value for value in values]
        if not all(math.isfinite(value) for value in values):
            raise RuntimeError(f"Nonfinite rigid transform at scene frame {frame}")
        trajectory.update(struct.pack("<7f", *values))


def copy_output_frames(source_frames: Path, output_frames: Path, indices):
    output_frames.mkdir(exist_ok=True)
    for index in indices:
        source = source_frames / f"{FRAME_MAP[index]:06d}.png"
        target = output_frames / f"{index:04d}.png"
        if not target.exists():
            try:
                os.link(source, target)
            except OSError:
                shutil.copy2(source, target)


def encode(args):
    movie = args.output / args.film_name
    checked_run(["ffmpeg", "-v", "error", "-y", "-framerate", "30", "-i",
                 str(args.output / "frames" / "%04d.png"), "-frames:v", "300",
                 "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-threads", "2", str(movie)])
    checked_run(["ffmpeg", "-v", "error", "-i", str(movie), "-f", "null", "-"])
    metadata = json.loads(checked_run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                      "-show_entries", "stream=width,height,nb_frames,avg_frame_rate:format=duration",
                                      "-of", "json", str(movie)]))
    stream = metadata["streams"][0]
    if (stream["width"], stream["height"], stream["nb_frames"], stream["avg_frame_rate"]) != (args.width, args.height, "300", "30/1"):
        raise RuntimeError(f"Unexpected encoded film: {metadata}")
    return {"file": str(movie), "sha256": digest(movie), "metadata": metadata, "fullyDecoded": True}


def main():
    args = arguments()
    selected_output_frames = output_frame_ids(args)
    source_path, inputs, piece_count = preflight(args)
    if args.preflight:
        print(json.dumps({"inputs": inputs, "fractures": piece_count,
                          "uniqueSourceFrames": len(scene_frames_for_output(selected_output_frames)),
                          "outputFrames": len(selected_output_frames),
                          "selectedOutputFrames": selected_output_frames}, indent=2))
        return
    args.output.mkdir(parents=True, exist_ok=True)
    report_path = args.output / ("benchmark.json" if args.mode == "benchmark" else "render-report.json")
    source_frames = args.output / ("benchmark" if args.mode == "benchmark" else "source-frames")
    source_frames.mkdir(exist_ok=True)
    report = {
        "mode": args.mode,
        "renderer": "Blender Cycles CPU with OpenImageDenoise" if args.engine == "cycles" else "Blender EEVEE rasterization",
        "engine": args.engine,
        "lightTransport": "Path-traced direct/indirect lighting" if args.engine == "cycles" else "Same studio lights with rasterized shadows and ambient occlusion; indirect GI differs from Cycles.",
        "source": str(source_path),
        "sourceSha256": digest(source_path),
        "runnerSha256": digest(Path(__file__)),
        "inputHashes": inputs,
        "resolution": [args.width, args.height],
        "samples": args.samples,
        "threads": args.threads,
        "fps": 30,
        "outputFrameMap": FRAME_MAP,
        "selectedOutputFrames": selected_output_frames,
        "method": "Fresh geometry, Bullet dynamics and Blender rendering; original r6 reversed-breakup editorial mapping.",
        "newRenderedPixels": True,
        "oldVideoFramesRead": False,
        "fallSourceFrames": [243, 389],
        "fallOutputFrames": [153, 299],
        "forwardFallFrameMapPreserved": True,
        "authoredEntrance": "Reverse playback of newly rendered simulated breakup, not a newly forward-solved gathering lift.",
        "frames": [],
    }
    setup_started = time.perf_counter()
    bpy, scene, objects = build_scene(args, source_path)
    report["blenderVersion"] = bpy.app.version_string
    report["sceneSetupSeconds"] = time.perf_counter() - setup_started
    report["fractures"] = piece_count
    report["rigidObjects"] = len(objects)
    initial_masses = [obj.rigid_body.mass for obj in objects]
    report["totalRigidMass"] = sum(initial_masses)
    settings = {key: report[key] for key in ("blenderVersion", "engine", "sourceSha256", "runnerSha256",
                                            "inputHashes", "resolution", "samples")}
    settings["motionBlur"] = not args.no_motion_blur
    ensure_render_settings(args.output, args.mode, source_frames, settings)
    wanted = set(args.benchmark_frames) if args.mode == "benchmark" else scene_frames_for_output(selected_output_frames)
    physics_end = max(wanted) if args.mode == "benchmark" else 390
    trajectory = hashlib.sha256()
    trajectory.update(json.dumps([obj.name for obj in objects], separators=(",", ":")).encode("utf-8"))
    started = time.perf_counter()
    for frame in range(1, physics_end + 1):
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        transforms = [obj.evaluated_get(depsgraph).matrix_world for obj in objects]
        if not all(math.isfinite(value) for matrix in transforms for row in matrix for value in row):
            raise RuntimeError(f"Nonfinite rigid transform at scene frame {frame}")
        if [obj.rigid_body.mass for obj in objects] != initial_masses:
            raise RuntimeError(f"Rigid-body mass changed at scene frame {frame}")
        update_trajectory_digest(trajectory, frame, transforms)
        if frame not in wanted:
            continue
        target = source_frames / f"{frame - 1:06d}.png"
        render_started = time.perf_counter()
        reused = target.exists()
        if not reused:
            scene.render.filepath = str(target)
            bpy.ops.render.render(write_still=True)
        row = {"sceneFrame": frame, "sourceFrame": frame - 1, "path": str(target),
               "renderSeconds": time.perf_counter() - render_started,
               "reusedExistingImage": reused,
               "finiteTransforms": True,
               "rigidMassUnchanged": True,
               "minCentroidZ": min(matrix.translation.z for matrix in transforms)}
        report["frames"].append(row)
        report["elapsedSeconds"] = time.perf_counter() - started
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("EARTH_RENDER " + json.dumps(row), flush=True)
    if args.mode == "full":
        output_frames = args.output / "frames"
        copy_output_frames(source_frames, output_frames, selected_output_frames)
        if not args.skip_encode:
            report["film"] = encode(args)
    report["physicsFrames"] = physics_end
    report["physicsTrajectorySha256"] = trajectory.hexdigest()
    report["selectionComplete"] = True
    report["complete"] = args.film_frames is None
    report["elapsedSeconds"] = time.perf_counter() - started
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "complete": report["complete"],
                      "selectionComplete": True, "elapsedSeconds": report["elapsedSeconds"]}), flush=True)


if __name__ == "__main__":
    main()
