"""Preflight and supervise the bounded native solver -> mesh -> Cycles pipeline.

Use --dry-run to inspect dependencies without creating an output directory.
Use --output for a fresh revision; existing simulations are never overwritten.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def resolve_tool(value: str, name: str) -> str:
    """Accept PATH executables, explicit paths, and environment overrides."""
    found = shutil.which(value)
    if found:
        return found
    candidate = Path(value).expanduser()
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate.resolve())
    raise ValueError(f"{name} executable not found: {value!r}. Set --{name.lower()} or {name.upper()}_BIN.")


def resolve_input(value: str | None, base: Path, fallback: Path) -> Path:
    """Relocate legacy developer-machine references to the retained inputs."""
    if value:
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = base / candidate
        if candidate.is_dir():
            return candidate.resolve()
    return fallback.resolve()


def validate_config(config: dict) -> None:
    for key in ("h", "spaceScale", "timeScale"):
        value = config.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"Water config {key} must be a positive finite number.")
    for key in ("nx", "ny", "nz", "frames"):
        value = config.get(key)
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"Water config {key} must be a positive integer.")
    for key in ("origin", "extent"):
        values = config.get(key)
        if not isinstance(values, list) or len(values) != 3 or any(
                not isinstance(value, (int, float)) or not math.isfinite(value) for value in values):
            raise ValueError(f"Water config {key} must contain three finite coordinates.")
    for axis, cells in enumerate((config["nx"], config["ny"], config["nz"])):
        extent = config["extent"][axis]
        if not math.isclose(extent, cells * config["h"], rel_tol=1e-6, abs_tol=1e-8):
            raise ValueError("Water config extent must agree with its grid dimensions and h.")
        if not 0 <= config["origin"][axis] < extent:
            raise ValueError("Water config origin must lie inside the simulation domain.")


def make_plan(args: argparse.Namespace) -> dict:
    mode = "full" if args.full else "cpu"
    template = (args.input_root or ROOT / "sigil-02-active-elements" / f"water-{mode}").resolve()
    output = (args.output or template).resolve()
    config_path = output / "config.json" if (output / "config.json").is_file() else template / "config.json"
    if not config_path.is_file():
        raise ValueError(f"Missing water config: {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_config(config)
    fallback = ROOT / "sigil-02-bending-ground" / mode
    force_root = args.force_root.resolve() if args.force_root else resolve_input(config.get("forceRoot"), config_path.parent, fallback)
    source_root = resolve_input(config.get("sourceRoot"), config_path.parent, fallback)
    inputs = {}
    for name in ("parcels.f32", "guides.npz"):
        candidates = [output / name, template / name, source_root / name]
        inputs[name] = next((p for p in candidates if p.is_file()), candidates[1])
    missing = [str(p) for p in inputs.values() if not p.is_file()]
    missing += [str(force_root / f"guide-{axis}.f32") for axis in range(3)
                if not (force_root / f"guide-{axis}.f32").is_file()]
    if missing:
        raise ValueError("Missing retained simulation inputs:\n  " + "\n  ".join(missing)
                         + "\nRestore them first: python scripts/fetch_assets.py --all")
    parcel_bytes = inputs["parcels.f32"].stat().st_size
    if not parcel_bytes or parcel_bytes % 36:
        raise ValueError("Initial parcels must contain nonempty 9-float records.")
    force_bytes = (config["nx"] + 1) * (config["ny"] + 1) * (config["nz"] + 1) * 8
    if any((force_root / f"guide-{axis}.f32").stat().st_size != force_bytes for axis in range(3)):
        raise ValueError("Guide force dimensions do not match the configured solver grid.")
    if (output / "particles" / "manifest.json").exists() or any((output / "particles").glob("*.gz")):
        raise ValueError(f"Simulation already exists in {output}. Choose a fresh --output directory.")
    node = resolve_tool(args.node, "Node")
    blender = resolve_tool(args.blender, "Blender")
    config.update(forceRoot=str(force_root), sourceRoot=str(source_root))
    switches = ["--full"] if args.full else []
    shared = ["--output", str(output)]
    commands = [
        ("sim", [node, str(ROOT / "sigil_02_active_water.mjs"), *switches, *shared,
                 "--force-root", str(force_root)]),
        ("mesh", [sys.executable, str(ROOT / "sigil_02_active_mesh.py"),
                  *(switches or ["--preview"]), *shared]),
        ("render", [blender, "--background", "--python", str(ROOT / "sigil_02_active_water_render.py"),
                    "--", *(switches or ["--preview"]), *shared]),
    ]
    return dict(output=output, inputs=inputs, config=config, commands=commands)


def prepare_inputs(plan: dict) -> None:
    output = plan["output"]
    output.mkdir(parents=True, exist_ok=True)
    for name, source in plan["inputs"].items():
        destination = output / name
        if not destination.exists():
            shutil.copy2(source, destination)
    # Preserve published configs. Fresh revisions record the actual input roots.
    if not (output / "config.json").exists():
        (output / "config.json").write_text(json.dumps(plan["config"], indent=2) + "\n", encoding="utf-8")


def supervise(commands, output: Path, *, minimum_free_bytes: int = 1024 * 2**20,
              timeout: float = 0, poll_interval: float = .25) -> None:
    """Every worker must succeed, including workers that fail immediately."""
    processes = []
    logs = []
    started = time.monotonic()
    try:
        output.mkdir(parents=True, exist_ok=True)
        for name, command in commands:
            log = (output / f"{name}.log").open("w", encoding="utf-8")
            logs.append(log)
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            processes.append((name, process))
        (output / "processes.json").write_text(json.dumps({name: p.pid for name, p in processes}), encoding="utf-8")
        while True:
            states = [(name, p.poll()) for name, p in processes]
            failures = [(name, code) for name, code in states if code not in (None, 0)]
            if failures:
                detail = ", ".join(f"{name} exited {code} ({output / (name + '.log')})" for name, code in failures)
                raise RuntimeError(f"Water pipeline failed: {detail}")
            if all(code is not None for _, code in states):
                break
            if shutil.disk_usage(output).free < minimum_free_bytes:
                raise RuntimeError("Water pipeline stopped before disk exhaustion.")
            if timeout and time.monotonic() - started > timeout:
                raise RuntimeError(f"Water pipeline exceeded its {timeout:g} second timeout.")
            time.sleep(poll_interval)
    finally:
        for _, process in processes:
            if process.poll() is None:
                process.terminate()
        for _, process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for log in logs:
            log.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Full simulation and GPU rendering; default is a CPU preview.")
    parser.add_argument("--output", type=Path, help="Fresh revision directory.")
    parser.add_argument("--input-root", type=Path, help="Directory containing config, parcels and guides.")
    parser.add_argument("--force-root", type=Path, help="Directory containing guide-0/1/2.f32.")
    parser.add_argument("--node", default=os.environ.get("NODE_BIN", "node"))
    parser.add_argument("--blender", default=os.environ.get("BLENDER_BIN", "blender"))
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and tools and print commands without writing files.")
    parser.add_argument("--minimum-free-mb", type=int, default=1024)
    parser.add_argument("--timeout", type=float, default=0, help="Maximum run time in seconds; zero leaves it unbounded.")
    args = parser.parse_args(argv)
    if args.minimum_free_mb < 0 or args.timeout < 0:
        parser.error("Disk reserve and timeout must be nonnegative.")
    try:
        plan = make_plan(args)
        if args.dry_run:
            print(json.dumps(dict(output=str(plan["output"]), commands=dict(plan["commands"])), indent=2))
            return 0
        prepare_inputs(plan)
        supervise(plan["commands"], plan["output"], minimum_free_bytes=args.minimum_free_mb * 2**20, timeout=args.timeout)
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print("Full water sequence complete." if args.full else "CPU water motion preview complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
