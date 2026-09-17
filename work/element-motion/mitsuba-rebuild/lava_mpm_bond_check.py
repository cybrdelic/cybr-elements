"""A bonded substrate must not remotely pin a hovering body."""
import json,numpy as np
from lava_mpm import MPM,ROOT,block

def main():
    errors=[]
    for gap in (.01,0.):
        s=MPM(block([-.01,-.01,gap],[.01,.01,gap+.02],.005),.005,.01,temperature=900.,bonded_bed=True)
        s.v[:,0]=.01;initial=s.x.copy();row=s.step(.02,thermal=False)
        if gap:
            expected=np.array([.01,0,-9.81*.02]);error=float(np.linalg.norm(s.v-expected,axis=1).max());assert error<1e-5
        else:
            basal=s.rest[:,2]<.003;error=float(np.linalg.norm(s.x[basal]-initial[basal],axis=1).max());assert error<1e-5
        errors.append(error)
    result=dict(status='pass',hoveringVelocityError=errors[0],bondedBaseDisplacementM=errors[1],limits='Tests the selected ideal bonded boundary, not an adhesion or friction law for arbitrary terrain.')
    (ROOT/'validation'/'bonded_substrate.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':main()
