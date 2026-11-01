"""Owned numerical policies extracted from pinned legacy consumers; no image fitting."""
import math, gzip, json, time
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

def source_earth_dust(self, t):
    fuel, oxygen, temp, soot = [self.state[0, c] for c in [3, 4, 5, 6]]
    center, direction, on, speed = self.nozzle_pose(t)
    cx, cz = center
    dx, dz = direction
    px = self.x - float(cx)
    pz = self.z - float(cz)
    across = -px * float(dz) + pz * float(dx)
    along = px * float(dx) + pz * float(dz)
    nozzle = torch.exp(-((across / (0.17 * (1 + 0.18 * math.sin(t * 31)))) ** 2 + (self.y / 0.16) ** 2 + (along / 0.1) ** 2) * 1.5)
    if self.MODE == 'word':
        nozzle = torch.exp(-((px / 0.08) ** 2 + ((self.y + 2.0) / 0.1) ** 2 + (pz / 0.08) ** 2) * 1.5)
    inject = (nozzle * on * self.dt * (20 + speed * 3) * (0.72 + 0.28 * math.sin(t * 47))).clamp(0, 1)
    fuel.lerp_(torch.ones_like(fuel) * 0.65, inject)
    oxygen.mul_(1 - inject)
    soot.lerp_(torch.ones_like(soot) * 0.38, inject)
    temp.zero_()
    v = self.state[0, :3]
    wake = torch.exp(-((across / 0.32) ** 2 + (self.y / 0.3) ** 2 + (along / 0.55) ** 2)) * on
    v[2].add_(wake * torch.sin(self.y * 18 + t * 15) * 20 * self.dt)
    v[1].add_(wake * torch.cos(pz * 14 - t * 12) * 16 * self.dt)
    shear = 3.2 * torch.sin(self.y * 19 + t * 13) * torch.cos((px + pz) * 12 - t * 11)
    if self.MODE == 'arc':
        v[0].lerp_(float(dx) * 8.0 + shear * float(-dz), inject)
        v[1].lerp_(torch.sin(px * 38 + pz * 27 + t * 23) * 0.8, inject)
        v[2].lerp_(float(dz) * 8.0 + shear * float(dx), inject)
    else:
        v[0].lerp_(shear * 0.35, inject)
        v[1].lerp_(torch.ones_like(self.y) * 3.5 + shear * 0.3, inject)
        v[2].lerp_(shear * 0.3, inject)
    activation = ((temp - 0.15) / 0.22).clamp(0, 1)
    burn = torch.zeros_like(fuel)
    fuel.sub_(burn)
    oxygen.sub_(burn / 0.7).clamp_(0, 1)
    temp.add_(burn * 5.5).mul_(math.exp(-1.15 * self.dt)).clamp_(0, 3)
    soot.mul_(math.exp(-0.65 * self.dt))
    self.state[0, 7] = burn / self.dt
    del burn, activation
    v[0].add_(0.25 * self.dt)
    return (v, temp, soot)
