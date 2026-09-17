"""Use the existing OIDN CPU library, with every GPU backend disabled."""
import os,ctypes as c
import numpy as np
from pathlib import Path
for key in ['OIDN_DEVICE_SYCL','OIDN_DEVICE_CUDA','OIDN_DEVICE_HIP','OIDN_DEVICE_METAL']:os.environ[key]='0'
os.environ['OIDN_DEVICE_CPU']='1';os.environ['OIDN_DEFAULT_DEVICE']='cpu';os.environ['OIDN_NUM_THREADS']='2';os.environ['OIDN_SET_AFFINITY']='0'

def denoise(color,albedo=None,normal=None):
 root=Path('C:/Program Files/Blender Foundation/Blender 4.5/blender.shared');directory=os.add_dll_directory(str(root));cpu_backend=c.CDLL(str(root/'OpenImageDenoise_device_cpu.dll'));lib=c.CDLL(str(root/'OpenImageDenoise.dll'));P=c.c_void_p;S=c.c_char_p;Z=c.c_size_t
 signatures={'oidnNewDevice':([c.c_int],P),'oidnSetDeviceInt':([P,S,c.c_int],None),'oidnCommitDevice':([P],None),'oidnNewFilter':([P,S],P),'oidnSetSharedFilterImage':([P,S,P,c.c_int,Z,Z,Z,Z,Z],None),'oidnSetFilterBool':([P,S,c.c_bool],None),'oidnCommitFilter':([P],None),'oidnExecuteFilter':([P],None),'oidnGetDeviceError':([P,c.POINTER(S)],c.c_int),'oidnReleaseFilter':([P],None),'oidnReleaseDevice':([P],None)}
 for name,(args,ret) in signatures.items():fn=getattr(lib,name);fn.argtypes=args;fn.restype=ret
 device=lib.oidnNewDevice(1) # OIDN_DEVICE_TYPE_CPU; never DEFAULT.
 if not device:raise RuntimeError('OIDN CPU device creation failed')
 lib.oidnSetDeviceInt(device,b'numThreads',2);lib.oidnCommitDevice(device);f=lib.oidnNewFilter(device,b'RT');color=np.ascontiguousarray(np.maximum(color,0),dtype='f4');output=np.empty_like(color);arrays={'color':color,'output':output}
 if albedo is not None:arrays['albedo']=np.ascontiguousarray(albedo,dtype='f4')
 if normal is not None:arrays['normal']=np.ascontiguousarray(normal,dtype='f4')
 try:
  for name,a in arrays.items():lib.oidnSetSharedFilterImage(f,name.encode(),P(a.ctypes.data),3,a.shape[1],a.shape[0],0,0,0)
  lib.oidnSetFilterBool(f,b'hdr',True);lib.oidnSetFilterBool(f,b'cleanAux',False);lib.oidnCommitFilter(f);lib.oidnExecuteFilter(f);message=S();error=lib.oidnGetDeviceError(device,c.byref(message))
  if error:raise RuntimeError(message.value.decode() if message.value else f'OIDN error {error}')
 finally:lib.oidnReleaseFilter(f);lib.oidnReleaseDevice(device);directory.close()
 assert np.isfinite(output).all();return output
