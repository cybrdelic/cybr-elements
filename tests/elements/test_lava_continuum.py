from dataclasses import replace
from pathlib import Path
import math
import numpy as np
import pytest

from elements_core.lava_mpm import (
    LavaConfig, LavaMPM, enthalpy_from_temperature, temperature_from_enthalpy,
    particle_to_grid,
)
from elements_core.lava_surface import reconstruct, mesh_volume, wall_contact_heights, _constrain_vertices_to_mold
from elements_core.lava_material import material_controls, planck_rgb
from elements_core.lava_formation import PourFormationConfig, build_pour_initial_state, build_pour_source_schedule, _mold_contact, _mold_heat_transfer
from elements_core.lava_shallow import ShallowLavaConfig, initialize as initialize_shallow, advance_state as advance_shallow, metrics as shallow_metrics, _redistribute_overflow


def block(config=None, temperature=1500.0):
    c = config or LavaConfig(
        spacing=.025, shape=(40, 40, 40), origin=(-.5, -.5, 0),
        floor=.05, gravity=0, emissivity=0, convection=0,
        conductivity=0, max_dt=.0003,
    )
    a = np.arange(-.05, .0501, .0125)
    x = np.array(np.meshgrid(a, a, a + .38, indexing='ij')).reshape(3, -1).T
    H = enthalpy_from_temperature(np.full(len(x), temperature), c)
    return LavaMPM(c, x, H, np.full(len(x), .0125**3))


@pytest.mark.parametrize('temperature', [293.15, 800., 1249.9, 1250., 1350., 1450., 1500., 2200.])
def test_enthalpy_inverse(temperature):
    c = LavaConfig()
    assert temperature_from_enthalpy(enthalpy_from_temperature(temperature, c), c) == pytest.approx(temperature, abs=1e-10)


def test_uniform_translation_preserves_mass_momentum_volume_and_heat():
    s = block(); v = np.array([.21, -.13, .04]); s.v[:] = v
    x0 = s.x.copy(); energy = s.initial_energy
    s.advance(.003)
    np.testing.assert_allclose(s.v, np.broadcast_to(v, s.v.shape), atol=3e-10)
    np.testing.assert_allclose(s.x, x0 + v * .003, atol=1e-11)
    np.testing.assert_allclose(s.J, 1, atol=1e-10)
    np.testing.assert_allclose(s.mass @ s.v, s.mass.sum() * v, atol=1e-10)
    assert s.mass @ s.H == pytest.approx(energy, rel=1e-12)
    assert s.metrics()['massDifferenceKg'] == pytest.approx(0, abs=1e-12)


def test_maxwell_relaxation_matches_analytical_decay():
    s = block(); initial = np.array([[100., 20., 0], [20., -50., 0], [0, 0, -50.]])
    s.S[:] = initial; dt = .0002
    particle_to_grid(s.x, s.v, s.C, s.J, s.H, s.S, s.damage, s.mass, s.V0, s.origin, s.params,
                     dt, s.gm, s.gv, s.gH, s._visc)
    expected = initial * math.exp(-dt * s.config.shear_modulus * .1 / s.config.melt_viscosity)
    np.testing.assert_allclose(s.S, np.broadcast_to(expected, s.S.shape), rtol=1e-12, atol=1e-12)
    assert s._visc[0] > 0


def test_surface_reconstruction_carries_material_state_and_closes_volume():
    s = block(); mesh, report = reconstruct(s.snapshot(), spacing=.0125, world_origin=(-.5, -.5, 0), floor=.05)
    assert report['finalVolumeRelativeError'] < 3e-4
    assert report['minimumFloorClearanceMeters'] >= 0
    np.testing.assert_allclose(mesh['temperature'], 1500., atol=.002)
    assert mesh['damage'].shape == mesh['temperature'].shape
    assert mesh['rest'].shape == mesh['vertices'].shape
    assert abs(mesh_volume(mesh['vertices'].astype(np.float64), mesh['faces']) - s.V0.sum()) / s.V0.sum() < 3e-4


def test_surface_integer_lattice_translation_is_covariant():
    s = block(); a = s.snapshot(); b = {k: v.copy() if hasattr(v, 'copy') else v for k, v in a.items()}
    shift = np.array([.025, 0, 0]); b['positions'] = a['positions'] + shift; b['rest'] = a['rest'] + shift
    m0, _ = reconstruct(a, spacing=.0125, world_origin=(-.5, -.5, 0), floor=.05)
    m1, _ = reconstruct(b, spacing=.0125, world_origin=(-.5, -.5, 0), floor=.05)
    np.testing.assert_array_equal(m0['faces'], m1['faces'])
    np.testing.assert_allclose(m1['vertices'], m0['vertices'] + shift, atol=1e-7)


def test_wall_conformance_monotone_and_identity_outside_support():
    cell = .016; h = np.linspace(0, .060, 10001); mapped = wall_contact_heights(h, cell)
    assert np.all(mapped >= 0) and np.all(np.diff(mapped) >= -1e-14)
    np.testing.assert_allclose(mapped[h >= 2 * cell], h[h >= 2 * cell], atol=1e-14)
    assert np.all(mapped[h <= .75 * cell] == 0)


def test_material_phase_controls_are_monotone_without_hot_mask():
    temperature = np.array([1050., 1250., 1350., 1450., 1550.]); damage = np.full(5, .9)
    c = material_controls(temperature, damage)
    assert np.all(np.diff(c['crust']) <= 0)
    assert c['crust'][0] == pytest.approx(1.) and c['crust'][-1] == pytest.approx(0.)
    assert c['fracture'][0] > c['fracture'][2] > c['fracture'][-1]
    assert c['fracture'][-1] == pytest.approx(0.)
    assert c['coat'][-1] > 0
    assert c['obsidian'][0] > .8
    assert np.all(c['obsidian'][1:] == 0.)


def test_obsidian_is_glossier_than_fresh_transition_crust():
    c = material_controls(np.array([1040., 1250., 1530.]), np.array([.2,.2,.2]))
    assert c['obsidian'][0] > .9
    assert c['transitionalCrust'][1] > .99
    assert c['roughness'][0] < c['roughness'][1]
    assert c['coat'][0] > c['coat'][1]
    assert c['roughness'][2] < c['roughness'][1]

def test_damage_changes_crust_relief_not_thermal_radiance():
    temperature = np.full(5, 1325.)
    low = material_controls(temperature, np.zeros(5)); high = material_controls(temperature, np.ones(5))
    np.testing.assert_array_equal(low['thermalRadiance'], high['thermalRadiance'])
    np.testing.assert_array_equal(low['thermalColor'], high['thermalColor'])
    np.testing.assert_array_equal(low['thermalStrength'], high['thermalStrength'])
    assert np.all(high['fracture'] > low['fracture'])
    assert np.all(high['roughness'] >= low['roughness'])
    assert np.all(high['baseColor'] <= low['baseColor'] + 1e-15)


def test_planck_rgb_positive_monotone_and_red_dominant_at_lava_temperature():
    rgb = planck_rgb(np.array([900., 1100., 1300., 1500., 1800.]))
    assert np.isfinite(rgb).all() and np.all(rgb > 0)
    assert np.all(np.diff(rgb, axis=0) > 0)
    assert np.all(rgb[:, 0] > rgb[:, 1]) and np.all(rgb[:, 1] > rgb[:, 2])
    c = material_controls(np.array([900., 1100., 1300., 1500., 1800.]), np.zeros(5))
    assert np.allclose(np.max(c['thermalColor'], axis=1), 1.)
    assert np.all(np.diff(c['thermalStrength']) > 0)
    assert np.all(c['thermalColor'][:, 0] > c['thermalColor'][:, 1])


def test_material_controls_reject_invalid_state():
    with pytest.raises(ValueError): material_controls(np.array([1200.]), np.array([0., 1.]))
    with pytest.raises(ValueError): material_controls(np.array([np.nan]), np.array([0.]))
    with pytest.raises(ValueError): material_controls(np.array([1200.]), np.array([0.]), solidus=1450, liquidus=1250)
    with pytest.raises(ValueError): planck_rgb(np.array([0.]))


def test_mold_sidewall_friction_is_impulse_based_not_per_step_drag():
    sdf=np.full((2,2),.005,np.float64)
    gx=np.ones((2,2),np.float64);gz=np.zeros((2,2),np.float64)
    lo=np.zeros(3,np.float64);extent=np.ones(3,np.float64)

    # Perfectly wall-parallel motion has no normal impulse and must not be
    # exponentially damped merely because the particle sits in the contact band.
    x=np.array([[.5,.5,.05]],np.float64)
    v=np.array([[0.,1.,0.]],np.float64)
    count,_=_mold_contact(x,v,sdf,gx,gz,lo,extent,1.,0.,.1,.01,.46)
    assert count==1
    np.testing.assert_allclose(v[0],[0.,1.,0.],atol=1e-12)

    # Inward motion removes its normal component and applies Coulomb friction
    # proportional to that removed normal speed.
    x=np.array([[.5,.5,.05]],np.float64)
    v=np.array([[-.2,1.,0.]],np.float64)
    _mold_contact(x,v,sdf,gx,gz,lo,extent,1.,0.,.1,.01,.46)
    assert v[0,0]==pytest.approx(0.,abs=1e-12)
    assert v[0,1]==pytest.approx(1.-.46*.2,abs=1e-12)


def test_mold_conduction_removes_energy_and_preserves_accounting():
    c=LavaConfig(spacing=.025,shape=(40,40,40),origin=(-.5,-.5,0.),
                 floor=.05,gravity=0,emissivity=0,convection=0,conductivity=0,max_dt=.0003)
    s=block(c,temperature=1550.)
    s.x[:,2]=c.floor+.002
    H0=s.H.copy()
    sdf=np.full((4,4),1.,np.float64)
    lo=np.array([-1.,0.,-1.],np.float64);extent=np.array([2.,1.,2.],np.float64)
    q,contacts=_mold_heat_transfer(
        s.x,s.J,s.H,s.mass,sdf,lo,extent,1.,0.,.2,.002,c.floor,.01,2600.,450.,s.params,.01)
    assert contacts==len(s.x)
    assert q>0
    assert np.all(s.H<H0)
    assert q==pytest.approx(float(s.mass@(H0-s.H)),rel=1e-12)
    s.mold_conduction_loss+=q
    assert s.metrics()['thermalBalanceRelative']==pytest.approx(0,abs=1e-12)


def test_surface_mold_constraint_pushes_subwall_vertices_into_cavity():
    sdf=np.tile(np.linspace(-.05,.05,9),(9,1))
    gx=np.ones_like(sdf);gy=np.zeros_like(sdf)
    mold={'sdf':sdf,'gx':gx,'gz':gy,'lo':np.array([-1.,0.,-1.]),
          'extent':np.array([2.,1.,2.]),'stageScale':1.,'sourceCenterZ':0.,
          'wallTop':.12,'margin':.002}
    v=np.array([[-.04,0.,.08],[.04,0.,.08],[.04,0.,.2]],np.float64)
    out=_constrain_vertices_to_mold(v,mold,.01)
    assert out[0,0]>v[0,0]
    np.testing.assert_allclose(out[1:],v[1:],atol=1e-12)


def test_open_boundary_injection_updates_mass_and_energy_reference():
    s = block()
    n0=len(s.x);energy0=s.initial_energy
    take=np.arange(8)
    positions=s.x[take]+np.array([.18,0.,.02])
    velocities=np.tile(np.array([.03,-.01,-.2]),(len(take),1))
    added=s.inject(positions,s.H[take],s.V0[take],velocities,positions*1.07)
    assert added==len(take)
    assert len(s.x)==n0+len(take)
    assert s.initial_count==len(s.x)
    assert s.initial_energy>energy0
    m=s.metrics()
    assert m['sourceInjectedParticles']==len(take)
    assert m['sourceInjectedMassKg']>0
    assert m['sourceInjectedEnergyJ']>0
    assert m['massDifferenceKg']==pytest.approx(0,abs=1e-12)
    assert m['thermalBalanceRelative']==pytest.approx(0,abs=1e-12)


def test_pour_source_schedule_is_timed_at_the_nozzle_plane():
    source = Path('work/element-motion/sigil-02-v2/source.npz')
    assert source.is_file()
    c = LavaConfig(spacing=.018, shape=(96,68,82), origin=(-.864,-.612,0.),
                   max_dt=.0007, support_start=-1., support_end=-.5)
    formation = PourFormationConfig()
    schedule,mold,report=build_pour_source_schedule(source,c,samples_per_axis=1,formation=formation)
    t=schedule['releaseTime'];z=schedule['positions'][:,2]
    assert len(t)==report['sourceNumericalParticles']
    assert len(t)==report['targetSamples']*formation.source_longitudinal_subdivisions
    assert np.all(np.diff(t)>=0)
    assert t[0]==pytest.approx(0,abs=1e-12)
    assert t[-1]>.7
    assert report['simultaneousReservoirRelease'] is False
    assert report['sourceMassFluxIsParticleResolved'] is True
    assert report['sourceDurationSeconds']==pytest.approx(t[-1])
    assert report['sourceSubstepPeriodSeconds']==pytest.approx(
        report['sourceLayerPeriodSeconds']/formation.source_longitudinal_subdivisions)
    assert schedule['volumes'].sum()==pytest.approx(report['targetFillVolumeM3'],rel=1e-12)
    assert report['sourceVolumePreservedAfterSubdivision']==pytest.approx(report['targetFillVolumeM3'],rel=1e-12)
    assert z.min()>mold['wallTop']
    assert z.max()<formation.nozzle_bottom+c.spacing*.2
    assert schedule['materialCoordinates'][:,2].max()>z.max()+.1
    initial=np.searchsorted(t,1e-12,side='right')
    assert 0<initial<len(t)//4


def test_pour_formation_starts_as_feed_columns_above_the_cavity():
    source = Path('work/element-motion/sigil-02-v2/source.npz')
    assert source.is_file()
    c = LavaConfig(spacing=.018, shape=(96,68,82), origin=(-.864,-.612,0.),
                   max_dt=.0007, support_start=-1., support_end=-.5)
    formation = PourFormationConfig()
    pos,H,V,velocity,mold,report = build_pour_initial_state(source,c,samples_per_axis=1,formation=formation)
    assert len(pos) > 1000
    assert report['noTargetPositionForces'] is True
    assert len(report['inlets']) >= 3
    assert np.min(pos[:,2]) > mold['wallTop']
    # Feed-column z is a source-time parameterization; the scheduled particles
    # are respawned at nozzle_bottom and are the state constrained by the MPM domain.
    schedule,_,_=build_pour_source_schedule(source,c,samples_per_axis=1,formation=formation)
    assert schedule['positions'][:,2].max() < c.origin[2] + c.spacing*(c.shape[2]-6)
    assert all(row['radius'] <= row['requestedRadius']+1e-12 for row in report['inlets'])
    assert all(row['centerClearance'] >= row['radius'] for row in report['inlets'])
    assert np.linalg.norm(velocity[:,:2],axis=1).max() > 0
    temperature = temperature_from_enthalpy(H,c)
    assert temperature.max() > c.liquidus
    assert temperature.min() > c.solidus
    assert temperature.min() < c.liquidus
    assert np.all(V > 0)


def test_shallow_overflow_redistribution_is_conservative_and_component_local():
    labels=np.array([
        [1,1,0,2,2],
        [1,1,0,2,2],
    ],dtype=np.int32)
    h=np.array([
        [.09,.01,0.,.06,.01],
        [.01,.01,0.,.01,.01],
    ],dtype=np.float64)
    before=h.sum()
    out=_redistribute_overflow(h,labels,.05)
    assert out.sum()==pytest.approx(before,rel=0,abs=1e-12)
    assert out[labels==1].max()<=.05+1e-12
    assert out[labels==2].max()<=.05+1e-12
    assert np.all(out[labels==0]==0.)
    assert out[0,3] > h[0,3] - .011  # component 2 is not fed by component 1 excess


def test_shallow_inlet_capacity_partition_matches_cavity_target():
    source=Path('work/element-motion/sigil-02-v2/source.npz')
    assert source.is_file()
    formation=PourFormationConfig(main_nozzles=7,nozzle_bottom=.105)
    cfg=ShallowLavaConfig(nx=112,ny=56,pour_duration=1.4,target_depth=.038)
    state=initialize_shallow(source,formation,cfg)
    assigned=sum(src['assignedVolumeM3'] for src in state['sources'])
    assert assigned==pytest.approx(state['targetVolumeM3'],rel=5e-3)
    assert sum(src['territoryCells'] for src in state['sources'])==np.count_nonzero(state['mask'])
    assert all(src['sigma']>=cfg.source_sigma_min for src in state['sources'])
    assert all(src['sigma']<=cfg.source_sigma_max for src in state['sources'])


def test_shallow_short_run_conserves_injected_volume_and_caps_source_mounds():
    source=Path('work/element-motion/sigil-02-v2/source.npz')
    formation=PourFormationConfig(main_nozzles=7,nozzle_bottom=.105)
    cfg=ShallowLavaConfig(
        nx=96,ny=48,pour_duration=1.0,inlet_stagger_seconds=.25,
        target_depth=.032,max_depth=.048,max_dt=.008)
    state=initialize_shallow(source,formation,cfg)
    advance_shallow(state,0.,.45,cfg)
    m=shallow_metrics(state,.45,cfg)
    assert abs(m['massBalanceRelative'])<5e-4
    assert m['maximumDepthM']<=cfg.max_depth+1e-8
    assert m['wetCoverageFraction']>0.
    assert m['skinTemperatureMaxK']>cfg.liquidus
