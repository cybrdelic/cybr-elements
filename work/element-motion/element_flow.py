"""Shared collocated flow operators for the Fire/Air style-02 films.

This is the existing ELEMENTS Torch numerical method, not a general fluid API.
State is [1, 8, Z, Y, X]: velocity xyz, fuel, oxygen, normalized temperature,
soot, reaction rate. Source injection, chemistry and optics belong to consumers.
Grid sampling uses border extension; derivatives and the central-symbol FFT
projection are periodic, with the original boundary sponge applied beforehand.
Those historical boundary policies are preserved, not physical validation.
"""
import torch
import torch.nn.functional as F


class CollocatedFlow:
    """Own transport, vorticity confinement, projection and scalar edge policy."""

    def __init__(self, *, grid, step_scale, dt, h, k, k2, sponge, shape):
        self.grid, self.step_scale, self.dt = grid, step_scale, dt
        self.h, self.k, self.k2 = h, k, k2
        self.sponge, self.shape = sponge, shape

    def advect(self, q, vel, sign=1):
        lookup=self.grid-(vel*self.step_scale*self.dt*sign).permute(0,2,3,4,1)
        return F.grid_sample(q,lookup,mode='bilinear',padding_mode='border',align_corners=True)

    @staticmethod
    def derivative(q, axis, spacing):
        return (torch.roll(q,-1,axis)-torch.roll(q,1,axis))/(2*spacing)

    def divergence(self, v):
        derivative, h = self.derivative, self.h
        return derivative(v[0,0],2,h[0])+derivative(v[0,1],1,h[1])+derivative(v[0,2],0,h[2])

    def transport(self, state):
        """Semi-Lagrangian velocity and departure-limited MacCormack scalars."""
        advect = self.advect
        grid, step_scale, dt = self.grid, self.step_scale, self.dt
        vel=state[:,:3]
        moved=advect(state,vel)
        # Correct scalar diffusion, constrained to the source neighbourhood's range.
        returned=advect(moved,vel,-1)
        corrected=moved[:,3:]+.5*(state[:,3:]-returned[:,3:])
        upper=F.max_pool3d(state[:,3:],3,stride=1,padding=1)
        lower=-F.max_pool3d(-state[:,3:],3,stride=1,padding=1)
        # The limiter belongs to the departure neighbourhood, not the destination
        # cell. Clamping against the latter pinned fast jets to a one-cell front
        # and generated axis-aligned cuts whenever velocity exceeded one cell/dt.
        departure=grid-(vel*step_scale*dt).permute(0,2,3,4,1)
        upper=F.grid_sample(upper,departure,mode='nearest',padding_mode='border',align_corners=True)
        lower=F.grid_sample(lower,departure,mode='nearest',padding_mode='border',align_corners=True)
        moved[:,3:]=torch.maximum(lower,torch.minimum(upper,corrected)).clamp_min_(0)
        state=moved
        # These correction buffers are dead after the scalar update. Keeping them
        # alive through steering, vorticity and FFT projection retained gigabytes
        # of scratch storage without changing a single numerical result.
        del vel,returned,corrected,upper,lower,departure,moved
        return state

    def project(self, state):
        """Apply the original vorticity, sponge, FFT and oxygen edge sequence."""
        derivative, divergence = self.derivative, self.divergence
        h, dt, k, k2 = self.h, self.dt, self.k, self.k2
        sponge, shape = self.sponge, self.shape
        v, oxygen = state[0,:3], state[0,4]
        # Resolved vorticity confinement retains rolled shear structures.
        wx=derivative(v[2],1,h[1])-derivative(v[1],0,h[2])
        wy=derivative(v[0],0,h[2])-derivative(v[2],2,h[0])
        wz=derivative(v[1],2,h[0])-derivative(v[0],1,h[1])
        omega=torch.stack([wx,wy,wz]); magnitude=torch.linalg.vector_norm(omega,dim=0)
        grad=torch.stack([derivative(magnitude,2,h[0]),derivative(magnitude,1,h[1]),derivative(magnitude,0,h[2])])
        grad=grad/torch.linalg.vector_norm(grad,dim=0).clamp_min(1e-6)
        v.add_(torch.linalg.cross(grad,omega,dim=0)*(.12*dt))
        del wx,wy,wz,omega,magnitude,grad
        v.mul_(sponge[0])
        spectral=torch.fft.rfftn(v,dim=(-3,-2,-1))
        projection=(spectral*k).sum(0)/k2
        spectral-=k*projection
        # Small physical/numerical viscosity, not a temporal image filter.
        spectral*=torch.exp(-k2*(.000025*dt))
        v.copy_(torch.fft.irfftn(spectral,s=shape,dim=(-3,-2,-1)))
        state[:,3:4].mul_(sponge)
        state[:,5:].mul_(sponge)
        oxygen.lerp_(torch.ones_like(oxygen),1-sponge[0,0])
        return float(divergence(state[:,:3]).square().mean().sqrt())
