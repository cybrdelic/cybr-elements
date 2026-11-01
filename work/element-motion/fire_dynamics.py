"""Owned numerical policies extracted from pinned legacy consumers; no image fitting."""
import math, gzip, json, time
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

def source_fire_v3(self, t):
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
    temp.lerp_(torch.ones_like(temp) * 1.25, inject)
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
    burn = torch.minimum(fuel, oxygen * 0.7) * (1 - math.exp(-8 * self.dt)) * activation
    fuel.sub_(burn)
    oxygen.sub_(burn / 0.7).clamp_(0, 1)
    temp.add_(burn * 5.5).mul_(math.exp(-1.15 * self.dt)).clamp_(0, 3)
    soot.add_(burn * 0.8).mul_(math.exp(-1.15 * self.dt))
    self.state[0, 7] = burn / self.dt
    del burn, activation
    v[2].add_((temp * 3.4 - soot * 0.32) * self.dt)
    return (v, temp, soot)

def source_bending_fire_v5(self, t):
    fuel, oxygen, temp, soot = [self.state[0, c] for c in [3, 4, 5, 6]]
    center, direction, on, speed = self.nozzle_pose(t)
    cx, cz = center
    dx, dz = direction
    px = self.x - float(cx)
    pz = self.z - float(cz)
    across = -px * float(dz) + pz * float(dx)
    along = px * float(dx) + pz * float(dz)
    nozzle = torch.exp(-((across / 0.23) ** 2 + ((self.y - 0.08 * math.sin(t * 17) - across * 0.35 * math.sin(t * 11)) / 0.045) ** 2 + (along / 0.12) ** 2) * 1.5)
    if self.MODE == 'word':
        nozzle = torch.exp(-((px / 0.08) ** 2 + ((self.y + 2.0) / 0.1) ** 2 + (pz / 0.08) ** 2) * 1.5)
    inject = (nozzle * on * self.dt * (20 + speed * 3) * (0.72 + 0.28 * math.sin(t * 47))).clamp(0, 1)
    fuel.lerp_(torch.ones_like(fuel) * 0.95, inject)
    oxygen.mul_(1 - inject)
    temp.lerp_(torch.ones_like(temp) * 1.25, inject)
    v = self.state[0, :3]
    wake = torch.exp(-((across / 0.32) ** 2 + (self.y / 0.3) ** 2 + (along / 0.55) ** 2)) * on
    v[2].add_(wake * torch.sin(self.y * 18 + t * 15) * 20 * self.dt)
    v[1].add_(wake * torch.cos(pz * 14 - t * 12) * 16 * self.dt)
    shear = 4.8 * torch.sin(self.y * 19 + t * 13) * torch.cos((px + pz) * 12 - t * 11)
    if self.MODE == 'arc':
        v[0].lerp_(float(dx) * 8.0 + shear * float(-dz), inject)
        v[1].lerp_(torch.sin(px * 38 + pz * 27 + t * 23) * 0.8, inject)
        v[2].lerp_(float(dz) * 8.0 + shear * float(dx), inject)
    else:
        v[0].lerp_(shear * 0.35, inject)
        v[1].lerp_(torch.ones_like(self.y) * 3.5 + shear * 0.3, inject)
        v[2].lerp_(shear * 0.3, inject)
    activation = ((temp - 0.15) / 0.22).clamp(0, 1)
    burn = torch.minimum(fuel, oxygen * 0.7) * (1 - math.exp(-8 * self.dt)) * activation
    fuel.sub_(burn)
    oxygen.sub_(burn / 0.7).clamp_(0, 1)
    temp.add_(burn * 5.5).mul_(math.exp(-1.15 * self.dt)).clamp_(0, 3)
    soot.add_(burn * 0.8).mul_(math.exp(-1.15 * self.dt))
    self.state[0, 7] = burn / self.dt
    del burn, activation
    v[2].add_((temp * 3.4 - soot * 0.32) * self.dt)
    return (v, temp, soot)

def source_fire_v2(self, t):
    fuel, oxygen, temp, soot = [self.state[0, c] for c in [3, 4, 5, 6]]
    center, direction, on, speed = self.nozzle_pose(t)
    cx, cz = center
    dx, dz = direction
    px = self.x - float(cx)
    pz = self.z - float(cz)
    across = -px * float(dz) + pz * float(dx)
    along = px * float(dx) + pz * float(dz)
    nozzle = torch.exp(-((across / (0.17 * (1 + 0.18 * math.sin(t * 31)))) ** 2 + (self.y / 0.16) ** 2 + (along / 0.14) ** 2) * 1.5)
    if self.MODE == 'word':
        nozzle = torch.exp(-((px / 0.08) ** 2 + ((self.y + 2.0) / 0.1) ** 2 + (pz / 0.08) ** 2) * 1.5)
    inject = (nozzle * on * self.dt * (22 + speed * 4)).clamp(0, 1)
    fuel.lerp_(torch.ones_like(fuel) * 0.65, inject)
    oxygen.mul_(1 - inject)
    temp.lerp_(torch.ones_like(temp) * 1.25, inject)
    v = self.state[0, :3]
    wake = torch.exp(-((across / 0.32) ** 2 + (self.y / 0.3) ** 2 + (along / 0.55) ** 2)) * on
    v[2].add_(wake * torch.sin(self.y * 18 + t * 15) * 9 * self.dt)
    v[1].add_(wake * torch.cos(pz * 14 - t * 12) * 8 * self.dt)
    shear = 3.2 * torch.sin(self.y * 19 + t * 13) * torch.cos((px + pz) * 12 - t * 11)
    if self.MODE == 'arc':
        v[0].lerp_(-float(dx) * 3.5 + shear * float(-dz), inject)
        v[1].lerp_(torch.sin(px * 38 + pz * 27 + t * 23) * 0.8, inject)
        v[2].lerp_(-float(dz) * 3.5 + shear * float(dx), inject)
    else:
        v[0].lerp_(shear * 0.35, inject)
        v[1].lerp_(torch.ones_like(self.y) * 3.5 + shear * 0.3, inject)
        v[2].lerp_(shear * 0.3, inject)
    activation = ((temp - 0.15) / 0.22).clamp(0, 1)
    burn = torch.minimum(fuel, oxygen * 0.7) * (1 - math.exp(-8 * self.dt)) * activation
    fuel.sub_(burn)
    oxygen.sub_(burn / 0.7).clamp_(0, 1)
    temp.add_(burn * 5.5).mul_(math.exp(-1.15 * self.dt)).clamp_(0, 3)
    soot.add_(burn * 0.8).mul_(math.exp(-1.15 * self.dt))
    self.state[0, 7] = burn / self.dt
    del burn, activation
    v[2].add_((temp * 3.4 - soot * 0.32) * self.dt)
    return (v, temp, soot)

def source_sigil_native_fire_fed(self, t):
    fuel, oxygen, temp, soot = [self.state[0, c] for c in [3, 4, 5, 6]]
    center, direction, on, speed = self.nozzle_pose(t)
    cx, cz = center
    dx, dz = direction
    px = self.x - float(cx)
    pz = self.z - float(cz)
    across = -px * float(dz) + pz * float(dx)
    along = px * float(dx) + pz * float(dz)
    nozzle = torch.exp(-((across / 0.23) ** 2 + ((self.y - 0.08 * math.sin(t * 17) - across * 0.35 * math.sin(t * 11)) / 0.045) ** 2 + (along / 0.12) ** 2) * 1.5)
    if self.MODE == 'word':
        nozzle = torch.exp(-((px / 0.08) ** 2 + ((self.y + 2.0) / 0.1) ** 2 + (pz / 0.08) ** 2) * 1.5)
    inject = (nozzle * on * self.dt * (20 + speed * 3) * (0.72 + 0.28 * math.sin(t * 47))).clamp(0, 1)
    line = torch.exp(-((across / 0.044) ** 2 + (self.y / 0.05) ** 2 + (along / 0.085) ** 2) * 1.5) * on
    torch.maximum(self.reservoir, line, out=self.reservoir)
    gas_inject = (self.reservoir * (1.8 * self.dt)).clamp(0, 1)
    if t >= 2.4:
        self.reservoir.sub_(gas_inject).clamp_min_(0)
    fuel.lerp_(torch.ones_like(fuel) * 0.22, gas_inject)
    oxygen.lerp_(torch.ones_like(oxygen) * 0.8, gas_inject)
    temp.lerp_(torch.ones_like(temp) * 0.8, gas_inject)
    fuel.lerp_(torch.ones_like(fuel) * 0.95, inject)
    oxygen.mul_(1 - inject)
    temp.lerp_(torch.ones_like(temp) * 1.25, inject)
    v = self.state[0, :3]
    wake = torch.exp(-((across / 0.32) ** 2 + (self.y / 0.3) ** 2 + (along / 0.55) ** 2)) * on
    v[2].add_(wake * torch.sin(self.y * 18 + t * 15) * 20 * self.dt)
    v[1].add_(wake * torch.cos(pz * 14 - t * 12) * 16 * self.dt)
    shear = 4.8 * torch.sin(self.y * 19 + t * 13) * torch.cos((px + pz) * 12 - t * 11)
    if self.MODE == 'arc':
        v[0].lerp_(float(dx) * 8.0 + shear * float(-dz), inject)
        v[1].lerp_(torch.sin(px * 38 + pz * 27 + t * 23) * 0.8, inject)
        v[2].lerp_(float(dz) * 8.0 + shear * float(dx), inject)
    else:
        v[0].lerp_(shear * 0.35, inject)
        v[1].lerp_(torch.ones_like(self.y) * 3.5 + shear * 0.3, inject)
        v[2].lerp_(shear * 0.3, inject)
    activation = ((temp - 0.15) / 0.22).clamp(0, 1)
    burn = torch.minimum(fuel, oxygen * 0.7) * (1 - math.exp(-8 * self.dt)) * activation
    fuel.sub_(burn)
    oxygen.sub_(burn / 0.7).clamp_(0, 1)
    temp.add_(burn * 5.5).mul_(math.exp(-1.15 * self.dt)).clamp_(0, 3)
    soot.add_(burn * 0.8).mul_(math.exp(-1.15 * self.dt))
    self.state[0, 7] = burn / self.dt
    del burn, activation
    v[2].add_((temp * 3.4 - soot * 0.32) * self.dt)
    return (v, temp, soot)


def source_style02(self, t):
    fuel, oxygen, temp, soot = [self.state[0, c] for c in [3, 4, 5, 6]]
    age = t - self.arrival
    opened = torch.sigmoid(age / 0.026)
    leading = torch.exp(-((age - 0.08) / 0.105) ** 2)
    valve = math.exp(-3.2 * max(0.0, t - 6.8))
    corrugation = 0.045 * torch.sin(self.x * 7 + self.z * 5 - t * 3.4) + 0.025 * torch.sin(self.x * 17 - self.z * 11 + t * 5.7)
    sheet = torch.exp(-((self.y - corrugation) / self.sheet_depth) ** 2 * 1.5) * self.support
    current = sheet * opened * valve
    front = (sheet * leading * self.dt * 20).clamp(0, 1)
    sustained = (current * self.dt * 2.5).clamp(0, 1)
    inject = (front + sustained).clamp(0, 1)
    fuel.lerp_(torch.ones_like(fuel) * 0.55, sustained)
    fuel.lerp_(torch.ones_like(fuel) * 0.95, front)
    oxygen.mul_(1 - inject)
    temp.lerp_(torch.ones_like(temp) * 0.5, sustained)
    temp.lerp_(torch.ones_like(temp) * 1.25, front)
    v = self.state[0, :3]
    speed = 0.25 + 7.75 * leading
    shear = 4.8 * torch.sin(self.y * 19 + t * 13) * torch.cos((self.x + self.z) * 12 - t * 11) * leading
    v[0].lerp_(self.tangent_x * speed - self.tangent_z * shear, inject)
    v[1].lerp_(0.18 + torch.sin(self.x * 38 + self.z * 27 + t * 23) * (0.12 + 0.68 * leading), inject)
    v[2].lerp_(self.tangent_z * speed + self.tangent_x * shear, inject)
    wake = sheet * leading
    v[2].add_(wake * torch.sin(self.y * 18 + t * 15) * 20 * self.dt)
    v[1].add_(wake * torch.cos(self.z * 14 - t * 12) * 16 * self.dt)
    del age, opened, leading, corrugation, sheet, current, front, sustained, inject, speed, shear, wake
    activation = ((temp - 0.15) / 0.22).clamp(0, 1)
    burn = torch.minimum(fuel, oxygen * 0.7) * (1 - math.exp(-8 * self.dt)) * activation
    fuel.sub_(burn)
    oxygen.sub_(burn / 0.7).clamp_(0, 1)
    temp.add_(burn * 5.5).mul_(math.exp(-1.15 * self.dt)).clamp_(0, 3)
    soot.add_(burn * 0.8).mul_(math.exp(-1.15 * self.dt))
    self.state[0, 7] = burn / self.dt
    del burn, activation
    v[2].add_((temp * 3.4 - soot * 0.32) * self.dt)
    return (v, temp, soot)
