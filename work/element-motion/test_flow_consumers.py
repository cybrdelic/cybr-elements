"""Whole-step parity for migrated consumers against their pinned Git sources.

Missing historical trail assets are not fabricated: operator tests inject the
same bounded nozzle fixture into both versions. The fire-v2/v3 movie smoke test
uses the original checked-in spline motion separately.
"""
import ast
import json
import subprocess
from pathlib import Path
import unittest
import numpy as np
import torch
from verify_element_flow import namespace, pixels

ROOT=Path(__file__).resolve().parent
# All 16 reference scripts are byte-identical at the public default base.
BASE='79ae673eee773cda972aaf4a56d1f0f0e1cd79a0'
CONSUMERS=('fire-v3','air-v2','air-v3','bending-fire-v5','fire-material-v2',
           'earth-dust','fire-v2','air-material','sigil_native_fire_fed',
           'fire-sheets','fire-shared','bending-air','air-shared',
           'air-material-v2','fire-material')


def source(name, old=False):
    path=f'work/element-motion/{name}.py'
    if old:
        return subprocess.check_output(['git','show',f'{BASE}:{path}'],cwd=ROOT.parent.parent).decode()
    return (ROOT/f'{name}.py').read_text()


def consumer_namespace(text, *, size=(23,10,17), fps=24, control='none', motion=None):
    # The original legacy scripts expose these globals via their motion imports.
    # Execute only pure initialization/functions: never a fixed-path CUDA bake.
    motion=motion or dict(MODE='arc',START=.08,WRITE=1.6,
        nozzle_pose=lambda t:(np.array([-.2,1.6]),np.array([.8,.6]),.7,4.),
        nozzle_turn=lambda t:.3)
    import verify_element_flow as harness
    ns=dict(torch=torch,F=harness.F,np=np,math=harness.math,Image=harness.Image,
        CollocatedFlow=harness.CollocatedFlow,device='cpu',ROOT=ROOT,
        a=harness.SimpleNamespace(size=size,fps=fps,substeps=3,padded_domain=False,
            gesture_version='19',control=control,control_strength=1.,wind=.15),**motion)
    code=text[text.index('X,Y,Z=a.size'):text.index('rows=[];')]
    exec(compile(code,'<consumer-grid>','exec'),ns)
    nodes=[n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<consumer-functions>','exec'),ns)
    return ns


from types import SimpleNamespace
from element_session import ElementSession
from element_scenes import SCENES
from element_runner import parser,save_checkpoint,load_checkpoint,encode_frames
import tempfile


def session(name,**changes):
    args=parser(name).parse_args([])
    for key,value in dict(size=(23,10,17),wind=.15,**changes).items():setattr(args,key,value)
    motion=dict(identity='fixed-nozzle-regression-v1',MODE='arc',START=.08,WRITE=1.6,
        nozzle_pose=lambda t:(np.array([-.2,1.6]),np.array([.8,.6]),.7,4.),nozzle_turn=lambda t:.3)
    return ElementSession(SCENES[name],args,motion=motion)


class ConsumerParity(unittest.TestCase):
    def setUp(self):torch.set_num_threads(2);torch.set_grad_enabled(False)

    def test_native_encoder_cadence(self):
        for name in CONSUMERS:
            for fps in (24,30,60):
                s=session(name,fps=fps)
                self.assertEqual(s.FPS,fps);self.assertEqual(s.SIM_FPS,fps)
                self.assertEqual(s.dt,1/(fps*s.a.substeps))

    def test_all_consumers(self):
        for name in CONSUMERS:
            for fps in (24,30):
                for control in ('none','directed'):
                    with self.subTest(consumer=name,fps=fps,control=control):
                        before=consumer_namespace(source(name,True),fps=fps,control=control)
                        after=session(name,fps=fps,control=control)
                        torch.manual_seed(418)
                        state=torch.rand_like(before['state']);state[:,:3]=(state[:,:3]-.5)*14
                        before['state']=state.clone();after.state=state.clone()
                        for t in (.4,1.9,7.2):
                            d0=before['step'](t);d1=after.step(t)
                            self.assertTrue(torch.equal(before['state'],after.state))
                            self.assertEqual(d0,d1)
                        if fps==24 and control=='none':
                            self.assertTrue(np.array_equal(pixels(before),after.pixels(1)))
        print(json.dumps(dict(consumers=len(CONSUMERS),wholeStepComparisons=180,
            renderedPixelComparisons=15,pixelDimensions=[1920,1080],
            stateMaxAbsoluteError=0,originalFullFilmsVerified=False)))

    def test_checkpoint_resume_preserves_reservoir_and_native_clock(self):
        original=session('sigil_native_fire_fed');resumed=session('sigil_native_fire_fed')
        for _ in range(4):original.advance_frame()
        self.assertGreater(float(original.reservoir.max()),0)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'frame4.pt';save_checkpoint(original,path)
            self.assertEqual(load_checkpoint(resumed,path),4)
            with self.assertRaises(FileExistsError):save_checkpoint(original,path)
            for _ in range(4):
                self.assertEqual(original.advance_frame(),resumed.advance_frame())
                self.assertTrue(torch.equal(original.state,resumed.state))
                self.assertTrue(torch.equal(original.reservoir,resumed.reservoir))
            wrong=session('fire-v3');before=wrong.state.clone()
            with self.assertRaises(ValueError):load_checkpoint(wrong,path)
            self.assertTrue(torch.equal(before,wrong.state))

    def test_instances_do_not_share_mutable_state(self):
        a=session('air-v3');b=session('fire-v3');untouched=b.state.clone()
        a.advance_frame();self.assertTrue(torch.equal(b.state,untouched))
        self.assertIsNot(a.control_cache,b.control_cache)

    def test_style02_recipe_preserves_294_native_samples(self):
        from verify_element_flow import fields,namespace
        for name in ('sigil_02_air','sigil_02_air_v2','sigil_02_fire_v2'):
            for fps in (24,30):
                args=parser(name).parse_args(['--fps',str(fps)]);args.size=(23,10,17)
                current=ElementSession(SCENES[name],args,source_fields=fields(args.size))
                self.assertEqual(current.TOTAL,294)
                self.assertEqual(current.TOTAL/fps,12.25 if fps==24 else 9.8)
                self.assertEqual(current.spec.review_gate,135)
        old=namespace(source('sigil_02_air',True),size=(23,10,17),device='cpu')
        new=namespace(source('sigil_02_air'),size=(23,10,17),device='cpu')
        torch.manual_seed(36);old['state']=torch.rand_like(old['state']);new['state']=old['state'].clone()
        for t in (.4,1.9,7.2):
            self.assertEqual(old['step'](t),new['step'](t))
            self.assertTrue(torch.equal(old['state'],new['state']))
        self.assertTrue(np.array_equal(pixels(old),pixels(new)))

    def test_real_encoder_keeps_sample_count_and_duration(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)
            # Tiny diagnostic RGB samples test the encoder; not a scene artifact.
            for i in range(6):Image.fromarray(np.full((16,16,3),i*30,dtype=np.uint8)).save(p/f'{i:06d}.png')
            probe=encode_frames(p,p/'clock.mp4',6,24)
            self.assertEqual(int(probe['nb_frames']),6)
            self.assertEqual(float(probe['duration']),.25)


if __name__=='__main__':unittest.main()
