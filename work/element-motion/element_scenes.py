"""Composition registry: domain dynamics + optics + original motion, not engines."""
from dataclasses import dataclass
from pathlib import Path
import fire_dynamics, air_dynamics, dust_dynamics, element_choreography
import element_optics as optics
ROOT=Path(__file__).resolve().parent
@dataclass(frozen=True)
class SceneSpec:
    name: str
    motion: str
    source_reaction: object
    turn: object
    radiance: object
    pixels: object
    capture: object
    video: Path
    frames: Path
    pilot: int=0
    crf: int=17
    reservoir: bool=False
    bounds: tuple|None=None
    source_asset: str|None=None
    sheet_depth: tuple=(0.,0.)
    default_seconds: float=4.
    default_native_frames: int=0
    tracer_density: float=.55
    tracer_decay: float=1.35
    review_gate: int|None=None
    continue_path: Path|None=None
SCENES={
    'fire-v3': SceneSpec('fire-v3', 'motion', fire_dynamics.source_fire_v3, element_choreography.turn_fire_v3, optics.radiance_fire_v3, optics.pixels_fire_v3, optics.capture_fire_v3, ROOT.parent.parent/'outputs/cybrdelic-type/elements/motion/fire-v3-test.mp4', ROOT/'fire-v3-frames', 0, 17, False),
    'air-v2': SceneSpec('air-v2', 'motion', air_dynamics.source_air_v2, element_choreography.turn_air_v2, optics.radiance_fire_v3, optics.pixels_air_v2, optics.capture_fire_v3, ROOT.parent.parent/'outputs/cybrdelic-type/elements/motion/air-v2-test.mp4', ROOT/'air-v2-frames', 0, 17, False),
    'air-v3': SceneSpec('air-v3', 'motion', air_dynamics.source_air_v3, element_choreography.turn_air_v3, optics.radiance_fire_v3, optics.pixels_air_v2, optics.capture_fire_v3, ROOT.parent.parent/'outputs/cybrdelic-type/elements/motion/air-v3-test.mp4', ROOT/'air-v3-frames', 0, 17, False),
    'bending-fire-v5': SceneSpec('bending-fire-v5', 'shared_motion', fire_dynamics.source_bending_fire_v5, element_choreography.turn_fire_v3, optics.radiance_bending_fire_v5, optics.pixels_bending_fire_v5, optics.capture_fire_v3, ROOT/'bending-rebuild-v5/fire-v5.mp4', ROOT/'bending-rebuild-v5/fire-frames', 46, 15, False),
    'fire-material-v2': SceneSpec('fire-material-v2', 'shared_motion', fire_dynamics.source_fire_v3, element_choreography.turn_fire_v3, optics.radiance_fire_material_v2, optics.pixels_bending_fire_v5, optics.capture_fire_v3, ROOT.parent.parent/'outputs/cybrdelic-type/elements/motion/fire-material-v2.mp4', ROOT/'fire-material-v2-frames', 0, 17, False),
    'earth-dust': SceneSpec('earth-dust', 'shared_motion', dust_dynamics.source_earth_dust, element_choreography.turn_fire_v3, optics.radiance_fire_v3, optics.pixels_earth_dust, optics.capture_earth_dust, ROOT.parent.parent/'outputs/cybrdelic-type/elements/motion/earth-dust.mp4', ROOT/'earth-dust-frames', 0, 17, False),
    'fire-v2': SceneSpec('fire-v2', 'motion', fire_dynamics.source_fire_v2, element_choreography.turn_air_v2, optics.radiance_fire_v3, optics.pixels_fire_v3, optics.capture_fire_v3, ROOT.parent.parent/'outputs/cybrdelic-type/elements/motion/fire-v2-test.mp4', ROOT/'fire-v2-frames', 0, 17, False),
    'air-material': SceneSpec('air-material', 'shared_motion', air_dynamics.source_air_material, element_choreography.turn_fire_v3, optics.radiance_fire_v3, optics.pixels_air_material, optics.capture_air_material, ROOT.parent.parent/'outputs/cybrdelic-type/elements/motion/air-material.mp4', ROOT/'air-material-frames', 0, 17, False),
    'sigil_native_fire_fed': SceneSpec('sigil_native_fire_fed', 'sigil_native_motion', fire_dynamics.source_sigil_native_fire_fed, element_choreography.turn_fire_v3, optics.radiance_sigil_native_fire_fed, optics.pixels_bending_fire_v5, optics.capture_fire_v3, ROOT/'sigil-native/fire-c-fed.mp4', ROOT/'sigil-native/fire-c-fed', 120, 17, True),
    'fire-sheets': SceneSpec('fire-sheets', 'shared_motion', fire_dynamics.source_bending_fire_v5, element_choreography.turn_fire_v3, optics.radiance_sigil_native_fire_fed, optics.pixels_bending_fire_v5, optics.capture_fire_v3, ROOT.parent.parent/'outputs/cybrdelic-type/elements/motion/fire-sheets.mp4', ROOT/'fire-sheets-frames', 0, 17, False),
    'fire-shared': SceneSpec('fire-shared', 'shared_motion', fire_dynamics.source_fire_v3, element_choreography.turn_fire_v3, optics.radiance_fire_v3, optics.pixels_fire_v3, optics.capture_fire_v3, ROOT.parent.parent/'outputs/cybrdelic-type/elements/motion/fire-shared.mp4', ROOT/'fire-shared-frames', 0, 17, False),
    'bending-air': SceneSpec('bending-air', 'shared_motion', air_dynamics.source_bending_air, element_choreography.turn_fire_v3, optics.radiance_fire_v3, optics.pixels_bending_air, optics.capture_air_material, ROOT.parent.parent/'outputs/cybrdelic-type/elements/motion/bending/air.mp4', ROOT/'bending-rebuild/air-frames', 46, 17, False),
    'air-shared': SceneSpec('air-shared', 'shared_motion', air_dynamics.source_air_material, element_choreography.turn_fire_v3, optics.radiance_fire_v3, optics.pixels_air_v2, optics.capture_air_material, ROOT.parent.parent/'outputs/cybrdelic-type/elements/motion/air-shared.mp4', ROOT/'air-shared-frames', 0, 17, False),
    'air-material-v2': SceneSpec('air-material-v2', 'shared_motion', air_dynamics.source_air_material, element_choreography.turn_fire_v3, optics.radiance_fire_v3, optics.pixels_air_material_v2, optics.capture_air_material, ROOT.parent.parent/'outputs/cybrdelic-type/elements/motion/air-material-v2.mp4', ROOT/'air-material-v2-frames', 0, 17, False),
    'fire-material': SceneSpec('fire-material', 'shared_motion', fire_dynamics.source_fire_v3, element_choreography.turn_fire_v3, optics.radiance_fire_material, optics.pixels_bending_fire_v5, optics.capture_fire_v3, ROOT.parent.parent/'outputs/cybrdelic-type/elements/motion/fire-material.mp4', ROOT/'fire-material-frames', 0, 17, False),
    'sigil_02_fire_v2': SceneSpec('sigil_02_fire_v2',None,fire_dynamics.source_style02,None,optics.radiance_style02,optics.pixels_style02_fire,optics.capture_fire_v3,ROOT/'sigil-02-v2/fire-02.mp4',ROOT/'sigil-02-v2/fire-frames',bounds=((-7.,-.6,-1.05),(14.,1.2,7.875)),source_asset='sigil-02-v2/source.npz',sheet_depth=(.028,.026),default_native_frames=294,review_gate=135,continue_path=ROOT/'sigil-02-v2/continue'),
    'sigil_02_air_v2': SceneSpec('sigil_02_air_v2',None,air_dynamics.source_style02,None,optics.radiance_style02,optics.pixels_style02_air,optics.capture_fire_v3,ROOT/'sigil-02-elements/air-02-v2.mp4',ROOT/'sigil-02-elements/air-frames-v2',bounds=((-7.,-.6,-1.05),(14.,1.2,7.875)),source_asset='sigil-02-v2/source.npz',sheet_depth=(.050,.040),default_native_frames=294,review_gate=135,continue_path=ROOT/'sigil-02-elements/continue-air-v2'),
    'sigil_02_air': SceneSpec('sigil_02_air',None,air_dynamics.source_style02,None,optics.radiance_style02,optics.pixels_style02_air,optics.capture_fire_v3,ROOT/'sigil-02-elements/air-02.mp4',ROOT/'sigil-02-elements/air-frames',bounds=((-7.,-.6,-1.05),(14.,1.2,7.875)),source_asset='sigil-02-v2/source.npz',sheet_depth=(.050,.040),default_native_frames=294,tracer_density=.85,tracer_decay=.65,review_gate=135,continue_path=ROOT/'sigil-02-elements/continue-air'),
}
