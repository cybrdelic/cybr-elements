"""Conservative viscous thin-film lava study on the retained lettering source.

Hydrostatic gravity drives a finite-volume Bingham mobility. The same face
flux transports volume and specific enthalpy. Radiation/convection cool a
lumped surface boundary coupled to the column; cooling raises viscosity.
This is a nominal 2.5-D look-development model, not the archived 3-D MPM
research pipeline, calibrated basalt rheology, or a solid-fracture solver.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import map_coordinates

RHO, CP, LATENT = 2600., 1200., 400000.
SOLIDUS, LIQUIDUS, AMBIENT = 1173., 1473., 293.15


def enthalpy(temperature):
    t = np.asarray(temperature)
    return CP*(t-AMBIENT) + LATENT*np.clip((t-SOLIDUS)/(LIQUIDUS-SOLIDUS), 0, 1)


def temperature(h):
    e = np.asarray(h)
    e0, e1 = enthalpy(SOLIDUS), enthalpy(LIQUIDUS)
    return np.where(e < e0, AMBIENT+e/CP,
                    np.where(e <= e1, SOLIDUS+(e-e0)/(CP+LATENT/(LIQUIDUS-SOLIDUS)),
                             LIQUIDUS+(e-e1)/CP))


class LavaFilm:
    def __init__(self, support, dx, *, depth=.25, viscosity=80000., yield_stress=75.):
        s = np.asarray(support, dtype=np.float64)
        if s.ndim != 2 or min(s.shape) < 3 or not np.isfinite(s).all() or np.any((s < 0)|(s > 1)):
            raise ValueError('support must be a finite two-dimensional field in [0,1]')
        if dx <= 0 or depth <= 0 or viscosity <= 0 or yield_stress < 0:
            raise ValueError('physical dimensions and viscosity must be positive')
        self.dx, self.mu0, self.yield_stress = float(dx), viscosity, yield_stress
        self.h = s*depth
        self.energy = RHO*self.h*enthalpy(LIQUIDUS)
        self.surface = np.full_like(s, LIQUIDUS)
        self.time, self.radiated = 0., 0.
        self.initial_volume = float(self.h.sum()*dx*dx)
        self.initial_energy = float(self.energy.sum()*dx*dx)
        self.velocity = np.zeros((*s.shape, 2))

    def bulk_temperature(self):
        specific = np.divide(self.energy, RHO*self.h, out=np.zeros_like(self.h), where=self.h > 1e-10)
        return temperature(specific)

    def mobility(self):
        t = self.bulk_temperature()
        mu = self.mu0*np.exp(np.clip(9000*(1/np.maximum(t, AMBIENT)-1/LIQUIDUS), 0, 18))
        return 9.81*RHO*self.h**3/(3*mu)

    def _step(self, dt):
        h, dx = self.h, self.dx
        mob = self.mobility()
        qx = np.zeros((h.shape[0], h.shape[1]+1))
        qy = np.zeros((h.shape[0]+1, h.shape[1]))
        for q, axis in ((qx, 1), (qy, 0)):
            left = h[:, :-1] if axis == 1 else h[:-1, :]
            right = h[:, 1:] if axis == 1 else h[1:, :]
            ml = mob[:, :-1] if axis == 1 else mob[:-1, :]
            mr = mob[:, 1:] if axis == 1 else mob[1:, :]
            slope = (right-left)/dx
            tau = RHO*9.81*(left+right)*.5*np.abs(slope)
            ratio = np.clip(self.yield_stress/np.maximum(tau, 1e-20), 0, 1)
            plug = 1-1.5*ratio+.5*ratio**3
            value = -(ml+mr)*.5*slope*plug
            if axis == 1:
                q[:, 1:-1] = value
            else:
                q[1:-1, :] = value
        # Limit each face by its donor's available volume. Closed outer faces
        # remain zero, so no mass is clipped or silently lost at a boundary.
        outgoing = (np.maximum(qx[:, 1:], 0)+np.maximum(-qx[:, :-1], 0)
                    +np.maximum(qy[1:, :], 0)+np.maximum(-qy[:-1, :], 0))
        available = np.minimum(1, h*dx/(dt*np.maximum(outgoing, 1e-30)))
        qx[:, 1:-1] *= np.where(qx[:, 1:-1] >= 0, available[:, :-1], available[:, 1:])
        qy[1:-1, :] *= np.where(qy[1:-1, :] >= 0, available[:-1, :], available[1:, :])
        specific = np.divide(self.energy, RHO*h, out=np.zeros_like(h), where=h > 1e-12)
        ex, ey = np.zeros_like(qx), np.zeros_like(qy)
        ex[:, 1:-1] = RHO*qx[:, 1:-1]*np.where(qx[:, 1:-1] >= 0, specific[:, :-1], specific[:, 1:])
        ey[1:-1, :] = RHO*qy[1:-1, :]*np.where(qy[1:-1, :] >= 0, specific[:-1, :], specific[1:, :])
        self.h = h-dt/dx*(qx[:, 1:]-qx[:, :-1]+qy[1:, :]-qy[:-1, :])
        self.energy -= dt/dx*(ex[:, 1:]-ex[:, :-1]+ey[1:, :]-ey[:-1, :])
        if np.min(self.h) < -1e-12 or np.min(self.energy) < -1e-5:
            raise FloatingPointError('Conservative lava transport lost positivity')
        self.velocity[..., 0] = np.divide((qx[:, 1:]+qx[:, :-1])*.5, self.h,
                                           out=np.zeros_like(h), where=self.h > 1e-8)
        self.velocity[..., 1] = np.divide((qy[1:, :]+qy[:-1, :])*.5, self.h,
                                           out=np.zeros_like(h), where=self.h > 1e-8)
        bulk = self.bulk_temperature()
        skin_depth = np.maximum(np.minimum(self.h*.15, .004), 1e-5)
        capacity = RHO*CP*skin_depth
        conductance = 1.5/skin_depth
        old = np.minimum(self.surface, bulk)
        skin = old.copy()
        # Implicit nonlinear surface balance avoids negative temperatures or
        # a time-step-dependent crust as very thin border cells cool.
        for _ in range(8):
            loss = .95*5.670374419e-8*(skin**4-AMBIENT**4)+12*(skin-AMBIENT)
            residual = capacity*(skin-old)/dt-conductance*(bulk-skin)+loss
            jacobian = capacity/dt+conductance+.95*5.670374419e-8*4*skin**3+12
            skin = np.clip(skin-residual/jacobian, AMBIENT, np.maximum(AMBIENT, bulk))
        flux = .95*5.670374419e-8*(skin**4-AMBIENT**4)+12*(skin-AMBIENT)
        cooled = np.minimum(self.energy, dt*flux)*(self.h > 1e-8)
        self.energy -= cooled
        self.radiated += float(cooled.sum()*dx*dx)
        self.surface = np.where(self.h > 1e-8, skin, AMBIENT)
        self.time += dt

    def advance(self, duration):
        remaining = duration
        while remaining > 1e-10:
            max_mobility = float(self.mobility().max())
            dt = min(remaining, .05, .18*self.dx*self.dx/max(max_mobility, 1e-12))
            self._step(dt)
            remaining -= dt
        if not np.isfinite(self.h).all() or not np.isfinite(self.energy).all():
            raise FloatingPointError('Nonfinite lava state')

    def diagnostics(self):
        volume = float(self.h.sum()*self.dx*self.dx)
        e = float(self.energy.sum()*self.dx*self.dx)
        return {'seconds': self.time, 'volume_m3': volume,
                'volume_error_relative': abs(volume-self.initial_volume)/max(self.initial_volume, 1e-20),
                'energy_balance_relative': abs(e+self.radiated-self.initial_energy)/max(self.initial_energy, 1e-20),
                'min_height': float(self.h.min()), 'maximum_speed': float(np.linalg.norm(self.velocity, axis=-1).max()),
                'surface_min_K': float(self.surface[self.h > .003].min()),
                'surface_max_K': float(self.surface.max()), 'radiated_J': self.radiated}


def source_support(path, nx=320):
    with np.load(path, allow_pickle=False) as data:
        extent, lo = data['extent'].copy(), data['lo'].copy()
        dx = float(extent[0]/(nx-1))
        ny = round(float(extent[2]/dx))+1
        yy, xx = np.meshgrid(np.linspace(0, data['support'].shape[0]-1, ny),
                             np.linspace(0, data['support'].shape[1]-1, nx), indexing='ij')
        sdf = map_coordinates(data['sdf'], [yy, xx], order=1)
        support = np.clip(sdf/(dx*.8)+.5, 0, 1)
        support *= np.clip((sdf+.02)/.12, 0, 1)
    y = lo[2]+np.arange(ny)*dx
    y_center = float((y[:, None]*support).sum()/max(support.sum(), 1e-20))
    return support, dx, (float(lo[0]), float(lo[2]-y_center))


def surface_mesh(height, dx, origin):
    from skimage.measure import marching_cubes

    h = np.asarray(height, np.float32)
    dz = min(dx*.28, .012)
    z = np.arange(-dz, float(h.max())+dz*2, dz, dtype=np.float32)
    field = np.minimum(h[..., None]-z, z-.003)
    # Remove the zero-height exterior; only the true film carries geometry.
    field = np.minimum(field, (h-.004)[..., None])
    vertices, faces, _, _ = marching_cubes(field, level=0, spacing=(dx, dx, dz),
                                           allow_degenerate=False)
    result = np.column_stack((vertices[:, 1]+origin[0], vertices[:, 0]+origin[1], vertices[:, 2]-dz))
    return result.astype(np.float32), faces[:, [0, 2, 1]]


def lava_material():
    import bpy
    from studio_scene import node, math_node, noise, ramp, principled_material

    m, p = principled_material('Studio / thermally cooled basalt skin', (.028, .022, .018), .78)
    t = m.node_tree
    position = node(t, 'ShaderNodeNewGeometry').outputs['Position']
    surface = node(t, 'ShaderNodeAttribute'); surface.attribute_name = 'surface_temperature'
    bulk = node(t, 'ShaderNodeAttribute'); bulk.attribute_name = 'bulk_temperature'
    cells = node(t, 'ShaderNodeTexVoronoi', 'Unresolved crust plate boundaries')
    cells.feature = 'DISTANCE_TO_EDGE'
    cells.inputs['Scale'].default_value = 3.5
    warp = node(t, 'ShaderNodeTexNoise'); warp.inputs['Scale'].default_value = 3.7
    warp.inputs['Detail'].default_value = 5; t.links.new(position, warp.inputs['Vector'])
    distort = node(t, 'ShaderNodeVectorMath'); distort.operation = 'SCALE'; distort.inputs['Scale'].default_value = .65
    t.links.new(warp.outputs['Color'], distort.inputs[0])
    add = node(t, 'ShaderNodeVectorMath'); add.operation = 'ADD'
    t.links.new(position, add.inputs[0]); t.links.new(distort.outputs[0], add.inputs[1])
    t.links.new(add.outputs[0], cells.inputs['Vector'])
    crack = ramp(t, cells.outputs['Distance'], [(.003, (1,)*3), (.055, (0,)*3)], 'Subsurface fissures')
    breaks = noise(t, position, 2.1, 5, 'Heterogeneous ruptured skin')
    broken = math_node(t, 'MULTIPLY', crack, ramp(t, breaks, [(.39, (0,)*3), (.62, (1,)*3)], 'Discontinuous crust'))
    pockets = ramp(t, breaks, [(.54, (0,)*3), (.65, (1,)*3)], 'Exposed molten pockets')
    broken = math_node(t, 'MAXIMUM', broken, pockets)
    crust = math_node(t, 'MULTIPLY', math_node(t, 'SUBTRACT', surface.outputs['Fac'], 1410), 1/63)
    opened = math_node(t, 'MAXIMUM', crust, broken)
    opened = math_node(t, 'MINIMUM', math_node(t, 'MAXIMUM', opened, 0), 1)
    blackbody = node(t, 'ShaderNodeBlackbody')
    t.links.new(bulk.outputs['Fac'], blackbody.inputs[0])
    t.links.new(blackbody.outputs['Color'], p.inputs['Emission Color'])
    t.links.new(math_node(t, 'MULTIPLY', opened, 1.6), p.inputs['Emission Strength'])
    albedo = ramp(t, opened, [(.04, (.025, .020, .017)), (.8, (.14, .032, .006))], 'Crust to liquid reflectance')
    t.links.new(albedo, p.inputs['Base Color'])
    pores = noise(t, position, 100, 3, 'Vesicular basalt relief')
    bump = node(t, 'ShaderNodeBump'); bump.inputs['Strength'].default_value = .65
    bump.inputs['Distance'].default_value = .025
    t.links.new(pores, bump.inputs['Height']); t.links.new(bump.outputs['Normal'], p.inputs['Normal'])
    return m


def build_mesh_object(film, origin, material, previous=None):
    import bpy

    if previous is not None:
        mesh = previous.data
        bpy.data.objects.remove(previous, do_unlink=True)
        bpy.data.meshes.remove(mesh)
    vertices, faces = surface_mesh(film.h, film.dx, origin)
    mesh = bpy.data.meshes.new('Conservative viscous lava surface')
    mesh.from_pydata(vertices.tolist(), [], faces.tolist()); mesh.update()
    o = bpy.data.objects.new('Studio / cooling viscous lava', mesh)
    bpy.context.collection.objects.link(o); mesh.materials.append(material)
    for p in mesh.polygons:
        p.use_smooth = True
    relief = o.modifiers.new('Unresolved vesicular skin relief', 'DISPLACE')
    tx = bpy.data.textures.new('Lava skin microrelief', 'DISTORTED_NOISE')
    tx.noise_scale = .065; tx.distortion = 1.4
    relief.texture = tx; relief.texture_coords = 'LOCAL'
    relief.strength = .045; relief.mid_level = .5
    coordinates = np.stack([(vertices[:, 1]-origin[1])/film.dx, (vertices[:, 0]-origin[0])/film.dx])
    for name, field in [('surface_temperature', film.surface), ('bulk_temperature', film.bulk_temperature())]:
        attr = mesh.attributes.new(name, 'FLOAT', 'POINT')
        attr.data.foreach_set('value', map_coordinates(field, coordinates, order=1, mode='nearest').astype(np.float32))
    return o
