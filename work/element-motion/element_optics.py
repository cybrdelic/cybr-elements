"""Owned numerical policies extracted from pinned legacy consumers; no image fitting."""
import math, gzip, json, time
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

def radiance_fire_v3(self):
    temp = self.state[0, 5]
    soot = self.state[0, 6]
    reaction = self.state[0, 7]
    hot = ((temp - 0.35) / 1.65).clamp(0, 1)
    sigma = (soot * 3.6 + reaction * 0.09).clamp(0, 16)
    tau = torch.flip(torch.cumsum(torch.flip(soot, [0]), dim=0), [0]) * self.h[2] * 3.6
    key = torch.exp(-tau)
    colors = torch.stack([torch.ones_like(hot), 0.1 + 0.85 * hot.pow(0.8), 0.004 + 0.56 * hot.pow(2)], dim=-1)
    emission = colors * (reaction.pow(0.85) * 4)[..., None]
    light = torch.tensor([0.045, 0.037, 0.052], device=self.device) + key[..., None] * torch.tensor([1.8, 1.55, 1.45], device=self.device)
    rgb = emission + soot[..., None] * 3.6 * 0.55 * light / (4 * math.pi)
    return (rgb, sigma)

def pixels_fire_v3(self, frame):
    rgb, sigma = self.radiance()
    atten = torch.exp(-sigma * self.h[1])
    transmission = torch.cat([torch.ones_like(atten[:, :1]), torch.cumprod(atten[:, :-1], dim=1)], dim=1)
    linear = (transmission[..., None] * rgb * (1 - atten[..., None]) / sigma[..., None].clamp_min(1e-06)).sum(1)
    linear = F.interpolate(linear.permute(2, 0, 1).flip(1)[None], size=(768, 1920), mode='bicubic', align_corners=False).clamp_min(0)
    blur = F.avg_pool2d(F.avg_pool2d(linear, (1, 21), stride=1, padding=(0, 10)), (21, 1), stride=1, padding=(10, 0))
    linear = (linear + blur * 0.06) * 0.72
    linear = F.pad(linear, (0, 0, 120, 192))
    fade = 1.0
    linear = linear * fade
    im = (linear * (2.51 * linear + 0.03) / (linear * (2.43 * linear + 0.59) + 0.14)).clamp(0, 1)
    im = torch.where(im <= 0.0031308, im * 12.92, 1.055 * im.pow(1 / 2.4) - 0.055)
    pixels = (im[0].permute(1, 2, 0) * 255).byte().cpu().numpy()
    return pixels

def capture_fire_v3(self, frame, t, div):
    rgb, sigma = self.radiance()
    packed = torch.cat([(rgb / 16).clamp(0, 1).sqrt(), (sigma / 16).sqrt()[..., None]], dim=-1)
    raw = (packed * 255).round().to(torch.uint8).cpu().numpy()
    (self.out / f'{frame:04}.rgba.gz').write_bytes(gzip.compress(raw.tobytes(), compresslevel=2))
    velocity = F.interpolate(self.state[:, :3], size=tuple((int(n) for n in self.velocity_size[::-1])), mode='trilinear', align_corners=True)[0].permute(1, 2, 3, 0).cpu().numpy().astype('<f2')
    np.save(self.out / f'{frame:04}.velocity.npy', velocity)
    atten = torch.exp(-sigma * self.h[1])
    transmission = torch.cat([torch.ones_like(atten[:, :1]), torch.cumprod(atten[:, :-1], dim=1)], dim=1)
    image = (transmission[..., None] * rgb * (1 - atten[..., None]) / sigma[..., None].clamp_min(1e-06)).sum(1)
    image = (image * (2.51 * image + 0.03) / (image * (2.43 * image + 0.59) + 0.14)).clamp(0, 1)
    image = torch.where(image <= 0.0031308, image * 12.92, 1.055 * image.pow(1 / 2.4) - 0.055)
    pixels = (image.flip(0) * 255).byte().cpu().numpy()
    im = Image.fromarray(pixels).resize((396, 480))
    im.save(self.out / f'{frame:04}.jpg', quality=90)
    row = {'frame': frame, 'time': t, 'fuel': float(self.state[0, 3].sum()), 'soot': float(self.state[0, 6].sum()), 'reaction': float(self.state[0, 7].sum()), 'divergenceRMS': div, 'activeVoxels': int(np.any(raw > 0, axis=-1).sum()), 'seconds': round(time.monotonic() - self.started, 2)}
    self.rows.append(row)
    if frame % self.a.fps == 0:
        print(json.dumps(row), flush=True)

def pixels_air_v2(self, frame):
    sigma = self.state[0, 6] * 2.4
    depthLight = torch.exp(-torch.cumsum(sigma, dim=0) * float(self.h[2]) * 0.55)
    rgb = sigma[..., None] * depthLight[..., None] * torch.tensor([0.66, 0.75, 0.8], device=self.device) * 1.8
    atten = torch.exp(-sigma * self.h[1])
    transmission = torch.cat([torch.ones_like(atten[:, :1]), torch.cumprod(atten[:, :-1], dim=1)], dim=1)
    linear = (transmission[..., None] * rgb * (1 - atten[..., None]) / sigma[..., None].clamp_min(1e-06)).sum(1)
    linear = F.interpolate(linear.permute(2, 0, 1).flip(1)[None], size=(768, 1920), mode='bicubic', align_corners=False).clamp_min(0)
    blur = F.avg_pool2d(F.avg_pool2d(linear, (1, 21), stride=1, padding=(0, 10)), (21, 1), stride=1, padding=(10, 0))
    linear = (linear + blur * 0.06) * 0.72
    linear = F.pad(linear, (0, 0, 120, 192))
    fade = 1.0
    linear = linear * fade
    im = (linear * (2.51 * linear + 0.03) / (linear * (2.43 * linear + 0.59) + 0.14)).clamp(0, 1)
    im = torch.where(im <= 0.0031308, im * 12.92, 1.055 * im.pow(1 / 2.4) - 0.055)
    pixels = (im[0].permute(1, 2, 0) * 255).byte().cpu().numpy()
    return pixels

def radiance_bending_fire_v5(self):
    temp = self.state[0, 5]
    soot = self.state[0, 6]
    reaction = self.state[0, 7]
    hot = ((temp - 0.28) / 1.8).clamp(0, 1)
    sigma = (soot * 6.0 + reaction * 0.032).clamp(0, 16)
    tau = torch.flip(torch.cumsum(torch.flip(soot, [0]), dim=0), [0]) * self.h[2] * 4.4
    key = torch.exp(-tau)
    colors = torch.stack([torch.ones_like(hot), 0.035 + 0.93 * hot.pow(1.3), 0.002 + 0.72 * hot.pow(3.0)], dim=-1)
    front = reaction.clamp_min(0).pow(0.95) / (1 + 0.1 * reaction.clamp_min(0))
    emission = colors * (front * 7.0)[..., None]
    light = torch.tensor([0.02, 0.019, 0.025], device=self.device) + key[..., None] * torch.tensor([1.4, 1.1, 0.85], device=self.device)
    rgb = emission + soot[..., None] * 4.4 * 0.42 * light / (4 * math.pi)
    return (rgb, sigma)

def pixels_bending_fire_v5(self, frame):
    rgb, sigma = self.radiance()
    atten = torch.exp(-sigma * self.h[1])
    transmission = torch.cat([torch.ones_like(atten[:, :1]), torch.cumprod(atten[:, :-1], dim=1)], dim=1)
    linear = (transmission[..., None] * rgb * (1 - atten[..., None]) / sigma[..., None].clamp_min(1e-06)).sum(1)
    linear = F.interpolate(linear.permute(2, 0, 1).flip(1)[None], size=(768, 1920), mode='bicubic', align_corners=False).clamp_min(0)
    blur = F.avg_pool2d(F.avg_pool2d(linear, (1, 21), stride=1, padding=(0, 10)), (21, 1), stride=1, padding=(10, 0))
    linear = (linear + blur * 0.018) * 0.72
    linear = F.pad(linear, (0, 0, 120, 192))
    fade = 1.0
    linear = linear * fade
    im = (linear * (2.51 * linear + 0.03) / (linear * (2.43 * linear + 0.59) + 0.14)).clamp(0, 1)
    im = torch.where(im <= 0.0031308, im * 12.92, 1.055 * im.pow(1 / 2.4) - 0.055)
    pixels = (im[0].permute(1, 2, 0) * 255).byte().cpu().numpy()
    return pixels

def radiance_fire_material_v2(self):
    temp = self.state[0, 5]
    soot = self.state[0, 6]
    reaction = self.state[0, 7]
    hot = ((temp - 0.28) / 1.8).clamp(0, 1)
    sigma = (soot * 4.4 + reaction * 0.025).clamp(0, 16)
    tau = torch.flip(torch.cumsum(torch.flip(soot, [0]), dim=0), [0]) * self.h[2] * 4.4
    key = torch.exp(-tau)
    colors = torch.stack([torch.ones_like(hot), 0.035 + 0.93 * hot.pow(1.3), 0.002 + 0.72 * hot.pow(3.0)], dim=-1)
    front = reaction.clamp_min(0).pow(0.95)
    emission = colors * (front * 4.3)[..., None]
    light = torch.tensor([0.02, 0.019, 0.025], device=self.device) + key[..., None] * torch.tensor([1.4, 1.1, 0.85], device=self.device)
    rgb = emission + soot[..., None] * 4.4 * 0.42 * light / (4 * math.pi)
    return (rgb, sigma)

def pixels_earth_dust(self, frame):
    sigma = self.state[0, 6] * 2.4
    depthLight = torch.exp(-torch.cumsum(sigma, dim=0) * float(self.h[2]) * 0.55)
    rgb = sigma[..., None] * depthLight[..., None] * torch.tensor([0.48, 0.3, 0.15], device=self.device) * 1.8
    atten = torch.exp(-sigma * self.h[1])
    transmission = torch.cat([torch.ones_like(atten[:, :1]), torch.cumprod(atten[:, :-1], dim=1)], dim=1)
    linear = (transmission[..., None] * rgb * (1 - atten[..., None]) / sigma[..., None].clamp_min(1e-06)).sum(1)
    linear = F.interpolate(linear.permute(2, 0, 1).flip(1)[None], size=(768, 1920), mode='bicubic', align_corners=False).clamp_min(0)
    blur = F.avg_pool2d(F.avg_pool2d(linear, (1, 21), stride=1, padding=(0, 10)), (21, 1), stride=1, padding=(10, 0))
    linear = (linear + blur * 0.06) * 0.72
    linear = F.pad(linear, (0, 0, 120, 192))
    fade = 1.0
    linear = linear * fade
    im = (linear * (2.51 * linear + 0.03) / (linear * (2.43 * linear + 0.59) + 0.14)).clamp(0, 1)
    im = torch.where(im <= 0.0031308, im * 12.92, 1.055 * im.pow(1 / 2.4) - 0.055)
    pixels = (im[0].permute(1, 2, 0) * 255).byte().cpu().numpy()
    return pixels

def capture_earth_dust(self, frame, t, div):
    sigma = self.state[0, 6] * 2.4
    depthLight = torch.exp(-torch.cumsum(sigma, dim=0) * float(self.h[2]) * 0.55)
    rgb = sigma[..., None] * depthLight[..., None] * torch.tensor([0.48, 0.3, 0.15], device=self.device) * 1.8
    packed = torch.cat([(rgb / 16).clamp(0, 1).sqrt(), (sigma / 16).sqrt()[..., None]], dim=-1)
    raw = (packed * 255).round().to(torch.uint8).cpu().numpy()
    (self.out / f'{frame:04}.rgba.gz').write_bytes(gzip.compress(raw.tobytes(), compresslevel=2))
    velocity = F.interpolate(self.state[:, :3], size=tuple((int(n) for n in self.velocity_size[::-1])), mode='trilinear', align_corners=True)[0].permute(1, 2, 3, 0).cpu().numpy().astype('<f2')
    np.save(self.out / f'{frame:04}.velocity.npy', velocity)
    atten = torch.exp(-sigma * self.h[1])
    transmission = torch.cat([torch.ones_like(atten[:, :1]), torch.cumprod(atten[:, :-1], dim=1)], dim=1)
    image = (transmission[..., None] * rgb * (1 - atten[..., None]) / sigma[..., None].clamp_min(1e-06)).sum(1)
    image = (image * (2.51 * image + 0.03) / (image * (2.43 * image + 0.59) + 0.14)).clamp(0, 1)
    image = torch.where(image <= 0.0031308, image * 12.92, 1.055 * image.pow(1 / 2.4) - 0.055)
    pixels = (image.flip(0) * 255).byte().cpu().numpy()
    im = Image.fromarray(pixels).resize((396, 480))
    im.save(self.out / f'{frame:04}.jpg', quality=90)
    row = {'frame': frame, 'time': t, 'fuel': float(self.state[0, 3].sum()), 'soot': float(self.state[0, 6].sum()), 'reaction': float(self.state[0, 7].sum()), 'divergenceRMS': div, 'activeVoxels': int(np.any(raw > 0, axis=-1).sum()), 'seconds': round(time.monotonic() - self.started, 2)}
    self.rows.append(row)
    if frame % self.a.fps == 0:
        print(json.dumps(row), flush=True)

def pixels_air_material(self, frame):
    density = self.state[0, 6]
    sigma = density.clamp_min(0).pow(1.45) * 3.0
    top = torch.flip(torch.cumsum(torch.flip(sigma, [0]), dim=0), [0]) * self.h[2]
    back = torch.flip(torch.cumsum(torch.flip(sigma, [1]), dim=1), [1]) * self.h[1]
    lit = torch.exp(-top * 1.7 - back * 0.8)
    cosine = (2 - self.y) / torch.sqrt((self.x + 2) ** 2 + (2 - self.y) ** 2 + (self.z - 4) ** 2).clamp_min(0.1)
    phase = (1 - 0.45 ** 2) / (1 + 0.45 ** 2 - 2 * 0.45 * cosine).clamp_min(0.05).pow(1.5)
    rgb = sigma[..., None] * (lit * phase * 0.95 + 0.1)[..., None] * torch.tensor([0.66, 0.76, 0.83], device=self.device)
    atten = torch.exp(-sigma * self.h[1])
    transmission = torch.cat([torch.ones_like(atten[:, :1]), torch.cumprod(atten[:, :-1], dim=1)], dim=1)
    linear = (transmission[..., None] * rgb * (1 - atten[..., None]) / sigma[..., None].clamp_min(1e-06)).sum(1)
    linear = F.interpolate(linear.permute(2, 0, 1).flip(1)[None], size=(768, 1920), mode='bicubic', align_corners=False).clamp_min(0)
    blur = F.avg_pool2d(F.avg_pool2d(linear, (1, 21), stride=1, padding=(0, 10)), (21, 1), stride=1, padding=(10, 0))
    linear = (linear + blur * 0.005) * 0.72
    linear = F.pad(linear, (0, 0, 120, 192))
    fade = 1.0
    linear = linear * fade
    im = (linear * (2.51 * linear + 0.03) / (linear * (2.43 * linear + 0.59) + 0.14)).clamp(0, 1)
    im = torch.where(im <= 0.0031308, im * 12.92, 1.055 * im.pow(1 / 2.4) - 0.055)
    pixels = (im[0].permute(1, 2, 0) * 255).byte().cpu().numpy()
    return pixels

def capture_air_material(self, frame, t, div):
    sigma = self.state[0, 6] * 2.4
    depthLight = torch.exp(-torch.cumsum(sigma, dim=0) * float(self.h[2]) * 0.55)
    rgb = sigma[..., None] * depthLight[..., None] * torch.tensor([0.66, 0.75, 0.8], device=self.device) * 1.8
    packed = torch.cat([(rgb / 16).clamp(0, 1).sqrt(), (sigma / 16).sqrt()[..., None]], dim=-1)
    raw = (packed * 255).round().to(torch.uint8).cpu().numpy()
    (self.out / f'{frame:04}.rgba.gz').write_bytes(gzip.compress(raw.tobytes(), compresslevel=2))
    velocity = F.interpolate(self.state[:, :3], size=tuple((int(n) for n in self.velocity_size[::-1])), mode='trilinear', align_corners=True)[0].permute(1, 2, 3, 0).cpu().numpy().astype('<f2')
    np.save(self.out / f'{frame:04}.velocity.npy', velocity)
    atten = torch.exp(-sigma * self.h[1])
    transmission = torch.cat([torch.ones_like(atten[:, :1]), torch.cumprod(atten[:, :-1], dim=1)], dim=1)
    image = (transmission[..., None] * rgb * (1 - atten[..., None]) / sigma[..., None].clamp_min(1e-06)).sum(1)
    image = (image * (2.51 * image + 0.03) / (image * (2.43 * image + 0.59) + 0.14)).clamp(0, 1)
    image = torch.where(image <= 0.0031308, image * 12.92, 1.055 * image.pow(1 / 2.4) - 0.055)
    pixels = (image.flip(0) * 255).byte().cpu().numpy()
    im = Image.fromarray(pixels).resize((396, 480))
    im.save(self.out / f'{frame:04}.jpg', quality=90)
    row = {'frame': frame, 'time': t, 'fuel': float(self.state[0, 3].sum()), 'soot': float(self.state[0, 6].sum()), 'reaction': float(self.state[0, 7].sum()), 'divergenceRMS': div, 'activeVoxels': int(np.any(raw > 0, axis=-1).sum()), 'seconds': round(time.monotonic() - self.started, 2)}
    self.rows.append(row)
    if frame % self.a.fps == 0:
        print(json.dumps(row), flush=True)

def radiance_sigil_native_fire_fed(self):
    temp = self.state[0, 5]
    soot = self.state[0, 6]
    reaction = self.state[0, 7]
    hot = ((temp - 0.28) / 1.8).clamp(0, 1)
    sigma = (soot * 4.4 + reaction * 0.025).clamp(0, 16)
    tau = torch.flip(torch.cumsum(torch.flip(soot, [0]), dim=0), [0]) * self.h[2] * 4.4
    key = torch.exp(-tau)
    colors = torch.stack([torch.ones_like(hot), 0.035 + 0.93 * hot.pow(1.3), 0.002 + 0.72 * hot.pow(3.0)], dim=-1)
    front = reaction.clamp_min(0).pow(0.95)
    emission = colors * (front * 6.5)[..., None]
    light = torch.tensor([0.02, 0.019, 0.025], device=self.device) + key[..., None] * torch.tensor([1.4, 1.1, 0.85], device=self.device)
    rgb = emission + soot[..., None] * 4.4 * 0.42 * light / (4 * math.pi)
    return (rgb, sigma)

def pixels_bending_air(self, frame):
    density = self.state[0, 6]
    sigma = density.clamp_min(0).pow(1.45) * 3.0
    top = torch.flip(torch.cumsum(torch.flip(sigma, [0]), dim=0), [0]) * self.h[2]
    back = torch.flip(torch.cumsum(torch.flip(sigma, [1]), dim=1), [1]) * self.h[1]
    lit = torch.exp(-top * 1.7 - back * 0.8)
    cosine = (2 - self.y) / torch.sqrt((self.x + 2) ** 2 + (2 - self.y) ** 2 + (self.z - 4) ** 2).clamp_min(0.1)
    phase = (1 - 0.45 ** 2) / (1 + 0.45 ** 2 - 2 * 0.45 * cosine).clamp_min(0.05).pow(1.5)
    rgb = sigma[..., None] * (lit * phase * 4.2 + 0.18)[..., None] * torch.tensor([0.66, 0.76, 0.83], device=self.device)
    atten = torch.exp(-sigma * self.h[1])
    transmission = torch.cat([torch.ones_like(atten[:, :1]), torch.cumprod(atten[:, :-1], dim=1)], dim=1)
    linear = (transmission[..., None] * rgb * (1 - atten[..., None]) / sigma[..., None].clamp_min(1e-06)).sum(1)
    linear = F.interpolate(linear.permute(2, 0, 1).flip(1)[None], size=(768, 1920), mode='bicubic', align_corners=False).clamp_min(0)
    blur = F.avg_pool2d(F.avg_pool2d(linear, (1, 21), stride=1, padding=(0, 10)), (21, 1), stride=1, padding=(10, 0))
    linear = (linear + blur * 0.005) * 1.05
    linear = F.pad(linear, (0, 0, 120, 192))
    fade = 1.0
    linear = linear * fade
    im = (linear * (2.51 * linear + 0.03) / (linear * (2.43 * linear + 0.59) + 0.14)).clamp(0, 1)
    im = torch.where(im <= 0.0031308, im * 12.92, 1.055 * im.pow(1 / 2.4) - 0.055)
    pixels = (im[0].permute(1, 2, 0) * 255).byte().cpu().numpy()
    return pixels

def pixels_air_material_v2(self, frame):
    density = self.state[0, 6]
    sigma = density.clamp_min(0).pow(1.45) * 3.0
    top = torch.flip(torch.cumsum(torch.flip(sigma, [0]), dim=0), [0]) * self.h[2]
    back = torch.flip(torch.cumsum(torch.flip(sigma, [1]), dim=1), [1]) * self.h[1]
    lit = torch.exp(-top * 1.7 - back * 0.8)
    cosine = (2 - self.y) / torch.sqrt((self.x + 2) ** 2 + (2 - self.y) ** 2 + (self.z - 4) ** 2).clamp_min(0.1)
    phase = (1 - 0.45 ** 2) / (1 + 0.45 ** 2 - 2 * 0.45 * cosine).clamp_min(0.05).pow(1.5)
    rgb = sigma[..., None] * (lit * phase * 2.35 + 0.18)[..., None] * torch.tensor([0.66, 0.76, 0.83], device=self.device)
    atten = torch.exp(-sigma * self.h[1])
    transmission = torch.cat([torch.ones_like(atten[:, :1]), torch.cumprod(atten[:, :-1], dim=1)], dim=1)
    linear = (transmission[..., None] * rgb * (1 - atten[..., None]) / sigma[..., None].clamp_min(1e-06)).sum(1)
    linear = F.interpolate(linear.permute(2, 0, 1).flip(1)[None], size=(768, 1920), mode='bicubic', align_corners=False).clamp_min(0)
    blur = F.avg_pool2d(F.avg_pool2d(linear, (1, 21), stride=1, padding=(0, 10)), (21, 1), stride=1, padding=(10, 0))
    linear = (linear + blur * 0.005) * 0.72
    linear = F.pad(linear, (0, 0, 120, 192))
    fade = 1.0
    linear = linear * fade
    im = (linear * (2.51 * linear + 0.03) / (linear * (2.43 * linear + 0.59) + 0.14)).clamp(0, 1)
    im = torch.where(im <= 0.0031308, im * 12.92, 1.055 * im.pow(1 / 2.4) - 0.055)
    pixels = (im[0].permute(1, 2, 0) * 255).byte().cpu().numpy()
    return pixels

def radiance_fire_material(self):
    temp = self.state[0, 5]
    soot = self.state[0, 6]
    reaction = self.state[0, 7]
    hot = ((temp - 0.28) / 1.8).clamp(0, 1)
    sigma = (soot * 4.4 + reaction * 0.025).clamp(0, 16)
    tau = torch.flip(torch.cumsum(torch.flip(soot, [0]), dim=0), [0]) * self.h[2] * 4.4
    key = torch.exp(-tau)
    colors = torch.stack([torch.ones_like(hot), 0.035 + 0.93 * hot.pow(1.3), 0.002 + 0.72 * hot.pow(3.0)], dim=-1)
    front = reaction.clamp_min(0).pow(1.15)
    emission = colors * (front * 2.7)[..., None]
    light = torch.tensor([0.02, 0.019, 0.025], device=self.device) + key[..., None] * torch.tensor([1.4, 1.1, 0.85], device=self.device)
    rgb = emission + soot[..., None] * 4.4 * 0.42 * light / (4 * math.pi)
    return (rgb, sigma)


def radiance_style02(self):
    temp = self.state[0, 5]
    soot = self.state[0, 6]
    reaction = self.state[0, 7]
    hot = ((temp - 0.28) / 1.8).clamp(0, 1)
    sigma = (soot * 4.4 + reaction * 0.025).clamp(0, 16)
    tau = torch.flip(torch.cumsum(torch.flip(soot, [0]), dim=0), [0]) * self.h[2] * 4.4
    key = torch.exp(-tau)
    colors = torch.stack([torch.ones_like(hot), 0.035 + 0.93 * hot.pow(1.3), 0.002 + 0.72 * hot.pow(3.0)], dim=-1)
    front = reaction.clamp_min(0).pow(0.95)
    emission = colors * (front * 6.5)[..., None]
    light = torch.tensor([0.02, 0.019, 0.025], device=self.device) + key[..., None] * torch.tensor([1.4, 1.1, 0.85], device=self.device)
    rgb = emission + soot[..., None] * 4.4 * 0.42 * light / (4 * math.pi)
    return (rgb, sigma)


def pixels_style02_fire(self, frame):
    rgb, sigma = self.radiance()
    atten = torch.exp(-sigma * self.h[1])
    transmission = torch.cat([torch.ones_like(atten[:, :1]), torch.cumprod(atten[:, :-1], dim=1)], dim=1)
    linear = (transmission[..., None] * rgb * (1 - atten[..., None]) / sigma[..., None].clamp_min(1e-06)).sum(1)
    linear = F.interpolate(linear.permute(2, 0, 1).flip(1)[None], size=(1080, 1920), mode='bicubic', align_corners=False).clamp_min(0)
    blur = F.avg_pool2d(F.avg_pool2d(linear, (1, 21), stride=1, padding=(0, 10)), (21, 1), stride=1, padding=(10, 0))
    linear = (linear + blur * 0.018) * 0.72
    linear = linear
    fade = 1.0
    linear = linear * fade
    im = (linear * (2.51 * linear + 0.03) / (linear * (2.43 * linear + 0.59) + 0.14)).clamp(0, 1)
    im = torch.where(im <= 0.0031308, im * 12.92, 1.055 * im.pow(1 / 2.4) - 0.055)
    pixels = (im[0].permute(1, 2, 0) * 255).byte().cpu().numpy()
    return pixels


def pixels_style02_air(self, frame):
    density = self.state[0, 6]
    sigma = density.clamp_min(0).pow(1.24) * 3.0
    top = torch.flip(torch.cumsum(torch.flip(sigma, [0]), dim=0), [0]) * self.h[2]
    back = torch.flip(torch.cumsum(torch.flip(sigma, [1]), dim=1), [1]) * self.h[1]
    left = torch.cumsum(sigma, dim=2) * self.h[0]
    lit = torch.exp(-top * 1.7 - back * 0.8)
    side = torch.exp(-left * 1.4 - top * 0.65)
    cosine = (2 - self.y) / torch.sqrt((self.x + 2) ** 2 + (2 - self.y) ** 2 + (self.z - 4) ** 2).clamp_min(0.1)
    phase = (1 - 0.45 ** 2) / (1 + 0.45 ** 2 - 2 * 0.45 * cosine).clamp_min(0.05).pow(1.5)
    rgb = sigma[..., None] * (lit * phase * 3.9 + side * 0.85 + 0.11)[..., None] * torch.tensor([0.66, 0.76, 0.83], device=self.device)
    atten = torch.exp(-sigma * self.h[1])
    transmission = torch.cat([torch.ones_like(atten[:, :1]), torch.cumprod(atten[:, :-1], dim=1)], dim=1)
    linear = (transmission[..., None] * rgb * (1 - atten[..., None]) / sigma[..., None].clamp_min(1e-06)).sum(1)
    linear = F.interpolate(linear.permute(2, 0, 1).flip(1)[None], size=(1080, 1920), mode='bicubic', align_corners=False).clamp_min(0)
    blur = F.avg_pool2d(F.avg_pool2d(linear, (1, 21), stride=1, padding=(0, 10)), (21, 1), stride=1, padding=(10, 0))
    linear = (linear + blur * 0.002) * 1.05
    linear = linear
    fade = 1.0
    linear = linear * fade
    im = (linear * (2.51 * linear + 0.03) / (linear * (2.43 * linear + 0.59) + 0.14)).clamp(0, 1)
    im = torch.where(im <= 0.0031308, im * 12.92, 1.055 * im.pow(1 / 2.4) - 0.055)
    pixels = (im[0].permute(1, 2, 0) * 255).byte().cpu().numpy()
    return pixels
