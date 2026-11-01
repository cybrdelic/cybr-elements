"""One state/grid/control owner; independent instances, CPU or CUDA backend."""
import math, time, importlib
from collections import OrderedDict
from pathlib import Path
from types import MethodType
import numpy as np
import torch
from element_flow import CollocatedFlow
from element_choreography import advance,steer_broad_flow

class ElementSession:
    step=advance
    steer_broad_flow=steer_broad_flow

    def __init__(self,spec,args,device='cpu',motion=None,source_fields=None):
        self.spec,self.a,self.device=spec,args,device
        self.ROOT=Path(__file__).resolve().parent
        self.out=spec.frames;self.rows=[];self.started=time.monotonic()
        if args.fps<=0:raise ValueError('Positive cadence required')
        if args.seconds is None:args.seconds=spec.default_native_frames/args.fps if spec.default_native_frames else spec.default_seconds
        self.FPS=self.SIM_FPS=args.fps;self.TOTAL=round(args.seconds*args.fps)
        if args.pilot and spec.pilot:self.TOTAL=spec.pilot
        if args.fps<=0 or args.substeps<=0 or min(args.size)<3:raise ValueError('Positive cadence and grid dimensions >=3 required')
        self.motion_identity=(spec.motion or 'style02-source') if motion is None else motion.get("identity")
        if spec.motion is None and motion is None:
            motion=dict(MODE='arc',START=.30,WRITE=3.60,nozzle_pose=None,nozzle_turn=None)
        if motion is None:
            module=importlib.import_module(spec.motion)
            motion=dict(MODE=module.MODE,START=module.START,WRITE=module.WRITE,nozzle_pose=module.pose,nozzle_turn=module.turn_rate)
        for name in ('MODE','START','WRITE','nozzle_pose','nozzle_turn'):setattr(self,name,motion[name])
        for name in ('source_reaction','turn','radiance','pixels','capture'):setattr(self,name,MethodType(getattr(spec,name),self) if getattr(spec,name) is not None else None)
        self.X, self.Y, self.Z = self.a.size
        self.shape = (self.Z, self.Y, self.X)
        self.lo = np.array(spec.bounds[0] if spec.bounds else [-5.25, -3.0 if self.MODE == 'word' else -0.6, 0], np.float32)
        self.extent = np.array(spec.bounds[1] if spec.bounds else [10.5, 6.0 if self.MODE == 'word' else 1.2, 4.2], np.float32)
        self.velocity_size = np.array([66, 38, 64])
        if self.a.padded_domain:
            if np.any(np.array(self.a.size) < [264, 152, 320]):
                raise ValueError('Padded domain cannot lower production resolution')
            self.expanded = self.extent * (np.array(self.a.size) - 1) / (np.array([264, 152, 320]) - 1)
            self.lo[:2] -= (self.expanded[:2] - self.extent[:2]) * 0.5
            self.extent = self.expanded.astype(np.float32)
            self.velocity_size = np.ceil(self.velocity_size * np.array(self.a.size) / [264, 152, 320]).astype(int)
        self.h = torch.tensor(self.extent / (np.array(self.a.size) - 1), device=self.device)
        self.zz, self.yy, self.xx = torch.meshgrid(*(torch.linspace(-1, 1, self.n, device=self.device) for self.n in self.shape), indexing='ij')
        self.grid = torch.stack([self.xx, self.yy, self.zz], dim=-1)[None]
        if not spec.source_asset:
            self.x = self.lo[0] + (self.xx + 1) * float(self.extent[0]) * 0.5
            self.y = self.lo[1] + (self.yy + 1) * float(self.extent[1]) * 0.5
            self.z = self.lo[2] + (self.zz + 1) * float(self.extent[2]) * 0.5
        if spec.source_asset:
            self.x=torch.linspace(float(self.lo[0]),float(self.lo[0]+self.extent[0]),self.X,device=device)[None,None,:]
            self.y=torch.linspace(float(self.lo[1]),float(self.lo[1]+self.extent[1]),self.Y,device=device)[None,:,None]
            self.z=torch.linspace(float(self.lo[2]),float(self.lo[2]+self.extent[2]),self.Z,device=device)[:,None,None]
            owned=source_fields is None
            source_fields=np.load(self.ROOT/spec.source_asset) if owned else source_fields
            try:
                for field in ('support','arrival','dirx','dirz','sdf'):
                    if source_fields[field].shape!=(self.Z,self.X):raise ValueError('Source grid mismatch; production source is never resampled')
                for target,field in [('support','support'),('arrival','arrival'),('tangent_x','dirx'),('tangent_z','dirz')]:
                    setattr(self,target,torch.from_numpy(source_fields[field]).to(device)[:,None,:])
                self.halfwidth=torch.from_numpy(source_fields['sdf']).to(device)[:,None,:].clamp_min(0)
                self.sheet_depth=spec.sheet_depth[0]+spec.sheet_depth[1]*(self.halfwidth/.27).clamp(0,1).sqrt()
            finally:
                if owned:source_fields.close()
        self.step_scale = (2 / torch.tensor(self.extent, device=self.device)).view(1, 3, 1, 1, 1)
        self.state = torch.zeros((1, 8, *self.shape), device=self.device)
        self.state[:, 4] = 1
        self.edge = torch.minimum(torch.minimum(1 - self.xx.abs(), 1 - self.yy.abs()), 1 - self.zz.abs()).clamp(0, 1)
        self.sponge = (self.edge / 0.1).clamp(0, 1)[None, None]
        if not spec.source_asset:
            self.source = torch.exp(-((self.x / 0.32) ** 4 + (self.y / 0.245) ** 4 + ((self.z - 0.34) / 0.075) ** 4))
            self.source = (self.source > 0.01) * self.source
        if self.a.gesture_version == '22b':
            self.turn_support = torch.exp(-((((self.x - 0.8) ** 2 + self.y * self.y).sqrt() / 1.5) ** 4 + ((self.z - 1.0) / 2.0) ** 4))
        self.frequency = [torch.fft.fftfreq(self.n, device=self.device) for self.n in self.shape[:2]] + [torch.fft.rfftfreq(self.X, device=self.device)]
        self.kz, self.ky, self.kx = torch.meshgrid(*self.frequency, indexing='ij')
        self.k = torch.stack([torch.sin(2 * math.pi * self.kx) / self.h[0], torch.sin(2 * math.pi * self.ky) / self.h[1], torch.sin(2 * math.pi * self.kz) / self.h[2]])
        self.k2 = (self.k * self.k).sum(0).clamp_min(1e-12)
        self.dt = 1 / (self.a.fps * self.a.substeps)
        self.flow = CollocatedFlow(grid=self.grid, step_scale=self.step_scale, dt=self.dt, h=self.h, k=self.k, k2=self.k2, sponge=self.sponge, shape=self.shape)
        self.reservoir=torch.zeros(self.shape,device=device) if spec.reservoir else None
        self.control_cache=OrderedDict()
        if args.gesture_version.startswith('21'):
            module=importlib.import_module('bending_fire_choreography_v'+args.gesture_version)
            self.guide_strength=module.strength
            self.controller=module.FlowGuide(self.lo,self.extent,np.array(args.size)//4)
        if args.gesture_version=='22b':
            self.turn_rate=importlib.import_module('bending_fire_moves_v22b').turn_rate
        self.next_frame=0

    def control_frame(self,index):
        if index not in self.control_cache:
            self.control_cache[index]=torch.from_numpy(self.controller.frame(index)).to(self.device)
            if len(self.control_cache)>3:self.control_cache.popitem(last=False)
        self.control_cache.move_to_end(index)
        return self.control_cache[index]

    def advance_frame(self):
        frame=self.next_frame
        for sub in range(self.a.substeps):
            divergence=self.step((frame+sub/self.a.substeps)/self.a.fps)
        if not torch.isfinite(self.state).all():raise RuntimeError('Nonfinite simulation state')
        if str(self.device).startswith('cuda') and torch.cuda.max_memory_allocated()>6.8*1024**3:
            raise RuntimeError('Original 6.8GiB CUDA memory budget exceeded')
        self.next_frame+=1
        return frame,divergence
