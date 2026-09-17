"""Integrate Planck radiance through Mitsuba's CIE color matching functions.

Opaque lava needs no wavelength-dependent refraction. Integrating the source
spectrum before RGB path tracing removes wavelength Monte Carlo noise while
preserving its physically derived temperature/color/radiance relationship.
"""
import numpy as np,mitsuba as mi
WAVELENGTH=np.arange(360.,831.);CIE=np.array([np.array(mi.cie1931_xyz(float(w))) for w in WAVELENGTH]);XYZ_TO_RGB=np.array([[3.240479,-1.537150,-.498535],[-.969256,1.875991,.041556],[.055648,-.204043,1.057311]])
def radiance(temperature):
 wave=WAVELENGTH*1e-9;power=2*6.62607015e-34*299792458.**2/(wave**5*np.expm1(6.62607015e-34*299792458./(wave*1.380649e-23*temperature)))*1e-9;xyz=np.trapezoid(power[:,None]*CIE,WAVELENGTH,axis=0)/106.856895;return np.maximum(0,XYZ_TO_RGB@xyz).tolist()
