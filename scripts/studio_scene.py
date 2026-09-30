"""Shared, physically lit look-development for the seven element films.

This module changes optics and presentation, never the retained FLIP or Bullet
state. All coordinates are scene coordinates; no screen-space glyph masks,
painted highlights, film pixels, or generated imagery are used.
"""
from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector


def node(tree, kind, name=None):
    value = tree.nodes.new(kind)
    if name:
        value.name = value.label = name
    return value


def math_node(tree, operation, a, b=None):
    n = node(tree, 'ShaderNodeMath')
    n.operation = operation
    for i, value in enumerate((a, b)):
        if value is None:
            continue
        if isinstance(value, (float, int)):
            n.inputs[i].default_value = value
        else:
            tree.links.new(value, n.inputs[i])
    return n.outputs[0]


def ramp(tree, source, stops, name):
    n = node(tree, 'ShaderNodeValToRGB', name)
    cr = n.color_ramp
    cr.interpolation = 'EASE'
    cr.elements.remove(cr.elements[1])
    for i, (position, color) in enumerate(stops):
        e = cr.elements[0] if i == 0 else cr.elements.new(position)
        e.position = position
        e.color = (*color, 1) if len(color) == 3 else color
    tree.links.new(source, n.inputs['Fac'])
    return n.outputs['Color']


def noise(tree, position, scale, detail=3, name=None):
    n = node(tree, 'ShaderNodeTexNoise', name)
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = detail
    n.inputs['Roughness'].default_value = .65
    tree.links.new(position, n.inputs['Vector'])
    return n.outputs['Fac']


def principled_material(name, color, roughness):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Roughness'].default_value = roughness
    return m, p


def ice_material(frosted=False):
    """Clear dielectric, local entrained-air scattering, and a frosted skin."""
    m, p = principled_material('Studio / frosted fracture' if frosted else 'Studio / glacier ice',
                              (.985, .997, 1), .32 if frosted else .10)
    p.inputs['Transmission Weight'].default_value = 1
    p.inputs['IOR'].default_value = 1.31
    m.cycles.homogeneous_volume = False
    t = m.node_tree
    position = node(t, 'ShaderNodeNewGeometry').outputs['Position']
    cloud = noise(t, position, 3.5, 4, 'Entrained air / heterogeneous core')
    scatter_density = ramp(t, cloud, [(.35, (1.5,)*3), (.64, (5.5,)*3),
                                      (.83, (18,)*3)], 'Clear core to trapped air')
    scatter = node(t, 'ShaderNodeVolumeScatter')
    scatter.inputs['Color'].default_value = (.83, .93, 1, 1)
    scatter.inputs['Anisotropy'].default_value = .18
    t.links.new(scatter_density, scatter.inputs['Density'])
    absorption = node(t, 'ShaderNodeVolumeAbsorption')
    absorption.inputs['Color'].default_value = (.52, .84, .92, 1)
    absorption.inputs['Density'].default_value = .11
    add = node(t, 'ShaderNodeAddShader')
    t.links.new(scatter.outputs[0], add.inputs[0])
    t.links.new(absorption.outputs[0], add.inputs[1])
    t.links.new(add.outputs[0], t.nodes.get('Material Output').inputs['Volume'])
    skin = noise(t, position, 55, 2, 'Submillimetre frost')
    bump = node(t, 'ShaderNodeBump')
    bump.inputs['Strength'].default_value = .18 if frosted else .075
    bump.inputs['Distance'].default_value = .0018
    t.links.new(skin, bump.inputs['Height'])
    t.links.new(bump.outputs['Normal'], p.inputs['Normal'])
    if frosted:
        p.inputs['Roughness'].default_value = .32
    return m


def floor_material(kind):
    m, p = principled_material('Studio / graphite stage', (.008, .010, .014) if kind == 'lava' else (.028, .031, .035),
                              .32 if kind in ('water', 'ice') else .48)
    p.inputs['Specular IOR Level'].default_value = .35
    t = m.node_tree
    pos = node(t, 'ShaderNodeNewGeometry').outputs['Position']
    grains = noise(t, pos, 100, 2, 'Fine stage grain')
    bump = node(t, 'ShaderNodeBump')
    bump.inputs['Strength'].default_value = .10
    bump.inputs['Distance'].default_value = .0004
    t.links.new(grains, bump.inputs['Height'])
    t.links.new(bump.outputs['Normal'], p.inputs['Normal'])
    return m


def area(name, location, target, energy, color, width, height):
    d = bpy.data.lights.new('Studio / ' + name, 'AREA')
    d.energy = energy
    d.color = color
    d.shape = 'RECTANGLE'
    d.size = width
    d.size_y = height
    o = bpy.data.objects.new(d.name, d)
    bpy.context.collection.objects.link(o)
    o.location = location
    o.rotation_euler = (Vector(target)-o.location).to_track_quat('-Z', 'Y').to_euler()
    return o


class Studio:
    def __init__(self, scene, kind, *, camera=None, target=(0, 0, 1.65),
                 samples=None, orbit=True):
        self.scene, self.kind = scene, kind
        self.target = Vector(target)
        self.orbit = orbit
        self.camera = camera or scene.camera
        self.lava = kind == 'lava'
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'CPU'
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'
        scene.cycles.samples = samples or scene.cycles.samples
        scene.cycles.use_denoising = True
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_min_samples = min(16, scene.cycles.samples)
        scene.cycles.adaptive_threshold = .008
        scene.cycles.max_bounces = 16
        scene.cycles.transmission_bounces = 12
        scene.cycles.volume_bounces = 2
        scene.cycles.volume_step_rate = .5
        scene.cycles.sample_clamp_indirect = 8
        scene.render.use_persistent_data = True
        scene.render.filter_size = 1.25
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.look = 'AgX - Medium High Contrast'
        scene.view_settings.exposure = -.65 if self.lava else -.35 if kind == 'fire' else .2
        scene.render.use_motion_blur = False
        self._world()
        self._lights()
        self._floor()
        self._optics()
        self._compositor()
        self.update(4)

    def _world(self):
        s = self.scene
        if s.world is None:
            s.world = bpy.data.worlds.new('Studio world')
        s.world.use_nodes = True
        t = s.world.node_tree
        t.nodes.clear()
        env = node(t, 'ShaderNodeBackground', 'Neutral bounce environment')
        env.inputs['Color'].default_value = (.20, .23, .28, 1)
        env.inputs['Strength'].default_value = .20
        visible = node(t, 'ShaderNodeBackground', 'Visible charcoal background')
        visible.inputs['Color'].default_value = (.014, .020, .030, 1)
        visible.inputs['Strength'].default_value = .25
        rays = node(t, 'ShaderNodeLightPath')
        mix = node(t, 'ShaderNodeMixShader')
        t.links.new(rays.outputs['Is Camera Ray'], mix.inputs[0])
        t.links.new(env.outputs[0], mix.inputs[1])
        t.links.new(visible.outputs[0], mix.inputs[2])
        out = node(t, 'ShaderNodeOutputWorld')
        t.links.new(mix.outputs[0], out.inputs['Surface'])

    def _lights(self):
        # Retain actual point discharge lights. Replace the area-light rig.
        for o in list(bpy.data.objects):
            if o.type == 'LIGHT' and o.data.type == 'AREA':
                bpy.data.objects.remove(o, do_unlink=True)
        target = self.target
        factor = .35 if self.lava else .07 if self.kind in ('fire', 'lightning') else 1.0
        area('large neutral key', (-2.2, -4.4, 7.5), target, 1100*factor,
             (1, .96, .90), 6.0, 3.2)
        area('transmitted edge', (2.6, 2.5, 4.5), target, 1450*factor,
             (.83, .90, 1), 5.5, 2.3)
        area('front fill', (4.3, -5.0, 2.8), target, 300*factor,
             (.94, .96, 1), 4.0, 3.0)
        area('vertical reflection strip', (-4.5, -1.8, 2.8), target, 320*factor,
             (1, 1, 1), .8, 4.0)

    def _floor(self):
        material = floor_material(self.kind)
        floors = [o for o in bpy.data.objects if o.type == 'MESH' and
                  ('ground / visible' in o.name.lower() or 'ground / matches' in o.name.lower()
                   or (o.name.startswith('Plane') and len(o.data.polygons) == 1))]
        for o in floors:
            o.hide_render = True
        # A curved photographic sweep removes the finite-plane horizon behind
        # the lettering. Retained collision floors are left in the simulation.
        section = [(-100, -.006), (9, -.006)]
        for i in range(1, 33):
            angle = math.pi*.5*i/32
            section.append((9+8*math.sin(angle), 8*(1-math.cos(angle))-.006))
        section.append((17, 45))
        vertices = [(x, y, z) for y, z in section for x in (-100, 100)]
        faces = [(2*i, 2*i+1, 2*i+3, 2*i+2) for i in range(len(section)-1)]
        mesh = bpy.data.meshes.new('Seamless studio sweep')
        mesh.from_pydata(vertices, [], faces); mesh.update()
        sweep = bpy.data.objects.new('Studio / seamless contact stage', mesh)
        bpy.context.collection.objects.link(sweep)
        mesh.materials.append(material)
        for polygon in mesh.polygons:
            polygon.use_smooth = True

    def _optics(self):
        if self.kind == 'ice':
            core, fracture = ice_material(), ice_material(True)
            for o in bpy.data.objects:
                if o.type == 'MESH' and o.name.startswith('ice fracture'):
                    o.data.materials.clear()
                    o.data.materials.append(core)
                    o.data.materials.append(fracture)
        if self.kind == 'water':
            for m in bpy.data.materials:
                if m.name.startswith('Clear water /'):
                    p = m.node_tree.nodes.get('Principled BSDF')
                    p.inputs['Base Color'].default_value = (1, 1, 1, 1)
                    p.inputs['Roughness'].default_value = .012
                    for n in m.node_tree.nodes:
                        if n.type == 'BUMP':
                            n.inputs['Strength'].default_value = .35
                        if n.type == 'VOLUME_ABSORPTION':
                            n.inputs['Color'].default_value = (.68, .90, .96, 1)
                            n.inputs['Density'].default_value = .035
        if self.kind == 'earth':
            import numpy as np
            # Three-dimensional rest coordinates follow each rigid fragment.
            # The old front-projected UVs collapsed on extruded side faces,
            # stretching the scan into horizontal wood-like stripes.
            for o in bpy.data.objects:
                if o.type != 'MESH' or not o.name.startswith('Fracture '):
                    continue
                attr = o.data.attributes.new('stone_rest_position', 'FLOAT_VECTOR', 'POINT')
                rest = np.array([tuple(v.co+o.location) for v in o.data.vertices], np.float32)
                attr.data.foreach_set('vector', rest.ravel())
                tess = o.modifiers.new('Stone / fracture relief tessellation', 'SUBSURF')
                tess.subdivision_type = 'SIMPLE'; tess.levels = tess.render_levels = 1
                relief = o.modifiers.new('Stone / physical chipped surface', 'DISPLACE')
                tx = bpy.data.textures.new(o.name+' local relief', 'CLOUDS')
                tx.noise_scale = .11; tx.noise_depth = 2
                relief.texture = tx; relief.strength = .024; relief.mid_level = .5
                relief.texture_coords = 'LOCAL'
            for m in bpy.data.materials:
                if 'stone /' not in m.name.lower() and 'fresh fracture' not in m.name.lower():
                    continue
                t = m.node_tree
                pos = node(t, 'ShaderNodeNewGeometry').outputs['Position']
                rest = node(t, 'ShaderNodeAttribute'); rest.attribute_name = 'stone_rest_position'
                mapping = node(t, 'ShaderNodeVectorMath'); mapping.operation = 'SCALE'
                mapping.inputs['Scale'].default_value = .55
                t.links.new(rest.outputs['Vector'], mapping.inputs[0])
                for n in list(t.nodes):
                    if n.type == 'NORMAL_MAP':
                        n.inputs['Strength'].default_value = 0
                    if n.type == 'TEX_IMAGE':
                        n.projection = 'BOX'; n.projection_blend = .25
                        t.links.new(mapping.outputs[0], n.inputs['Vector'])
                # Fine geometry-normal detail supplements the retained scan.
                p = t.nodes.get('Principled BSDF')
                fine = noise(t, pos, 80, 2, 'Unresolved mineral grain')
                bump = node(t, 'ShaderNodeBump')
                bump.inputs['Distance'].default_value = .0012
                bump.inputs['Strength'].default_value = .25
                if p.inputs['Normal'].is_linked:
                    t.links.new(p.inputs['Normal'].links[0].from_socket, bump.inputs['Normal'])
                t.links.new(fine, bump.inputs['Height'])
                t.links.new(bump.outputs['Normal'], p.inputs['Normal'])

    def _compositor(self):
        s = self.scene
        s.use_nodes = True
        t = s.node_tree
        t.nodes.clear()
        source = node(t, 'CompositorNodeRLayers')
        result = source.outputs['Image']
        if self.kind in ('fire', 'lava', 'lightning'):
            glow = node(t, 'CompositorNodeGlare', 'Restricted optical halation')
            glow.glare_type = 'FOG_GLOW'
            glow.quality = 'HIGH'
            glow.threshold = 3.5
            glow.mix = -.96
            t.links.new(result, glow.inputs['Image'])
            result = glow.outputs['Image']
        out = node(t, 'CompositorNodeComposite')
        t.links.new(result, out.inputs[0])

    def update(self, seconds):
        c = self.camera
        if c is None:
            return
        if self.lava:
            c.location = (.55 + (.22*math.sin(seconds*.22) if self.orbit else 0), -9.2, 10.7)
            c.data.lens = 50
        else:
            c.location = (.75 + (.40*math.sin(seconds*.28) if self.orbit else 0), -13.5, 4.1)
            c.data.lens = 50
        c.rotation_euler = (self.target-c.location).to_track_quat('-Z', 'Y').to_euler()
        c.data.clip_start, c.data.clip_end = .05, 150
        c.data.dof.use_dof = False
        self.scene.camera = c


def lightning_pulse(age, delay=.066):
    """Short return-stroke train with a true quiet interval, no constant glow."""
    if age < 0 or age > .22:
        return 0.0
    return 1.7*math.exp(-age/.018) + .70*math.exp(-((age-delay)/.009)**2)


def update_lightning(namespace, seconds):
    import bisect

    families = namespace['families']
    active, energy = [], []
    # The authored groups share a brief discharge train, with propagation
    # delays and actual sub-shutter integration. Families still vary by group.
    for group in range(6):
        train = namespace['trains'][group]
        slowed = [(e[0]*2.15, *e[1:]) for e in train]
        index = max(0, bisect.bisect_right([e[0] for e in slowed], seconds)-1)
        begin, family, delay, gain = slowed[index]
        begin = math.floor((seconds+1e-9)/.46)*.46
        age = seconds-begin-group*.004
        power = sum(lightning_pulse(age+shutter, delay)
                    for shutter in (-.006, -.002, .002, .006))/4
        active.append(family)
        energy.append(power*gain)
        namespace['lamps'][group].data.energy = power*gain*140
    for ob, nodes, family, group in namespace['electric']:
        ob.hide_render = family != active[group] or energy[group] < .002
        for n, hierarchy in nodes:
            n.inputs['Color'].default_value = (.84, .91, 1, 1)
            n.inputs['Strength'].default_value = energy[group]*40*hierarchy
    return sum(energy)/6


def configure_lightning(namespace):
    """Give channel depth and finite emission importance sampling in Cycles."""
    for ob, nodes, family, group in namespace['electric']:
        for sp in ob.data.splines:
            for point in sp.points:
                x, y, z, w = point.co
                point.co.y = y + .10*math.sin(x*1.9+z*2.2+group*.7)
        for m in ob.data.materials:
            m.cycles.emission_sampling = 'AUTO'


def gas_volume(path: Path, kind: str):
    """Read native solver grids; Cycles supplies shadows and perspective rays."""
    bpy.ops.object.volume_add()
    o = bpy.context.object
    o.name = f'Studio / solved {kind} volume'
    o.data.filepath = str(path.resolve())
    m = bpy.data.materials.new(f'Studio / {kind} scattering')
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    out = node(t, 'ShaderNodeOutputMaterial')
    volume = node(t, 'ShaderNodeVolumePrincipled')
    volume.inputs['Color'].default_value = (.88, .91, .95, 1) if kind == 'air' else (.4, .48, .62, 1) if kind == 'lightning' else (.18, .16, .14, 1)
    volume.inputs['Anisotropy'].default_value = .35
    # A linked density already samples the grid. The built-in density-name
    # multiplier would otherwise apply the same grid twice, blurring its edges.
    volume.inputs['Density Attribute'].default_value = ''
    density = node(t, 'ShaderNodeAttribute')
    density.attribute_name = 'density'
    position = node(t, 'ShaderNodeNewGeometry').outputs['Position']
    detail = noise(t, position, 9, 4, 'Unresolved volumetric optical detail')
    erosion = math_node(t, 'MULTIPLY', math_node(t, 'MAXIMUM', math_node(t, 'SUBTRACT', .60, detail), 0), .16)
    shaped = math_node(t, 'MAXIMUM', math_node(t, 'SUBTRACT', density.outputs['Fac'], erosion), 0)
    shaped = math_node(t, 'MULTIPLY', shaped, math_node(t, 'MULTIPLY', detail, detail))
    t.links.new(math_node(t, 'MULTIPLY', shaped, 2.5 if kind == 'air' else .08 if kind == 'lightning' else 1.2),
                volume.inputs['Density'])
    if kind == 'fire':
        temperature = node(t, 'ShaderNodeAttribute')
        temperature.attribute_name = 'temperature'
        reaction = node(t, 'ShaderNodeAttribute')
        reaction.attribute_name = 'reaction'
        blackbody = node(t, 'ShaderNodeBlackbody')
        t.links.new(temperature.outputs['Fac'], blackbody.inputs[0])
        t.links.new(blackbody.outputs['Color'], volume.inputs['Emission Color'])
        flame = math_node(t, 'MULTIPLY', reaction.outputs['Fac'], math_node(t, 'MULTIPLY', detail, detail))
        t.links.new(math_node(t, 'MULTIPLY', flame, 12),
                    volume.inputs['Emission Strength'])
    elif kind == 'lightning':
        # Authored ionization radiance is gated by the actual discharge train.
        # Quiet intervals have zero emission; the solved 3-D tracer shapes it.
        power = node(t, 'ShaderNodeMath', 'Discharge haze power')
        power.operation = 'MULTIPLY'; power.inputs[1].default_value = 0
        t.links.new(shaped, power.inputs[0])
        t.links.new(power.outputs[0], volume.inputs['Emission Strength'])
        volume.inputs['Emission Color'].default_value = (.22, .40, 1, 1)
    t.links.new(volume.outputs['Volume'], out.inputs['Volume'])
    o.data.materials.append(m)
    return o
