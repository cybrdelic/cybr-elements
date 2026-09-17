"""Metered hot-bed boundary, with no device or command-line side effects."""
import numpy as np


class HotBed:
    """Declared hot rock reservoir below the flow, with metered heat exchange."""
    def __init__(self,temperature=1173.15):self.temperature=temperature;self.received=0.
    def temperature_at(self,xyz):return np.full(len(xyz),self.temperature)
    def conductance(self,dx,k):return k/(dx*.5)
    def add_heat(self,xyz,heat):self.received+=float(np.sum(heat))
