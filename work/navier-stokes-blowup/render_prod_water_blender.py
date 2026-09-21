"""Render the Navier-Stokes blowup study with the accepted CYBR water look.

This is intentionally patterned after bending-water-render-v5.py and the
accepted water-optical material pass: clear IOR 1.333 water, very low roughness,
volume absorption, black camera background with a reflection environment,
studio strip lights, actual surface-velocity motion blur, and mass-carrying
detached droplets.

Run inside Blender:
  blender -b --python render_prod_water_blender.py -- --input ... --out ...
"""
from __future__ import annotations
import argparse
from pathlib import Path
import json, math, sys, time

import bpy
import numpy as np
from mathutils import Vector


def args():
    raw=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--width",type=int,default=800)
    p.add_argument("--height",type=int,default=450)
    p.add_argument("--samples",type=int,default=24)
    return p.parse_args(raw)


def set_socket(node,names,value):
    for name in names:
        if name in node.inputs:
            node.inputs[name].default_value=value
            return


def look_at(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()


def add_area(name,loc,power,size,size_y,target,color=(1,1,1)):
    data=bpy.data.lights.new(name,"AREA")
    data.energy=power
    data.color=color
    data.shape="RECTANGLE"
    data.size=size
    data.size_y=size_y
    obj=bpy.data.objects.new(name,data)
    bpy.context.collection.objects.link(obj)
    obj.location=loc
    look_at(obj,target)
    return obj


def water_material():
    m=bpy.data.materials.new("CYBR accepted clear water optical transport")
    m.use_nodes=True
    n=m.node_tree.nodes
    l=m.node_tree.links
    p=n.get("Principled BSDF")
    set_socket(p,["Base Color"],(.995,.999,1.0,1))
    set_socket(p,["Roughness"],.006)
    set_socket(p,["IOR"],1.333)
    set_socket(p,["Transmission Weight","Transmission"],1.0)

    absorb=n.new("ShaderNodeVolumeAbsorption")
    absorb.inputs["Color"].default_value=(.24,.65,.72,1)
    absorb.inputs["Density"].default_value=.14
    l.new(absorb.outputs[0],n.get("Material Output").inputs["Volume"])
    return m


def stage_material():
    m=bpy.data.materials.new("wet charcoal slate")
    m.use_nodes=True
    p=m.node_tree.nodes.get("Principled BSDF")
    set_socket(p,["Base Color"],(.012,.017,.022,1))
    set_socket(p,["Roughness"],.32)
    return m


def configure_world():
    w=bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world=w
    w.use_nodes=True
    n=w.node_tree.nodes;l=w.node_tree.links
    for node in list(n):
        n.remove(node)
    out=n.new("ShaderNodeOutputWorld")
    env=n.new("ShaderNodeBackground")
    env.inputs["Strength"].default_value=.46
    ramp=n.new("ShaderNodeValToRGB")
    cr=ramp.color_ramp
    cr.elements.remove(cr.elements[1])
    cr.elements[0].position=0
    cr.elements[0].color=(.012,.020,.027,1)
    for pos,col in [
        (.13,(.025,.050,.060,1)),
        (.28,(.68,.78,.82,1)),
        (.35,(.08,.13,.15,1)),
        (.56,(.020,.030,.038,1)),
        (.82,(.16,.20,.23,1)),
    ]:
        e=cr.elements.new(pos);e.color=col
    tex=n.new("ShaderNodeTexCoord")
    sep=n.new("ShaderNodeSeparateXYZ")
    l.new(tex.outputs["Normal"],sep.inputs[0])
    l.new(sep.outputs["Z"],ramp.inputs[0])
    l.new(ramp.outputs[0],env.inputs["Color"])

    black=n.new("ShaderNodeBackground")
    black.inputs["Color"].default_value=(0,0,0,1)
    black.inputs["Strength"].default_value=0
    path=n.new("ShaderNodeLightPath")
    mix=n.new("ShaderNodeMixShader")
    l.new(path.outputs["Is Camera Ray"],mix.inputs[0])
    l.new(env.outputs[0],mix.inputs[1])
    l.new(black.outputs[0],mix.inputs[2])
    l.new(mix.outputs[0],out.inputs["Surface"])


def make_mesh_object(name,verts,faces,mat):
    me=bpy.data.meshes.new(name+"Mesh")
    me.from_pydata(np.asarray(verts).tolist(),[],np.asarray(faces,dtype=np.int32).tolist())
    me.update()
    obj=bpy.data.objects.new(name,me)
    bpy.context.collection.objects.link(obj)
    me.materials.append(mat)
    for poly in me.polygons:
        poly.use_smooth=True
    return obj


def add_motion_shape(obj,start,end):
    if len(start)==0:return
    obj.shape_key_add(name="Shutter start")
    key=obj.shape_key_add(name="Shutter end")
    key.data.foreach_set("co",np.asarray(end,np.float32).ravel())
    key.value=0;key.keyframe_insert(data_path="value",frame=0)
    key.value=1;key.keyframe_insert(data_path="value",frame=2)
    if obj.data.shape_keys and obj.data.shape_keys.animation_data and obj.data.shape_keys.animation_data.action:
        for fc in obj.data.shape_keys.animation_data.action.fcurves:
            for kp in fc.keyframe_points:kp.interpolation="LINEAR"


def ico_template():
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1)
    o=bpy.context.object
    v=np.array([p.co[:] for p in o.data.vertices],np.float32)
    f=np.array([p.vertices[:] for p in o.data.polygons],np.int32)
    bpy.data.objects.remove(o,do_unlink=True)
    return v,f


def droplet_object(name,pos,radii,vel,dt,mat,iv,iff,max_drops=2600):
    if len(pos)==0:return None
    if len(pos)>max_drops:
        ids=np.linspace(0,len(pos)-1,max_drops,dtype=int)
        pos=pos[ids];radii=radii[ids];vel=vel[ids]
    half=.30*dt
    start_centers=pos-vel*half
    end_centers=pos+vel*half
    sv=(start_centers[:,None,:]+iv[None,:,:]*radii[:,None,None]).reshape(-1,3)
    ev=(end_centers[:,None,:]+iv[None,:,:]*radii[:,None,None]).reshape(-1,3)
    faces=(iff[None,:,:]+np.arange(len(pos))[:,None,None]*len(iv)).reshape(-1,3)
    obj=make_mesh_object(name,sv,faces,mat)
    add_motion_shape(obj,sv,ev)
    return obj


def convert_xyz(a):
    a=np.asarray(a,np.float32)
    if len(a)==0:return a.reshape(-1,3)
    return a[:,[0,2,1]]


def main():
    a=args()
    inp=a.input.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((inp/"manifest.json").read_text())
    frame_dt=float(manifest["frameDt"])

    scene=bpy.context.scene
    bpy.ops.object.select_all(action="SELECT");bpy.ops.object.delete(use_global=False)
    scene.render.engine="BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in {i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items} else "CYCLES"
    # Prefer Cycles when available. CPU is deterministic on the hosted runner.
    try: scene.render.engine="CYCLES"
    except Exception: pass
    if scene.render.engine=="CYCLES":
        scene.cycles.device="CPU"
        scene.cycles.samples=a.samples
        scene.cycles.use_denoising=True
        scene.cycles.max_bounces=12
        scene.cycles.transmission_bounces=10
        scene.cycles.glossy_bounces=6
        scene.cycles.diffuse_bounces=2
        scene.cycles.caustics_reflective=False
        scene.cycles.caustics_refractive=False
    scene.render.resolution_x=a.width
    scene.render.resolution_y=a.height
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.render.image_settings.color_mode="RGB"
    try:scene.view_settings.look="AgX - Medium High Contrast"
    except Exception:
        try:scene.view_settings.view_transform="AgX"
        except Exception:pass
    scene.render.film_transparent=False
    scene.render.use_motion_blur=True
    scene.render.motion_blur_shutter=.60
    scene.frame_start=0;scene.frame_end=2

    configure_world()
    water=water_material();stage=stage_material()

    # Wide dark floor, kept low so it does not cut the reconstructed water.
    bpy.ops.mesh.primitive_plane_add(size=8,location=(1.44,1.44,.028))
    floor=bpy.context.object
    floor.data.materials.append(stage)

    target=(1.44,1.44,.52)
    add_area("Long white strip",(-1.5,-1.6,4.2),650,4.8,.62,target)
    add_area("Tall edge card",(4.2,2.2,2.5),860,1.2,3.6,target)
    add_area("Soft blue rim",(-2.8,2.7,3.0),720,3.1,1.9,target,(.76,.90,1.0))
    add_area("Broad front",(2.0,-3.8,2.7),150,4.0,2.6,target,(.84,.94,1.0))

    bpy.ops.object.camera_add(location=(3.85,-5.65,2.75))
    cam=bpy.context.object
    cam.data.lens=52
    cam.data.sensor_width=36
    look_at(cam,target)
    scene.camera=cam

    iv,iff=ico_template()
    t0=time.time()
    active=[]
    for row in manifest["frames"]:
        f=int(row["frame"])
        for obj in active:
            me=obj.data
            bpy.data.objects.remove(obj,do_unlink=True)
            if me and me.users==0:bpy.data.meshes.remove(me)
        active=[]

        d=np.load(inp/f"{f:04d}.npz")
        verts=convert_xyz(d["positions"])
        vel=convert_xyz(d["surface_velocity"])
        faces=np.asarray(d["faces"],np.int32)[:,[0,2,1]]

        half=.30*frame_dt
        start=verts-vel*half
        end=verts+vel*half
        liquid=make_mesh_object("Native CYBR FLIP water",start,faces,water)
        add_motion_shape(liquid,start,end)
        active.append(liquid)

        drops=convert_xyz(d["drops"])
        drop_v=convert_xyz(d["drop_velocity"])
        radii=np.asarray(d["radii"],np.float32)
        droplet=droplet_object("Mass-conserving droplets",drops,radii,drop_v,frame_dt,water,iv,iff)
        if droplet:active.append(droplet)

        scene.frame_set(1)
        scene.render.filepath=str(out/f"{f:04d}.png")
        bpy.ops.render.render(write_still=True)
        print("RENDER",f,"verts",len(verts),"drops",len(drops),"seconds",round(time.time()-t0,1),flush=True)
        d.close()

    print("COMPLETE",flush=True)


if __name__=="__main__":
    main()
