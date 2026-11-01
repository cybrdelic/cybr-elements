"""Owned numerical policies extracted from pinned legacy consumers; no image fitting."""
import math, gzip, json, time
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

def source_air_v2(self, t):
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
    soot.lerp_(torch.ones_like(soot) * 0.6, inject)
    temp.zero_()
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
    burn = torch.zeros_like(fuel)
    fuel.sub_(burn)
    oxygen.sub_(burn / 0.7).clamp_(0, 1)
    temp.add_(burn * 5.5).mul_(math.exp(-1.15 * self.dt)).clamp_(0, 3)
    soot.mul_(math.exp(-0.35 * self.dt))
    self.state[0, 7] = burn / self.dt
    del burn, activation
    v[0].add_(0.25 * self.dt)
    return (v, temp, soot)

def source_air_v3(self, t):
    fuel, oxygen, temp, soot = [self.state[0, c] for c in [3, 4, 5, 6]]
    center, direction, on, speed = ([-2.8, 1.9], [1.0, 0.0], max(0.0, min(1.0, t / 0.06, (0.48 - t) / 0.06)), 6.0)
    cx, cz = center
    dx, dz = direction
    px = self.x - float(cx)
    pz = self.z - float(cz)
    across = -px * float(dz) + pz * float(dx)
    along = px * float(dx) + pz * float(dz)
    nozzle = torch.exp(-(((across * across + self.y * self.y).sqrt() / 0.3) ** 8 + (along / 0.12) ** 2) * 1.5)
    if self.MODE == 'word':
        nozzle = torch.exp(-((px / 0.08) ** 2 + ((self.y + 2.0) / 0.1) ** 2 + (pz / 0.08) ** 2) * 1.5)
    inject = (nozzle * on * self.dt * (45 + speed * 5)).clamp(0, 1)
    fuel.lerp_(torch.ones_like(fuel) * 0.65, inject)
    oxygen.mul_(1 - inject)
    soot.lerp_(torch.ones_like(soot) * 0.22, inject)
    temp.zero_()
    v = self.state[0, :3]
    wake = torch.exp(-((across / 0.32) ** 2 + (self.y / 0.3) ** 2 + (along / 0.55) ** 2)) * on
    v[2].add_(wake * torch.sin(self.y * 18 + t * 15) * 1.2 * self.dt)
    v[1].add_(wake * torch.cos(pz * 14 - t * 12) * 1.0 * self.dt)
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
    soot.mul_(math.exp(-0.35 * self.dt))
    self.state[0, 7] = burn / self.dt
    del burn, activation
    v[0].add_(0.25 * self.dt)
    return (v, temp, soot)

def source_air_material(self, t):
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
    soot.lerp_(torch.ones_like(soot) * 0.28, inject)
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

def source_bending_air(self, t):
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
    carrier = torch.zeros_like(soot)
    for j in range(3):
        yc = (j - 1) * 0.095 + 0.018 * math.sin(t * 12 + j * 2)
        ac = 0.09 * math.sin(t * 9 + j * 2.1)
        carrier += torch.exp(-((self.y - yc) / 0.028) ** 2 - ((across - ac) / 0.04) ** 2)
    soot.lerp_(torch.ones_like(soot) * 0.7, inject * carrier.clamp(0, 1))
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
    sustained = (current * self.dt * 4.0).clamp(0, 1)
    inject = (front + sustained).clamp(0, 1)
    filament = 0.25 + 0.75 * (0.5 + 0.5 * torch.sin(self.x * 45 + self.z * 33 + self.y * 29 - t * 5)).pow(3)
    soot.lerp_(torch.ones_like(soot) * self.spec.tracer_density, inject * filament)
    fuel.zero_()
    temp.zero_()
    v = self.state[0, :3]
    speed = 0.16 + 5.1 * leading
    shear = 4.8 * torch.sin(self.y * 19 + t * 13) * torch.cos((self.x + self.z) * 12 - t * 11) * leading
    v[0].lerp_(self.tangent_x * speed - self.tangent_z * shear, inject)
    v[1].lerp_(0.18 + torch.sin(self.x * 38 + self.z * 27 + t * 23) * (0.12 + 0.68 * leading), inject)
    v[2].lerp_(self.tangent_z * speed + self.tangent_x * shear, inject)
    wake = sheet * leading
    v[2].add_(wake * torch.sin(self.y * 18 + t * 15) * 20 * self.dt)
    v[1].add_(wake * torch.cos(self.z * 14 - t * 12) * 16 * self.dt)
    del age, opened, leading, corrugation, sheet, current, front, sustained, inject, speed, shear, wake
    self.state[0, 7].zero_()
    soot.mul_(math.exp(-self.spec.tracer_decay * self.dt))
    temp.zero_()
    return (v, temp, soot)
