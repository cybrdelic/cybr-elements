"""Finite-capacity three-dimensional rock substrate, CPU Fourier conduction."""
import numpy as np
import json
from scipy.sparse import coo_matrix,diags
from scipy.sparse.linalg import cg


class Bed:
    def __init__(self,origin=(-.10,-.08,-.06),shape=(28,16,6),dx=.01):
        self.origin=np.array(origin);self.shape=tuple(shape);self.dx=dx
        self.density=2800.;self.cp=850.;self.conductivity=2.;self.ambient=293.15
        self.temperature=np.full(shape,self.ambient);self.pending=np.zeros(shape)
        self.capacity=self.density*self.cp*dx**3
        self.received=0.;self.bottom_loss=0.;self.time=0.;self.rows=[]
        index=np.arange(np.prod(shape)).reshape(shape);rr=[];cc=[];vv=[];diag=np.zeros(shape)
        for axis in range(3):
            a=[slice(None)]*3;b=a.copy();a[axis]=slice(None,-1);b[axis]=slice(1,None)
            i=index[tuple(a)].ravel();j=index[tuple(b)].ravel();g=np.full(len(i),self.conductivity*dx)
            rr.extend([i,j]);cc.extend([j,i]);vv.extend([-g,-g]);diag[tuple(a)]+=self.conductivity*dx;diag[tuple(b)]+=self.conductivity*dx
        self.bottom=np.zeros(shape);self.bottom[:,:,0]=2*self.conductivity*dx
        diag+=self.bottom
        rr.append(index.ravel());cc.append(index.ravel());vv.append(diag.ravel())
        self.K=coo_matrix((np.concatenate(vv),(np.concatenate(rr),np.concatenate(cc))),shape=(index.size,)*2).tocsr()

    def weights(self,xyz):
        q=(xyz[:,:2]-self.origin[:2])/self.dx-.5;b=np.floor(q).astype(int);f=q-b
        result=[]
        for i in (0,1):
            for j in (0,1):
                ij=np.clip(b+[i,j],0,np.array(self.shape[:2])-1)
                w=(f[:,0] if i else 1-f[:,0])*(f[:,1] if j else 1-f[:,1])
                result.append((ij,w))
        return result

    def temperature_at(self,xyz):
        t=np.zeros(len(xyz))
        for ij,w in self.weights(xyz):t+=self.temperature[ij[:,0],ij[:,1],-1]*w
        return t

    def conductance(self,material_dx,material_k):
        return 1/(material_dx/(2*material_k)+self.dx/(2*self.conductivity))

    def add_heat(self,xyz,joules):
        for ij,w in self.weights(xyz):np.add.at(self.pending,(ij[:,0],ij[:,1],np.full(len(ij),self.shape[2]-1)),w*joules)
        self.received+=float(joules.sum())

    def advance(self,dt):
        A=diags(np.full(self.K.shape[0],self.capacity))+dt*self.K
        rhs=(self.capacity*self.temperature+self.pending+dt*self.bottom*self.ambient).ravel()
        t,info=cg(A,rhs,x0=self.temperature.ravel(),M=diags(1/A.diagonal()),rtol=1e-12,atol=1e-11,maxiter=80)
        if info:raise RuntimeError(('Bed heat solve failed',info))
        self.temperature=t.reshape(self.shape);self.pending[:]=0
        self.bottom_loss+=float(np.sum(dt*self.bottom*(self.temperature-self.ambient)))
        self.time+=dt;stored=float(np.sum(self.capacity*(self.temperature-self.ambient)))
        error=abs(stored+self.bottom_loss-self.received)
        row=dict(time=self.time,storedHeatJ=stored,receivedHeatJ=self.received,bottomLossJ=self.bottom_loss,energyErrorJ=error,maximumTemperature=float(self.temperature.max()))
        if error>1e-6*max(abs(self.received),1):raise RuntimeError(('Bed energy balance failed',row))
        self.rows.append(row);return row

    def save(self,path):
        np.savez_compressed(path,temperature=self.temperature,origin=self.origin,dx=self.dx,time=self.time,meta=json.dumps(dict(received=self.received,bottom_loss=self.bottom_loss,rows=self.rows)))

    @classmethod
    def load(cls,path):
        s=np.load(path);obj=cls(origin=s['origin'],shape=s['temperature'].shape,dx=float(s['dx']));obj.temperature=s['temperature'].copy();obj.time=float(s['time']);meta=json.loads(str(s['meta']))
        for k in ('received','bottom_loss','rows'):setattr(obj,k,meta[k])
        return obj
