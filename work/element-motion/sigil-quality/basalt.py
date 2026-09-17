"""Photographic basalt relief and a closed crust over an incandescent interior."""
import numpy as np
import bpy

def build(v,faces,normal,born,T,mesh,scene):
    hot=scene.material('Molten basalt interior',(.008,.003,.001),.34)
    n=hot.node_tree.nodes;l=hot.node_tree.links;p=n.get('Principled BSDF');bb=n.new('ShaderNodeBlackbody');bb.inputs[0].default_value=1500;l.new(bb.outputs[0],p.inputs['Emission Color']);p.inputs['Emission Strength'].default_value=.38
    mesh('Incandescent basalt interior',v,faces,hot)
    mat=scene.material('Scanned cooled basalt skin',(.008,.009,.010),.66,ior=1.49)
    n=mat.node_tree.nodes;l=mat.node_tree.links;p=n.get('Principled BSDF');position=n.new('ShaderNodeNewGeometry');sep=n.new('ShaderNodeSeparateXYZ');join=n.new('ShaderNodeCombineXYZ');l.new(position.outputs['Position'],sep.inputs[0]);l.new(sep.outputs['X'],join.inputs['X']);l.new(sep.outputs['Z'],join.inputs['Y']);coord=n.new('ShaderNodeVectorMath');coord.operation='SCALE';coord.inputs['Scale'].default_value=.63;l.new(join.outputs[0],coord.inputs[0])
    coord.operation='MULTIPLY';coord.inputs[1].default_value=(.105,.25,1)
    shifted=n.new('ShaderNodeVectorMath');shifted.operation='ADD';shifted.inputs[1].default_value=(.51,.03,0);l.new(coord.outputs[0],shifted.inputs[0])
    textures={}
    for label,suffix in [('height','disp'),('rough','rough'),('color','diff')]:
        im=bpy.data.images.load(str(scene.ASSETS/f'rock_boulder_cracked_{suffix}_2k.jpg'));im.colorspace_settings.name='sRGB' if label=='color' else 'Non-Color';tex=n.new('ShaderNodeTexImage');tex.image=im;l.new(shifted.outputs[0],tex.inputs['Vector']);textures[label]=tex
    grey=n.new('ShaderNodeRGBToBW');l.new(textures['color'].outputs[0],grey.inputs[0]);tone=n.new('ShaderNodeMath');tone.operation='MULTIPLY';tone.inputs[1].default_value=.055;l.new(grey.outputs[0],tone.inputs[0]);l.new(tone.outputs[0],p.inputs['Base Color'])
    rough=n.new('ShaderNodeMapRange');rough.inputs['To Min'].default_value=.43;rough.inputs['To Max'].default_value=.83;l.new(textures['rough'].outputs[0],rough.inputs[0]);l.new(rough.outputs[0],p.inputs['Roughness'])
    bump=n.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.012;bump.inputs['Strength'].default_value=.7;l.new(textures['height'].outputs[0],bump.inputs['Height']);l.new(bump.outputs[0],p.inputs['Normal'])
    # The same scan drives relief and shell openings; no procedural cell pattern.
    im=textures['height'].image;width,height=im.size[:];raw=np.empty(width*height*4,'f4');im.pixels.foreach_get(raw);heightmap=raw.reshape(height,width,4)[:,:,0]
    uv=v[:,[0,2]]*np.array([.105,.25])+np.array([.51,.03]);xx=(uv[:,0]%1)*(width-1);zz=(uv[:,1]%1)*(height-1);x0=xx.astype(int);z0=zz.astype(int);xf=xx-x0;zf=zz-z0
    h=heightmap[z0,x0]*(1-xf)*(1-zf)+heightmap[z0,np.minimum(x0+1,width-1)]*xf*(1-zf)+heightmap[np.minimum(z0+1,height-1),x0]*(1-xf)*zf+heightmap[np.minimum(z0+1,height-1),np.minimum(x0+1,width-1)]*xf*zf
    threshold=np.quantile(h[normal[:,1]<-.4],.055)
    usable=(normal[:,1]<.45)&(h>threshold)
    skin=faces[usable[faces].all(1)]
    age=np.maximum(0,T-born);thickness=.002+np.minimum(.01,2*np.sqrt(5e-6*age));raised=v+normal*(thickness+.024*(h-.35))[:,None]
    ids,inverse=np.unique(skin,return_inverse=True);skin=inverse.reshape(-1,3);vertices=raised[ids]
    edges=np.concatenate([skin[:,[0,1]],skin[:,[1,2]],skin[:,[2,0]]]);_,index,count=np.unique(np.sort(edges,axis=1),axis=0,return_index=True,return_counts=True);edge=edges[index[count==1]]
    base=len(vertices);vertices=np.r_[vertices,v[ids]];walls=np.r_[np.c_[edge[:,0],edge[:,1],edge[:,1]+base],np.c_[edge[:,0],edge[:,1]+base,edge[:,0]+base]]
    mesh('Closed scanned crust geometry',vertices,np.r_[skin,walls],mat)
