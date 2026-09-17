"""Transactional alternation and temporal error control for CPU MPM.

Every trial begins at the same accepted state. Heat, bed and gas mutations are
rolled back with mechanics. Neither a rejected solve nor its ledger survives.
"""
import copy
import time
import numpy as np


def clone_state(values):
    """Copy mutable physics, retaining append-only diagnostic records.

    Accepted rows are immutable: _step appends a new row and coupling edits
    only that new row. Copying their entire history at every Newton trial
    made the cost grow with the duration of a run. The list itself must be
    copied so rejected appends cannot survive rollback.
    """
    result={}
    for key,value in values.items():
        if key=='rows':result[key]=list(value)
        elif key=='_adaptive_report':result[key]=dict(value,records=list(value.get('records',[])))
        else:result[key]=copy.deepcopy(value)
    return result


def snapshot(s,kwargs):
    auxiliary={k:copy.deepcopy(kwargs[k].__dict__) for k in ('gas','bed') if kwargs.get(k) is not None}
    return clone_state(s.__dict__),auxiliary


def restore(s,kwargs,state):
    s.__dict__.clear();s.__dict__.update(clone_state(state[0]))
    for k,values in state[1].items():
        kwargs[k].__dict__.clear();kwargs[k].__dict__.update(copy.deepcopy(values))


def coupled_step(s,dt,**kwargs):
    state=snapshot(s,kwargs);old=state[0];guess=old['damage'].copy();old_g=np.maximum((1-old['damage'])**2,1e-8)
    count=len(guess);power=s.material.rheology=='basalt_power_creep'
    if power:
        sigma=np.sqrt(1.5*np.sum((old['deviator']/old_g[:,None])**2,axis=1))
        guess=np.r_[guess,np.log1p(sigma/1e6)]
    previous_velocity=None;compression=old['dilation']<-1e-10
    acceleration=getattr(s,'damage_acceleration','anderson')
    history_x=[];history_r=[];history_g=[];residuals=[];relaxing=False;restarts=0
    try:
        for iteration in range(80):
            if time.monotonic()>old.get('_solve_deadline',float('inf')):
                raise TimeoutError('CPU solve deadline reached; trial rolled back')
            restore(s,kwargs,state)
            # Same old elastic strain, evaluated with the trial degradation.
            s.damage=guess[:count].copy();s.deviator=old['deviator']*(np.maximum((1-s.damage)**2,1e-8)/old_g)[:,None]
            if power:s._creep_stress_guess=np.expm1(guess[count:])*1e6
            s._accepted_damage=old['damage'].copy()
            s._compression_active=compression.copy()
            row=s._step(dt,**kwargs)
            target=s.damage.copy();damage_error=float(np.max(abs(target-guess[:count])))
            creep_error=0.
            if power:
                target=np.r_[target,np.log1p(s._trial_creep_stress/1e6)]
                creep_error=float(np.max(abs(target[count:]-guess[count:])))
            next_compression=s._trial_dilation<-1e-10
            # The unilateral pressure complementarity now converges inside
            # the momentum solve; no discontinuous outer pressure switch.
            pressure_changes=0
            velocity_error=float('inf') if previous_velocity is None else float(np.max(np.linalg.norm(s.v-previous_velocity,axis=1)))
            if damage_error<2e-5 and creep_error<1e-6 and pressure_changes==0 and (iteration==0 or velocity_error<1e-6):
                row.update(damageCouplingIterations=iteration+1,damageCouplingResidual=damage_error,damageCouplingVelocityResidual=0. if iteration==0 else velocity_error,damageAcceleration=acceleration,accelerationRestarts=restarts)
                if power:row['creepCouplingLogStressResidual']=creep_error
                if hasattr(s,'_phase_report'):
                    row['phaseField']=dict(s._phase_report)
                    increment=s._phase_report['fractureEnergyJ']-s._phase_report['previousFractureEnergyJ']
                    s.ledger['fracture']=old['ledger']['fracture']+max(0.,increment)
                    row['fractureEnergyJ']=max(0.,increment)
                return row
            # Irreversibility applies while a coherent skeleton exists.
            # A melted network releases damage; clamping to the old solid
            # damage here made a fully melted, previously broken point fail
            # every iteration even though both momentum solves agreed.
            coherent=s.material.solid(s.material.temperature(s.h))>s.failure_fraction
            lower=np.where(coherent,old['damage'],0.)
            previous_velocity=s.v.copy()
            if acceleration=='anderson':
                # Safeguarded AA/relaxation, following the strategy described
                # by Storvik et al. (2021). Only the iteration is accelerated;
                # the constitutive equations, bounds and final tolerances
                # are unchanged. This is not a port of their FEM solver.
                residual=target-guess;norm=float(np.linalg.norm(residual));residuals.append(norm)
                if len(residuals)>1 and norm>residuals[-2]*1.001:
                    relaxing=True;history_x=[];history_r=[];history_g=[];restarts+=1
                if relaxing and len(residuals)>=4 and all(a>=b for a,b in zip(residuals[-4:-1],residuals[-3:])):
                    relaxing=False;history_x=[];history_r=[];history_g=[]
                if relaxing:
                    # The power-creep stress map can reverse sign, with a
                    # scalar log-stress slope as low as -(n-1). The old 1.4
                    # over-relaxation amplified that oscillation precisely
                    # when the safeguard was supposed to reduce it. This
                    # damping balances the scalar slope interval; the full
                    # coupled equations still require their original checks.
                    omega=2/(s.material.rock_creep_n+1) if power else 1.4
                    candidate=guess+omega*residual
                else:
                    history_x.append(guess.copy());history_r.append(residual.copy());history_g.append(target.copy())
                    history_x=history_x[-4:];history_r=history_r[-4:];history_g=history_g[-4:]
                    candidate=target.copy()
                    if len(history_r)>1:
                        R=np.column_stack([b-a for a,b in zip(history_r[:-1],history_r[1:])])
                        G=np.column_stack([b-a for a,b in zip(history_g[:-1],history_g[1:])])
                        gamma=np.linalg.lstsq(R,residual,rcond=1e-8)[0]
                        if np.linalg.norm(gamma)<50:candidate-=G@gamma
            elif acceleration=='relaxed':candidate=.5*guess+.5*target
            else:raise ValueError('Unknown damage acceleration')
            if power and (not np.isfinite(candidate).all() or np.max(candidate[count:])>30):candidate=.5*guess+.5*target
            guess_damage=np.where(coherent,np.clip(candidate[:count],lower,1.),0.)
            guess=np.r_[guess_damage,np.maximum(candidate[count:],0.)] if power else guess_damage
            compression=next_compression
        raise RuntimeError(('Damage/momentum alternation did not converge',damage_error,velocity_error,'creepLogStressResidual',creep_error,'pressureActiveChanges',pressure_changes))
    except Exception:
        restore(s,kwargs,state)
        raise


def temporal_error(a,b,cell,rtol=.03):
    mass=b['mass'];mass=mass/mass.sum()
    rms=lambda q:float(np.sqrt(np.sum(mass[:,None]*q*q)))
    speed=rms(b['v']);velocity=rms(a['v']-b['v'])/(2e-5+rtol*speed)
    position=float(np.max(np.linalg.norm((a['x']-b['x'])/cell,axis=1)))/.005
    damage=float(np.max(abs(a['damage']-b['damage'])))/.01
    from lava_mpm import Material
    material=b['material'];ta=material.temperature(a['h']);tb=material.temperature(b['h'])
    temperature=float(np.max(abs(ta-tb)))/.5
    works=[]
    for k in ('prescribed_boundary_work','inlet_boundary_work'):
        wa=a['ledger'].get(k,0);wb=b['ledger'].get(k,0)
        works.append(abs(wa-wb)/(1e-10+rtol*max(abs(wa),abs(wb))))
    return dict(velocity=velocity,position=position,damage=damage,temperature=temperature,work=max(works))


def error_state(s,old):
    result={key:getattr(s,key).copy() for key in ('x','v','mass','damage','h')}
    result['material']=s.material
    result['ledger']={key:s.ledger.get(key,0)-old['ledger'].get(key,0)
                      for key in ('prescribed_boundary_work','inlet_boundary_work')}
    return result


def advance(s,duration,max_dt=.01,min_dt=1e-7,max_trials=400,rtol=.03,max_wall=120,advance_auxiliaries=False,initial_dt=None,thermal_preflight=True,**kwargs):
    end=s.time+duration;dt=min(max_dt,duration,initial_dt if initial_dt is not None else max_dt);accepted=0;rejected=0;trials=0;records=[];start=time.monotonic();preflight_rejected=0
    last_failure=None
    def one_step(h,heat_only=False):
        previous_deadline=getattr(s,'_solve_deadline',None)
        s._solve_deadline=min(previous_deadline if previous_deadline is not None else float('inf'),start+max_wall)
        options=dict(kwargs,mechanics=False) if heat_only else kwargs
        try:row=s.step(h,**options)
        finally:
            if previous_deadline is None:s.__dict__.pop('_solve_deadline',None)
            else:s._solve_deadline=previous_deadline
        if advance_auxiliaries:
            gas=kwargs.get('gas');bed=kwargs.get('bed')
            if gas is not None:row['gas']=gas.advance(h,s.x,s.volume)
            if bed is not None and hasattr(bed,'advance'):row['bed']=bed.advance(h)
    while s.time<end-1e-12:
        s._adaptive_report=dict(accepted=accepted,rejected=rejected,trials=trials,records=records.copy(),nextDt=dt,lastFailure=last_failure,thermalPreflightRejected=preflight_rejected)
        if time.monotonic()-start>max_wall:raise RuntimeError('Adaptive CPU wall budget reached at last accepted state')
        dt=min(dt,end-s.time);state=snapshot(s,kwargs);trials+=1
        if trials>max_trials:raise RuntimeError('Adaptive CPU trial budget exhausted at last accepted state')
        try:
            if thermal_preflight and kwargs.get('thermal',True) and kwargs.get('mechanics',True):
                # Reject an obviously inaccurate heat interval before paying
                # for its nonlinear momentum/contact solves. Frozen-motion
                # trials are discarded completely, including bed/gas heat.
                # They can only REDUCE dt: acceptance still requires the
                # original full coupled step-doubling checks below.
                one_step(dt,True);coarse_t=s.material.temperature(s.h)
                coarse_rock=np.array(kwargs['bed'].temperature,copy=True) if advance_auxiliaries and kwargs.get('bed') is not None else None
                restore(s,kwargs,state);one_step(dt/2,True);one_step(dt/2,True)
                preview=float(np.max(abs(coarse_t-s.material.temperature(s.h))))/.5
                if coarse_rock is not None:preview=max(preview,float(np.max(abs(coarse_rock-np.asarray(kwargs['bed'].temperature))))/.5)
                restore(s,kwargs,state)
                if preview>1 or not np.isfinite(preview):
                    preflight_rejected+=1
                    raise ArithmeticError(('Heat preflight requests smaller interval',preview))
            one_step(dt);coarse=error_state(s,state[0])
            coarse_bed=np.array(kwargs['bed'].temperature,copy=True) if advance_auxiliaries and kwargs.get('bed') is not None else None
            restore(s,kwargs,state)
            one_step(dt/2);one_step(dt/2)
            fine=error_state(s,state[0])
            errors=temporal_error(coarse,fine,s.cell_size,rtol)
            if coarse_bed is not None:errors['substrateTemperature']=float(np.max(abs(coarse_bed-np.asarray(kwargs['bed'].temperature))))/.5
            error=max(errors.values())
            if error>1 or not np.isfinite(error):raise ArithmeticError(('Temporal estimate failed',errors))
            accepted+=1;records.append(dict(time=s.time,dt=dt,errors=errors))
            dt=min(max_dt,dt*min(1.8,max(.2,.85/np.sqrt(max(error,1e-12)))))
        except TimeoutError:
            restore(s,kwargs,state)
            raise
        except (RuntimeError,ArithmeticError,ValueError) as exc:
            restore(s,kwargs,state);rejected+=1;dt*=.5;last_failure=str(exc)
            if dt<min_dt:raise RuntimeError(('No accurate step above minimum dt',str(exc))) from exc
    return dict(accepted=accepted,rejected=rejected,trials=trials,records=records,nextDt=dt,thermalPreflightRejected=preflight_rejected)
