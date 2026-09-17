"""Compare sparse contact to the independent dense dual solution."""
import json,numpy as np,time
from scipy.sparse import csr_matrix,diags
from lava_mpm_fracture import implicit_contact
from lava_mpm_contact_admm import contact
from lava_mpm import ROOT

def main():
    rng=np.random.default_rng(502);rows=[]
    for condition in (1,100,10000):
        n=24;G=rng.normal(size=(n,n));A=csr_matrix(G.T@G*condition+np.eye(n));rhs=rng.normal(size=n);S=diags(np.ones(n))
        C=csr_matrix(rng.normal(size=(18,n)));offset=rng.normal(size=18)*.002;epsilon=1e-5
        exact=implicit_contact(A,rhs,S,C,epsilon,offset);start=time.time();sparse=contact(A,rhs,S,C,epsilon,offset)
        error=float(np.max(abs(exact[0]-sparse[0])));relative=error/max(np.max(abs(exact[0])),1e-12)
        assert relative<3e-4,(condition,error,relative)
        rows.append(dict(condition=condition,absoluteVelocityError=error,relativeVelocityError=relative,iterations=sparse[-1],seconds=time.time()-start))
    result=dict(status='pass',comparisons=rows,limits='Algebraic contact equivalence; not lava grid convergence.')
    (ROOT/'validation'/'sparse_contact.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':main()
