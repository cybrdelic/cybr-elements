"""CYBR / ELEMENTS — reference-driven horizontal flamethrower study.

This is an offline visual-effects simulation built from the repository's existing
reactive-flow approach.  It is intentionally a graphics model: projected
low-Mach flow, limited MacCormack scalar transport, fuel/oxidizer reaction,
buoyancy, vorticity confinement and volumetric radiation.  It is not a
calibrated combustion, weapon, or safety model.

Visual target
-------------
A sustained horizontal flame jet in a dark studio: a compact white/yellow core
at the nozzle, turbulent orange roll-ups, darker soot at the envelope, visible
heat/light on a steel target plate, and a restrained floor reflection.

The scene is generated from simulation state.  No image-generation model,
painted flame card, frame fitting, reverse playback, or per-frame silhouette
mask is used.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

os.environ.setdefault("OMP_NUM_THREADS", "2")

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
DEFAULT_OUTPUT = REPO / "outputs/cybrdelic-type/elements/motion/subelements/flamethrower-reference.mp4"
DEFAULT_WORK = ROOT / "run"


@dataclass(frozen=True)
class Domain:
    x0: float = 0.0
    x1: float = 6.2
    y0: float = -1.0
    y1: float = 1.0
    z0: float = 0.0
    z1: float = 3.0

    @property
    def extent(self) -> Tuple[float, float, float]:
        return (self.x1 - self.x0, self.y1 - self.y0, self.z1 - self.z0)


@dataclass(frozen=True)
class SceneLayout:
    nozzle_x: float = 0.56
    nozzle_z: float = 1.42
    nozzle_radius: float = 0.105
    plate_x: float = 5.05
    plate_half_y: float = 0.84
    plate_z0: float = 0.48
    plate_z1: float = 2.35
    plate_thickness: float = 0.12
    viewport_x0: float = -0.62
    viewport_x1: float = 6.28
    image_top_fraction: float = 0.07
    image_bottom_fraction: float = 0.86


@dataclass
class Buffers:
    state: torch.Tensor
    grid: torch.Tensor
    x: torch.Tensor
    y: torch.Tensor
    z: torch.Tensor
    h: torch.Tensor
    step_scale: torch.Tensor
    sponge: torch.Tensor
    k: torch.Tensor
    k2: torch.Tensor
    plate_mask: torch.Tensor
    impact_zone: torch.Tensor
    scene_base: torch.Tensor
    scene_plate_mask: torch.Tensor
    scene_floor_mask: torch.Tensor
    screen_x: torch.Tensor
    screen_z: torch.Tensor


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--name", default="flamethrower-reference")
    p.add_argument("--size", type=int, nargs=3, default=[224, 96, 128], metavar=("X", "Y", "Z"))
    p.add_argument("--seconds", type=float, default=4.0)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--substeps", type=int, default=4)
    p.add_argument("--jet-speed", type=float, default=17.5)
    p.add_argument("--fuel", type=float, default=0.96)
    p.add_argument("--target", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--pilot", action="store_true", help="Render 1280x720 instead of 1920x1080")
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--work", type=Path, default=DEFAULT_WORK)
    p.add_argument("--preview-every", type=int, default=15)
    p.add_argument("--save-state-every", type=int, default=0,
                   help="If non-zero, save temperature/soot/reaction every N frames")
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--memory-budget-gib", type=float, default=7.2)
    return p.parse_args()


def require_environment(a: argparse.Namespace) -> None:
    if not a.name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("--name must contain only letters, digits, '-' or '_'")
    if any(n < 24 for n in a.size):
        raise ValueError("Each grid dimension must be >= 24")
    if a.seconds <= 0 or a.fps <= 0 or a.substeps <= 0:
        raise ValueError("seconds, fps and substeps must be positive")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the production solve")
    a.work.mkdir(parents=True, exist_ok=True)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(a.work).free < 1024**3:
        raise RuntimeError("At least 1 GiB of free space is required")
    if a.output.exists():
        raise RuntimeError(f"Refusing to overwrite existing output: {a.output}")


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 0.0
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def valve(t: float, duration: float) -> float:
    on = smoothstep(0.02, 0.28, t)
    off = 1.0 - smoothstep(max(0.0, duration - 0.42), max(0.01, duration - 0.08), t)
    # Tiny pressure-pump modulation.  It changes the source, not the rendered image.
    flutter = 0.96 + 0.025 * math.sin(2.0 * math.pi * 7.1 * t) + 0.015 * math.sin(2.0 * math.pi * 13.7 * t + 0.8)
    return max(0.0, on * off * flutter)


def derivative(q: torch.Tensor, axis: int, spacing: torch.Tensor) -> torch.Tensor:
    return (torch.roll(q, -1, axis) - torch.roll(q, 1, axis)) / (2.0 * spacing)


def divergence(v: torch.Tensor, h: torch.Tensor) -> torch.Tensor:
    return (
        derivative(v[0], 2, h[0])
        + derivative(v[1], 1, h[1])
        + derivative(v[2], 0, h[2])
    )


def advect(q: torch.Tensor, vel: torch.Tensor, grid: torch.Tensor, step_scale: torch.Tensor, dt: float, sign: float = 1.0) -> torch.Tensor:
    lookup = grid - (vel * step_scale * (dt * sign)).permute(0, 2, 3, 4, 1)
    return F.grid_sample(q, lookup, mode="bilinear", padding_mode="border", align_corners=True)


def make_projection_symbols(shape: Tuple[int, int, int], h: torch.Tensor, device: str) -> Tuple[torch.Tensor, torch.Tensor]:
    Z, Y, X = shape
    fz = torch.fft.fftfreq(Z, device=device)
    fy = torch.fft.fftfreq(Y, device=device)
    fx = torch.fft.rfftfreq(X, device=device)
    kz, ky, kx = torch.meshgrid(fz, fy, fx, indexing="ij")
    # Fourier symbols matched to the centered finite-difference derivative used
    # above.  This avoids measuring a different divergence than we project.
    k = torch.stack(
        [
            torch.sin(2.0 * math.pi * kx) / h[0],
            torch.sin(2.0 * math.pi * ky) / h[1],
            torch.sin(2.0 * math.pi * kz) / h[2],
        ]
    )
    k2 = (k * k).sum(0).clamp_min(1e-12)
    return k, k2


def build_scene_buffers(
    device: str,
    width: int,
    height: int,
    domain: Domain,
    layout: SceneLayout,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    u = torch.linspace(0.0, 1.0, width, device=device)[None, :]
    v = torch.linspace(0.0, 1.0, height, device=device)[:, None]
    wx = layout.viewport_x0 + u * (layout.viewport_x1 - layout.viewport_x0)

    top = layout.image_top_fraction
    bottom = layout.image_bottom_fraction
    rel = ((v - top) / (bottom - top)).clamp(0.0, 1.0)
    wz = domain.z1 - rel * (domain.z1 - domain.z0)

    # Dark neutral studio, kept above zero to preserve soot silhouettes.
    vertical = (1.0 - v).pow(1.35)
    scene = torch.empty((3, height, width), device=device)
    scene[0] = 0.0060 + vertical * 0.0035
    scene[1] = 0.0065 + vertical * 0.0038
    scene[2] = 0.0075 + vertical * 0.0045

    floor_y = int(round(height * bottom))
    floor = torch.zeros((height, width), dtype=torch.bool, device=device)
    floor[floor_y:, :] = True
    floor_grad = ((torch.arange(height, device=device)[:, None] - floor_y) / max(1, height - floor_y)).clamp(0, 1)
    floor_luma = 0.013 + 0.018 * (1.0 - floor_grad).pow(2.0)
    scene = torch.where(floor[None], torch.stack([floor_luma * 0.95, floor_luma, floor_luma * 1.04]).expand(-1, -1, width), scene)

    # Analytic side-view prop geometry.  The fire itself never uses these masks.
    nozzle_body = (wx >= -0.55) & (wx <= layout.nozzle_x - 0.09) & ((wz - layout.nozzle_z).abs() <= 0.125)
    nozzle_taper = (wx > layout.nozzle_x - 0.09) & (wx <= layout.nozzle_x + 0.025) & ((wz - layout.nozzle_z).abs() <= 0.100)
    nozzle_ring = (wx > layout.nozzle_x - 0.17) & (wx < layout.nozzle_x - 0.08) & ((wz - layout.nozzle_z).abs() <= 0.145)
    nozzle_mask = nozzle_body | nozzle_taper | nozzle_ring

    metal_highlight = ((wz - (layout.nozzle_z + 0.05)) / 0.18).clamp(-1, 1)
    metal = torch.stack([
        0.030 + 0.035 * (1.0 - metal_highlight.abs()),
        0.032 + 0.038 * (1.0 - metal_highlight.abs()),
        0.035 + 0.044 * (1.0 - metal_highlight.abs()),
    ]).expand(-1, height, width)
    scene = torch.where(nozzle_mask[None], metal, scene)
    ring = torch.stack([
        torch.full((height, width), 0.070, device=device),
        torch.full((height, width), 0.051, device=device),
        torch.full((height, width), 0.026, device=device),
    ])
    scene = torch.where(nozzle_ring[None], ring, scene)

    plate = (
        (wx >= layout.plate_x - 0.035)
        & (wx <= layout.plate_x + 0.245)
        & (wz >= layout.plate_z0)
        & (wz <= layout.plate_z1)
    )
    # Slight bevel/darker right edge gives the target some thickness in side view.
    plate_edge = plate & (wx >= layout.plate_x + 0.18)
    plate_base = torch.stack([
        torch.full((height, width), 0.040, device=device),
        torch.full((height, width), 0.042, device=device),
        torch.full((height, width), 0.046, device=device),
    ])
    scene = torch.where(plate[None], plate_base, scene)
    edge_base = plate_base * torch.tensor([0.55, 0.56, 0.60], device=device)[:, None, None]
    scene = torch.where(plate_edge[None], edge_base, scene)

    # Two small feet, matching the industrial test-stand read of the reference.
    foot1 = (wx >= layout.plate_x - 0.02) & (wx <= layout.plate_x + 0.12) & (wz >= 0.13) & (wz <= 0.24)
    foot2 = (wx >= layout.plate_x + 0.17) & (wx <= layout.plate_x + 0.34) & (wz >= 0.13) & (wz <= 0.24)
    leg1 = (wx >= layout.plate_x + 0.01) & (wx <= layout.plate_x + 0.07) & (wz >= 0.20) & (wz <= layout.plate_z0)
    leg2 = (wx >= layout.plate_x + 0.20) & (wx <= layout.plate_x + 0.26) & (wz >= 0.20) & (wz <= layout.plate_z0)
    stand = foot1 | foot2 | leg1 | leg2
    scene = torch.where(stand[None], plate_base * 0.78, scene)

    # Vignette is applied in linear light, not as an opaque overlay.
    xnorm = (u - 0.5) / 0.5
    ynorm = (v - 0.5) / 0.5
    vignette = (1.0 - 0.18 * (xnorm * xnorm + ynorm * ynorm).clamp(0, 1)).clamp(0.78, 1.0)
    scene *= vignette
    return scene, plate, floor, wx.expand(height, -1), wz.expand(-1, width)


def build_buffers(
    a: argparse.Namespace,
    device: str,
    width: int,
    height: int,
    domain: Domain,
    layout: SceneLayout,
) -> Buffers:
    X, Y, Z = a.size
    shape = (Z, Y, X)
    ex, ey, ez = domain.extent
    h = torch.tensor([ex / (X - 1), ey / (Y - 1), ez / (Z - 1)], device=device)

    zz_n, yy_n, xx_n = torch.meshgrid(
        torch.linspace(-1.0, 1.0, Z, device=device),
        torch.linspace(-1.0, 1.0, Y, device=device),
        torch.linspace(-1.0, 1.0, X, device=device),
        indexing="ij",
    )
    grid = torch.stack([xx_n, yy_n, zz_n], dim=-1)[None]
    x = domain.x0 + (xx_n + 1.0) * ex * 0.5
    y = domain.y0 + (yy_n + 1.0) * ey * 0.5
    z = domain.z0 + (zz_n + 1.0) * ez * 0.5
    step_scale = (2.0 / torch.tensor([ex, ey, ez], device=device)).view(1, 3, 1, 1, 1)

    state = torch.zeros((1, 8, Z, Y, X), device=device)
    # velocity xyz, fuel, oxygen, normalized temperature, soot, reaction rate
    state[:, 4] = 1.0

    # Open inflow on the left, absorbing outlet on the right, side/top sponge.
    sx = ((domain.x1 - x) / 0.38).clamp(0, 1)
    sy = ((1.0 - (y.abs() / max(abs(domain.y0), abs(domain.y1)))) / 0.12).clamp(0, 1)
    sz_top = ((domain.z1 - z) / 0.32).clamp(0, 1)
    sz_bottom = (z / 0.12).clamp(0, 1)
    sponge = torch.minimum(torch.minimum(sx, sy), torch.minimum(sz_top, sz_bottom))[None, None]

    k, k2 = make_projection_symbols(shape, h, device)

    plate_x = layout.plate_x
    px = ((x - plate_x) / (layout.plate_thickness * 0.5)).abs()
    py = (y / layout.plate_half_y).abs()
    pz_mid = (layout.plate_z0 + layout.plate_z1) * 0.5
    pz_half = (layout.plate_z1 - layout.plate_z0) * 0.5
    pz = ((z - pz_mid) / pz_half).abs()
    plate_mask = ((px <= 1.0) & (py <= 1.0) & (pz <= 1.0)).float()
    if not a.target:
        plate_mask.zero_()

    impact_zone = (
        torch.exp(-((x - (plate_x - 0.26)) / 0.34).pow(2) * 1.8)
        * torch.exp(-(y / 0.72).pow(8))
        * torch.exp(-((z - pz_mid) / 0.94).pow(8))
    )
    if not a.target:
        impact_zone.zero_()

    scene_base, scene_plate_mask, scene_floor_mask, screen_x, screen_z = build_scene_buffers(
        device, width, height, domain, layout
    )

    return Buffers(
        state=state,
        grid=grid,
        x=x,
        y=y,
        z=z,
        h=h,
        step_scale=step_scale,
        sponge=sponge,
        k=k,
        k2=k2,
        plate_mask=plate_mask,
        impact_zone=impact_zone,
        scene_base=scene_base,
        scene_plate_mask=scene_plate_mask,
        scene_floor_mask=scene_floor_mask,
        screen_x=screen_x,
        screen_z=screen_z,
    )


def inject_and_react(
    b: Buffers,
    a: argparse.Namespace,
    layout: SceneLayout,
    t: float,
    dt: float,
) -> None:
    state = b.state
    fuel, oxygen, temp, soot = [state[0, c] for c in [3, 4, 5, 6]]
    v = state[0, :3]

    gate = valve(t, a.seconds)
    px = b.x - layout.nozzle_x
    ry = b.y
    rz = b.z - layout.nozzle_z
    r = torch.sqrt(ry * ry + rz * rz).clamp_min(1e-6)

    # A short rounded source volume just outside the nozzle.  The eighth-power
    # radial profile gives a pressurized core without a visibly hard cylinder.
    axial = torch.exp(-((px - 0.035) / 0.070).pow(4))
    radial = torch.exp(-(r / layout.nozzle_radius).pow(8) * 1.7)
    source = axial * radial * gate
    edge_ring = torch.exp(-((r - layout.nozzle_radius * 0.77) / (layout.nozzle_radius * 0.20)).pow(2)) * axial * gate

    inject = (source * dt * (38.0 + a.jet_speed * 1.55)).clamp(0.0, 1.0)
    fuel.lerp_(torch.full_like(fuel, a.fuel), inject)
    # Fuel-rich center, oxygen-rich shear layer.  This naturally moves the
    # strongest reaction away from a featureless opaque core.
    oxygen.lerp_(torch.full_like(oxygen, 0.08), inject)
    temp.lerp_(torch.full_like(temp, 0.62), inject)
    temp.lerp_(torch.full_like(temp, 1.10), (edge_ring * dt * 20.0).clamp(0, 1))

    theta = torch.atan2(rz, ry)
    fine = (
        0.75 * torch.sin(theta * 5.0 + t * 31.0)
        + 0.45 * torch.sin(theta * 9.0 - t * 47.0)
        + 0.30 * torch.cos((ry + rz) * 53.0 + t * 37.0)
    )
    core_speed = a.jet_speed * (0.97 + 0.045 * math.sin(t * 23.0) + 0.020 * math.sin(t * 61.0 + 0.4))
    v[0].lerp_(torch.full_like(v[0], core_speed) + fine * 0.65, inject)
    swirl = edge_ring * gate
    v[1].add_(swirl * (-rz / r) * (2.8 + 0.9 * math.sin(t * 17.0)) * dt * 18.0)
    v[2].add_(swirl * (ry / r) * (2.8 + 0.9 * math.cos(t * 19.0)) * dt * 18.0)

    activation = ((temp - 0.18) / 0.24).clamp(0, 1)
    mixing = (oxygen * (1.0 - oxygen)).sqrt().clamp(0, 0.5) * 2.0
    rate = 16.0 + 9.0 * mixing
    burn = torch.minimum(fuel, oxygen * 0.72) * (1.0 - torch.exp(-rate * dt)) * activation
    fuel.sub_(burn).clamp_(0, 1.25)
    oxygen.sub_(burn / 0.72).clamp_(0, 1.0)
    temp.add_(burn * 6.25).mul_(math.exp(-0.58 * dt)).clamp_(0, 3.3)
    soot.add_(burn * (0.72 + 0.45 * (1.0 - oxygen))).mul_(math.exp(-0.34 * dt)).clamp_(0, 2.5)
    state[0, 7] = burn / dt


def apply_forces_and_project(
    b: Buffers,
    a: argparse.Namespace,
    layout: SceneLayout,
    dt: float,
) -> float:
    state = b.state
    v = state[0, :3]
    temp = state[0, 5]
    soot = state[0, 6]
    reaction = state[0, 7]

    # Buoyancy remains subordinate to the source momentum near the nozzle and
    # increasingly bends the downstream envelope upward.
    v[2].add_((temp * 2.35 - soot * 0.17) * dt)

    # Broadband deterministic forcing in the shear layer.  It is a body force
    # in the simulation; there is no screen-space displacement of the flame.
    downstream = ((b.x - layout.nozzle_x) / 4.8).clamp(0, 1)
    reactive = (reaction * 0.030 + soot * 0.18).clamp(0, 1)
    turbulence = reactive * downstream
    v[1].add_(turbulence * torch.sin(b.x * 8.7 + b.z * 12.1 + b.y * 19.0) * (0.95 * dt))
    v[2].add_(turbulence * torch.cos(b.x * 10.9 - b.z * 9.3 + b.y * 17.0) * (0.80 * dt))

    if a.target:
        q = b.impact_zone
        # Brinkman-like pre-contact damping plus a resolved deflection force.
        # This is not a cutout in the rendered flame: the scalar field reaches
        # the target, then the flow is decelerated and rolls around it.
        damp = (1.0 - q * (1.0 - math.exp(-7.5 * dt))).clamp(0, 1)
        v[0].mul_(damp)
        ydir = b.y / (b.y.abs() + 0.10)
        zmid = 0.5 * (layout.plate_z0 + layout.plate_z1)
        zdir = (b.z - zmid) / ((b.z - zmid).abs() + 0.12)
        v[1].add_(q * ydir * (5.2 * dt))
        v[2].add_(q * (2.6 + 2.2 * zdir) * dt)

    # Resolved vorticity confinement preserves Kelvin-Helmholtz roll-up at a
    # much lower cost than simply increasing the grid until all scales resolve.
    wx = derivative(v[2], 1, b.h[1]) - derivative(v[1], 0, b.h[2])
    wy = derivative(v[0], 0, b.h[2]) - derivative(v[2], 2, b.h[0])
    wz = derivative(v[1], 2, b.h[0]) - derivative(v[0], 1, b.h[1])
    omega = torch.stack([wx, wy, wz])
    mag = torch.linalg.vector_norm(omega, dim=0)
    grad = torch.stack([
        derivative(mag, 2, b.h[0]),
        derivative(mag, 1, b.h[1]),
        derivative(mag, 0, b.h[2]),
    ])
    grad /= torch.linalg.vector_norm(grad, dim=0).clamp_min(1e-6)
    v.add_(torch.linalg.cross(grad, omega, dim=0) * (0.17 * dt))

    # Absorbing outer shell.  The inlet itself is kept away from the left-edge
    # sponge so its momentum is not artificially attenuated.
    v.mul_(b.sponge[0])

    spectral = torch.fft.rfftn(v, dim=(-3, -2, -1))
    projection = (spectral * b.k).sum(0) / b.k2
    spectral -= b.k * projection

    # Low-Mach thermal expansion.  The mean is removed because the periodic FFT
    # projection cannot represent a net volume source.
    expansion = (reaction * 7.8).clamp(0, 18.0)
    expansion = expansion - expansion.mean()
    spectral += -1j * b.k * (torch.fft.rfftn(expansion) / b.k2)

    # Tiny physical/numerical viscosity damps grid-scale ringing without
    # erasing the resolved turbulent structures.
    spectral *= torch.exp(-b.k2 * (0.000030 * dt))
    v.copy_(torch.fft.irfftn(spectral, s=state.shape[-3:], dim=(-3, -2, -1)))

    if a.target:
        solid = b.plate_mask
        v.mul_(1.0 - solid)
        state[0, 3].mul_(1.0 - solid)
        state[0, 5].mul_(1.0 - solid)
        state[0, 6].mul_(1.0 - solid)
        state[0, 7].mul_(1.0 - solid)
        state[0, 4].lerp_(torch.ones_like(state[0, 4]), solid)

    return float(divergence(state[0, :3], b.h).square().mean().sqrt())


def simulation_step(
    b: Buffers,
    a: argparse.Namespace,
    layout: SceneLayout,
    t: float,
    dt: float,
) -> float:
    state = b.state
    vel = state[:, :3]
    moved = advect(state, vel, b.grid, b.step_scale, dt)

    # Limited MacCormack correction on scalar channels only.  Velocity keeps the
    # stable semi-Lagrangian update; correcting it here tends to amplify pressure
    # ringing in the jet.
    returned = advect(moved, vel, b.grid, b.step_scale, dt, sign=-1.0)
    corrected = moved[:, 3:] + 0.5 * (state[:, 3:] - returned[:, 3:])
    upper = F.max_pool3d(state[:, 3:], 3, stride=1, padding=1)
    lower = -F.max_pool3d(-state[:, 3:], 3, stride=1, padding=1)
    departure = b.grid - (vel * b.step_scale * dt).permute(0, 2, 3, 4, 1)
    upper = F.grid_sample(upper, departure, mode="nearest", padding_mode="border", align_corners=True)
    lower = F.grid_sample(lower, departure, mode="nearest", padding_mode="border", align_corners=True)
    moved[:, 3:] = torch.maximum(lower, torch.minimum(upper, corrected)).clamp_min_(0.0)
    b.state = moved

    inject_and_react(b, a, layout, t, dt)
    div = apply_forces_and_project(b, a, layout, dt)

    # Scalars share the absorbing shell; oxygen is replenished at open bounds.
    b.state[:, 3:4].mul_(b.sponge)
    b.state[:, 5:].mul_(b.sponge)
    b.state[:, 4].lerp_(torch.ones_like(b.state[:, 4]), 1.0 - b.sponge[0, 0])
    return div


def flame_radiance(b: Buffers) -> Tuple[torch.Tensor, torch.Tensor]:
    temp = b.state[0, 5]
    soot = b.state[0, 6]
    reaction = b.state[0, 7].clamp_min(0)

    hot = ((temp - 0.20) / 2.55).clamp(0, 1)
    # Approximate blackbody progression: red -> orange -> yellow -> near-white.
    red = torch.ones_like(hot)
    green = (0.07 + 0.93 * hot.pow(0.72)).clamp(0, 1)
    blue = (0.015 + 0.72 * ((hot - 0.42) / 0.58).clamp(0, 1).pow(1.55)).clamp(0, 1)
    color = torch.stack([red, green, blue], dim=-1)

    # Reaction fronts are luminous; cool soot is primarily absorptive/scattering.
    front = reaction.pow(0.82)
    hot_soot = soot * hot.pow(3.2)
    emission = color * (front * 1.55 + hot_soot * 1.30)[..., None]

    sigma = (soot * 5.8 + reaction * 0.020).clamp(0, 20)

    # Soft key light through the volume.  This affects smoke visibility rather
    # than substituting a fake glow texture for the flame.
    tau_top = torch.flip(torch.cumsum(torch.flip(soot, dims=[0]), dim=0), dims=[0]) * b.h[2] * 3.6
    key = torch.exp(-tau_top)
    ambient = torch.tensor([0.018, 0.020, 0.024], device=temp.device)
    warm = torch.tensor([0.70, 0.20, 0.035], device=temp.device)
    scattering = soot[..., None] * (ambient + key[..., None] * warm * hot[..., None].pow(1.4)) * 0.18
    return emission + scattering, sigma


def integrate_volume(b: Buffers) -> Tuple[torch.Tensor, torch.Tensor]:
    rgb, sigma = flame_radiance(b)
    # Camera looks along +Y through the volume.  March front-to-back over Y.
    dy = b.h[1]
    alpha = 1.0 - torch.exp(-sigma * dy)
    one_minus = (1.0 - alpha).clamp(1e-6, 1.0)
    transmission = torch.cat(
        [torch.ones_like(alpha[:, :1]), torch.cumprod(one_minus[:, :-1], dim=1)],
        dim=1,
    )
    source = rgb * (alpha / sigma.clamp_min(1e-6))[..., None]
    linear = (transmission[..., None] * source).sum(dim=1)  # Z, X, RGB
    trans_final = torch.prod(one_minus, dim=1)             # Z, X
    return linear, trans_final


def separable_box_blur(x: torch.Tensor, radius: int) -> torch.Tensor:
    if radius <= 0:
        return x
    k = radius * 2 + 1
    x = F.avg_pool2d(x, kernel_size=(1, k), stride=1, padding=(0, radius))
    x = F.avg_pool2d(x, kernel_size=(k, 1), stride=1, padding=(radius, 0))
    return x


def resize_volume_to_viewport(
    linear: torch.Tensor,
    trans: torch.Tensor,
    width: int,
    height: int,
    domain: Domain,
    layout: SceneLayout,
) -> Tuple[torch.Tensor, torch.Tensor, Tuple[int, int, int, int]]:
    top = int(round(height * layout.image_top_fraction))
    bottom = int(round(height * layout.image_bottom_fraction))
    inner_h = max(1, bottom - top)

    world_span = layout.viewport_x1 - layout.viewport_x0
    x0_px = int(round((domain.x0 - layout.viewport_x0) / world_span * width))
    x1_px = int(round((domain.x1 - layout.viewport_x0) / world_span * width))
    x0_px = max(0, min(width - 1, x0_px))
    x1_px = max(x0_px + 1, min(width, x1_px))
    inner_w = x1_px - x0_px

    flame = linear.flip(0).permute(2, 0, 1)[None]
    flame = F.interpolate(flame, size=(inner_h, inner_w), mode="bicubic", align_corners=False).clamp_min(0)
    t = trans.flip(0)[None, None]
    t = F.interpolate(t, size=(inner_h, inner_w), mode="bilinear", align_corners=False).clamp(0, 1)

    full_flame = torch.zeros((1, 3, height, width), device=linear.device)
    full_trans = torch.ones((1, 1, height, width), device=linear.device)
    full_flame[:, :, top:bottom, x0_px:x1_px] = flame
    full_trans[:, :, top:bottom, x0_px:x1_px] = t
    return full_flame, full_trans, (top, bottom, x0_px, x1_px)


def tone_map_and_encode(linear: torch.Tensor, frame: int) -> np.ndarray:
    # Multi-scale optical bloom kept restrained to preserve flame detail.
    lum = (linear[:, 0:1] * 0.2126 + linear[:, 1:2] * 0.7152 + linear[:, 2:3] * 0.0722)
    bright = (linear - 0.35).clamp_min(0.0)
    bloom = separable_box_blur(bright, 5) * 0.055 + separable_box_blur(bright, 18) * 0.028
    linear = linear + bloom

    # Deterministic sub-LSB dither prevents dark-gradient banding without adding
    # visible film grain.  It changes only quantization, not flame structure.
    _, _, h, w = linear.shape
    yy = torch.arange(h, device=linear.device, dtype=linear.dtype)[:, None]
    xx = torch.arange(w, device=linear.device, dtype=linear.dtype)[None, :]
    noise = torch.frac(torch.sin(xx * 12.9898 + yy * 78.233 + frame * 0.9187) * 43758.5453) - 0.5
    linear = (linear + noise[None, None] / 4096.0).clamp_min(0)

    # ACES-like fit and sRGB transfer.
    mapped = ((linear * (2.51 * linear + 0.03)) / (linear * (2.43 * linear + 0.59) + 0.14)).clamp(0, 1)
    srgb = torch.where(mapped <= 0.0031308, mapped * 12.92, 1.055 * mapped.pow(1.0 / 2.4) - 0.055)
    return (srgb[0].permute(1, 2, 0) * 255.0).round().byte().cpu().numpy()


def render_frame(
    b: Buffers,
    a: argparse.Namespace,
    domain: Domain,
    layout: SceneLayout,
    width: int,
    height: int,
    frame: int,
) -> Tuple[np.ndarray, Dict[str, float]]:
    flame_low, trans_low = integrate_volume(b)
    flame, trans, _ = resize_volume_to_viewport(flame_low, trans_low, width, height, domain, layout)

    scene = b.scene_base[None].clone()
    flame_lum = flame[:, 0:1] * 0.2126 + flame[:, 1:2] * 0.7152 + flame[:, 2:3] * 0.0722
    light = separable_box_blur(flame_lum, 26).clamp(0, 2.5)
    warm_light = torch.tensor([1.0, 0.34, 0.065], device=scene.device)[None, :, None, None]
    scene += light * warm_light * 0.050

    # Dynamic target heating is sourced from simulation temperature immediately
    # upstream of the plate, then spatially concentrated around the impact zone.
    plate_band = (b.x > layout.plate_x - 0.42) & (b.x < layout.plate_x - 0.05)
    impact_temp = float((b.state[0, 5] * plate_band).amax().clamp(0, 3.3) / 3.3)
    impact_reaction = float((b.state[0, 7] * plate_band).mean().clamp_min(0))
    heat = min(1.0, impact_temp * 0.75 + impact_reaction * 0.12)
    plate_center_z = 0.5 * (layout.plate_z0 + layout.plate_z1)
    hot_spot = torch.exp(-((b.screen_z - plate_center_z) / 0.48).pow(2)) * b.scene_plate_mask
    scene += hot_spot[None, None] * warm_light * (0.16 * heat)

    # Restrained floor reflection from the bright flame, blurred and vertically
    # compressed so it reads as a rough concrete/specular response, not a mirror.
    floor = b.scene_floor_mask[None, None]
    reflected = torch.flip(flame_lum, dims=[2])
    reflected = separable_box_blur(reflected, 12) * floor
    scene += reflected * warm_light * 0.020

    composite = scene * trans + flame
    pixels = tone_map_and_encode(composite, frame)
    metrics = {
        "impactHeat": heat,
        "linearPeak": float(composite.amax()),
        "flameMean": float(flame_lum.mean()),
    }
    return pixels, metrics


def state_metrics(b: Buffers, layout: SceneLayout, div: float) -> Dict[str, float]:
    reaction = b.state[0, 7]
    soot = b.state[0, 6]
    temp = b.state[0, 5]
    active = (reaction > 0.018) | (soot > 0.025) | (temp > 0.42)
    if bool(active.any()):
        max_x = float(b.x[active].max())
    else:
        max_x = 0.0
    total_reaction = float(reaction.sum())
    near_target = b.x > (layout.plate_x - 0.55)
    target_reaction = float((reaction * near_target).sum())
    return {
        "divergenceRMS": div,
        "fuel": float(b.state[0, 3].sum()),
        "soot": float(soot.sum()),
        "reaction": total_reaction,
        "temperatureMax": float(temp.max()),
        "jetReachX": max_x,
        "impactReactionFraction": target_reaction / max(total_reaction, 1e-8),
    }


def save_state(work: Path, frame: int, b: Buffers) -> None:
    d = work / "state"
    d.mkdir(exist_ok=True)
    fields = b.state[0, [5, 6, 7]].detach().cpu().numpy().astype("<f2")
    np.savez_compressed(d / f"{frame:04d}.npz", fields=fields)


def open_encoder(output: Path, width: int, height: int, fps: int) -> subprocess.Popen:
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(output),
    ]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def main() -> None:
    a = parse_args()
    require_environment(a)
    torch.manual_seed(a.seed)
    np.random.seed(a.seed)
    torch.set_grad_enabled(False)
    torch.set_num_threads(2)
    device = "cuda"
    torch.cuda.reset_peak_memory_stats()

    width, height = ((1280, 720) if a.pilot else (1920, 1080))
    domain = Domain()
    layout = SceneLayout()
    b = build_buffers(a, device, width, height, domain, layout)
    dt = 1.0 / (a.fps * a.substeps)
    total_frames = int(round(a.seconds * a.fps))
    encoder = open_encoder(a.output, width, height, a.fps)
    if encoder.stdin is None:
        raise RuntimeError("ffmpeg stdin unavailable")

    started = time.monotonic()
    rows: List[Dict[str, float]] = []
    previews = a.work / "previews"
    previews.mkdir(exist_ok=True)

    try:
        for frame in range(total_frames):
            div = 0.0
            for sub in range(a.substeps):
                t = (frame + sub / a.substeps) / a.fps
                div = simulation_step(b, a, layout, t, dt)

            if not torch.isfinite(b.state).all():
                raise RuntimeError(f"Non-finite simulation state at frame {frame}")
            peak_gib = torch.cuda.max_memory_allocated() / (1024.0 ** 3)
            if peak_gib > a.memory_budget_gib:
                raise RuntimeError(f"GPU memory budget exceeded: {peak_gib:.2f} GiB > {a.memory_budget_gib:.2f} GiB")

            pixels, render_stats = render_frame(b, a, domain, layout, width, height, frame)
            encoder.stdin.write(pixels.tobytes())

            m = state_metrics(b, layout, div)
            m.update(render_stats)
            m.update({"frame": frame, "time": frame / a.fps, "gpuGiB": peak_gib})
            rows.append(m)

            if a.preview_every > 0 and (frame % a.preview_every == 0 or frame == total_frames - 1):
                Image.fromarray(pixels).save(previews / f"{frame:04d}.jpg", quality=94, subsampling=0)
            if a.save_state_every > 0 and frame % a.save_state_every == 0:
                save_state(a.work, frame, b)
            if frame % a.fps == 0 or frame == total_frames - 1:
                print(json.dumps({
                    "frame": frame,
                    "frames": total_frames,
                    "elapsed": round(time.monotonic() - started, 1),
                    **{k: round(v, 5) if isinstance(v, float) else v for k, v in m.items() if k not in {"frame", "time"}},
                }), flush=True)
    finally:
        encoder.stdin.close()

    if encoder.wait() != 0:
        raise RuntimeError("ffmpeg encoding failed")

    report = {
        "id": a.name,
        "source": Path(__file__).name,
        "graphicsModel": "3-D projected low-Mach reactive flow with limited MacCormack scalar transport",
        "notClaimed": "Not a calibrated engineering combustion/weapon model",
        "frames": total_frames,
        "fps": a.fps,
        "duration": a.seconds,
        "resolution": [width, height],
        "gridXYZ": list(a.size),
        "substeps": a.substeps,
        "jetSpeed": a.jet_speed,
        "targetEnabled": bool(a.target),
        "elapsedSeconds": time.monotonic() - started,
        "peakGpuGiB": torch.cuda.max_memory_allocated() / (1024.0 ** 3),
        "jetReachMaxX": max(r["jetReachX"] for r in rows),
        "impactReactionFractionMax": max(r["impactReactionFraction"] for r in rows),
        "impactHeatMax": max(r["impactHeat"] for r in rows),
        "divergenceRMSMax": max(r["divergenceRMS"] for r in rows),
        "linearPeakMax": max(r["linearPeak"] for r in rows),
        "output": str(a.output),
        "samples": rows,
        "visualIntent": [
            "compact near-white/yellow source core",
            "orange turbulent flame envelope with resolved roll-up",
            "soot extinction instead of opaque billboard smoke",
            "flow deflection at target plate",
            "scene illumination and floor response derived from flame radiance",
        ],
    }
    report_path = a.work / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(str(a.output), flush=True)
    print(str(report_path), flush=True)


if __name__ == "__main__":
    main()
