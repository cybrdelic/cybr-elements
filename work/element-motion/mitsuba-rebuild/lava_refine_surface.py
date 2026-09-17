"""CPU material-study geometry derived from the preferred rough baseline.

This is an authored, volume-preserving morphology study, not a new fluid
simulation. Rest coordinates and the original crust structure are retained.
"""
from pathlib import Path
import os, time, json, hashlib
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import numpy as np
from scipy.sparse import coo_matrix, diags
from scipy.ndimage import map_coordinates
from lava_skin import normals

R = Path(__file__).resolve().parent / 'lava-focus'

def smooth(x):
    x = np.clip(x, 0, 1)
    return x*x*(3-2*x)

def noise(p, frequency, seed):
    grid = np.random.default_rng(seed).normal(0, 1, (48, 48, 48))
    return map_coordinates(grid, (p*frequency+19).T, order=3, mode='wrap')

def volume(v, f):
    return float(np.sum(v[f[:, 0]] * np.cross(v[f[:, 1]], v[f[:, 2]]))/6)

def main():
    start = time.time()
    source = R/'iterations/01/surface-0059.npz'
    a = dict(np.load(source))
    v, f = a['v'].astype('f8'), a['f']
    original_volume = volume(v, f)
    original_v = v.copy()
    # Coarse normals only guide the deformation; the new shading normals
    # are recalculated from the resulting detailed geometry.
    edges = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    rows = np.concatenate([edges[:, 0], edges[:, 1]])
    cols = np.concatenate([edges[:, 1], edges[:, 0]])
    adj = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(v), len(v))).tocsr()
    avg = diags(1/np.maximum(np.asarray(adj.sum(1)).ravel(), 1))@adj
    coarse = a['normal'].astype('f8')
    for _ in range(24):
        coarse = .25*coarse+.75*(avg@coarse)
    coarse /= np.maximum(np.linalg.norm(coarse, axis=1)[:, None], 1e-8)
    top = smooth((v[:, 2]+.008)/.09)
    large = noise(original_v, 4.3, 727)
    medium = noise(original_v, 12., 188)
    bulge = np.zeros(len(v))
    for cx, cy, sx, sy, height in [(-.64,.12,.31,.30,.24),(-.05,-.19,.36,.28,.28),(.38,.16,.27,.24,.20)]:
        q = ((v[:, 0]-cx)/sx)**2+((v[:, 1]-cy)/sy)**2
        bulge += height*np.exp(-q*1.1)
    v[:, 2] += top*(bulge+.025*large+.009*medium)
    # Break the perfectly oval margin using the same coherent relief.
    v[:, :2] += coarse[:, :2]*(.035*large)[:, None]
    v[:, 1] *= .81
    # Cluster the existing openings instead of making new glowing lines.
    # Geometric recess depth and exposed temperature use the same field.
    old_open = a['opening'].astype('f8')
    old_tri = original_v[f]
    new_tri = v[f]
    old_area = np.linalg.norm(np.cross(old_tri[:,1]-old_tri[:,0], old_tri[:,2]-old_tri[:,0]),axis=1)
    new_area = np.linalg.norm(np.cross(new_tri[:,1]-new_tri[:,0], new_tri[:,2]-new_tri[:,0]),axis=1)
    ratio = np.clip(new_area/np.maximum(old_area,1e-12),.1,4.)
    strain = np.zeros(len(v)); counts = np.zeros(len(v))
    for corner in range(3):
        np.add.at(strain,f[:,corner],ratio)
        np.add.at(counts,f[:,corner],1)
    strain /= np.maximum(counts,1)
    for _ in range(8):
        strain = .4*strain+.6*(avg@strain)
    opened = np.clip(old_open*(1.08+.36*large+.16*medium+.7*smooth((strain-1.05)/.65)), 0, 1)
    v += coarse*(.017*old_open**1.5-.026*opened**1.5)[:, None]*top[:, None]
    cooled = np.minimum(a['temperature'], 1050.)
    exposed = smooth(opened/.78)
    temperature = cooled+(a['bulk']-cooled)*exposed
    # Keep the old lower surface cool and preserve the amount of lava.
    temperature = a['temperature']*(1-top)+temperature*top
    center = v.mean(0)
    scale = (original_volume/volume(v, f))**(1/3)
    v = center+(v-center)*scale
    a.update(v=v.astype('f4'), normal=normals(v, f).astype('f4'),
             temperature=temperature.astype('f4'), opening=opened.astype('f4'))
    output = R/'refined-lobed-02.npz'
    np.savez_compressed(output, **a)
    assert np.isfinite(v).all() and np.isfinite(temperature).all()
    report = {'source':str(source), 'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'output':str(output), 'vertices':len(v), 'triangles':len(f),
              'volumeRelativeError':abs(volume(v,f)/original_volume-1),
              'bounds':np.array([v.min(0),v.max(0)]).tolist(),
              'temperatureK':np.quantile(temperature,[0,.1,.5,.9,1]).tolist(),
              'seconds':round(time.time()-start,2), 'device':'CPU',
              'limitation':'Authored morphology and crust exposure; not a resolved crust-fracture simulation'}
    output.with_suffix('.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))

if __name__ == '__main__':
    main()
