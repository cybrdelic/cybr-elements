"""Owned numerical policies extracted from pinned legacy consumers; no image fitting."""
import math, gzip, json, time
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

def advance(self, t):
    self.state = self.flow.transport(self.state)
    v, temp, soot = self.source_reaction(t)
    v[0].add_(self.a.wind * (self.z - 0.25).clamp(0, 2) * ((self.z - 0.25) / 0.5).clamp(0, 1) * self.dt)
    if self.a.control == 'choreographed' and self.a.gesture_version.startswith('21'):
        self.steer_broad_flow(v, t, temp, soot)
    if self.a.gesture_version == '22b':
        angle = self.turn_support * (self.turn_rate(t) * self.dt)
        c = angle.cos()
        s = angle.sin()
        old_x = v[0].clone()
        v[0].mul_(c).sub_(v[1] * s)
        v[1].mul_(c).add_(old_x * s)
        del angle, c, s, old_x
    if self.a.control == 'directed':
        dx = self.x - (0.65 + 0.12 * math.sin(t * 0.8))
        dz = (self.z - 2.15) * 0.9
        radius = (dx * dx + dz * dz).sqrt().clamp_min(0.05)
        control = torch.exp(-((radius - 1.4) / 1.2) ** 4 - (self.y / 0.82) ** 4) * self.a.control_strength
        omega = 2.5 + 0.45 * math.sin(t * 1.4)
        radial = (radius - (1.4 + 0.13 * math.sin(t * 1.9))) * 3.2
        desired_x = -omega * dz - radial * dx / radius
        desired_z = (omega * dx - radial * dz / radius) / 0.9 + 0.18
        v[2].sub_((temp * 3.4 - soot * 0.32) * control * self.dt)
        guide = (control * (1 - math.exp(-5.5 * self.dt))).clamp(0, 1)
        v[0].lerp_(desired_x, guide)
        v[1].lerp_(-self.y * 0.9 + 0.22 * torch.sin(self.z * 2.5 + t * 2), guide)
        v[2].lerp_(desired_z, guide)
    if self.turn is not None:
        angle = self.turn(t, temp, soot)
        c = angle.cos()
        s = angle.sin()
        old_x = v[0].clone()
        v[0].mul_(c).sub_(v[2] * s)
        v[2].mul_(c).add_(old_x * s)
        del angle, c, s, old_x
    if self.MODE == 'word':
        lift = max(0.0, min(1.0, (self.START + self.WRITE + 0.35 - t) / 0.2)) * 0.65
        v[2].sub_((temp * 3.4 - soot * 0.32) * (lift * self.dt))
    return self.flow.project(self.state)

def steer_broad_flow(self, v, t, temp, soot):
    if self.guide_strength(t) < 1e-06:
        return
    phase = t * 24
    index = int(phase)
    fraction = phase - index
    guide = self.control_frame(index) * (1 - fraction) + self.control_frame(index + 1) * fraction
    low = F.interpolate(v[None], size=self.controller.shape, mode='trilinear', align_corners=True)[0]
    force = (guide[:3] - low) * (5.5 * guide[3:4])
    force *= torch.clamp(35 / torch.linalg.vector_norm(force, dim=0).clamp_min(1e-06), max=1)[None]
    guide[:3] = force
    applied = F.interpolate(guide[None], size=self.shape, mode='trilinear', align_corners=True)[0]
    v.add_(applied[:3] * self.dt)
    v[2].sub_((temp * 3.4 - soot * 0.32) * applied[3] * self.dt)

def turn_fire_v3(self, t, temp, soot):
    return (temp * 0.8 + soot * 4).clamp(0, 1) * (float(self.nozzle_turn(t)) * self.dt * 0.35 if self.MODE == 'arc' else 0.0)

def turn_air_v2(self, t, temp, soot):
    return (temp * 0.8 + soot * 4).clamp(0, 1) * (float(self.nozzle_turn(t)) * self.dt if self.MODE == 'arc' else 0.0)

def turn_air_v3(self, t, temp, soot):
    return (temp * 0.8 + soot * 4).clamp(0, 1) * (0.0 if self.MODE == 'arc' else 0.0)
