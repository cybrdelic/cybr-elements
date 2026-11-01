# Shared ELEMENTS runtime review

This clean review snapshot is based on public `master`
`79ae673eee773cda972aaf4a56d1f0f0e1cd79a0`. It incorporates the shared-flow
prerequisite proposed in draft PR #16 and the maintained runtime snapshot
`8d85231127437b81eb38bda4dff7d14a6ae681d0`, without publishing development
history or replacing the existing interactive browser engines.

## Scope

Eighteen Fire/Air/dust entrypoints select explicit scene policies and share
transport, projection, session state, resource preflight, checkpoint/resume,
encoding and receipt owners. Distinct source, domain and optical methods remain
explicit rather than being replaced by a generic look. Automatic device choice
uses available CUDA, otherwise CPU; explicit overrides remain authoritative.
A CUDA execution failure does not silently retry on CPU.

The root NumPy package exposes the portable `cybr_elements.lava_optics` API for
SCENES. It uses the analytic observer port, not measured CIE-table equivalence,
and is not a thermomechanical lava model.

All eighteen registered recipes now have their authentic required source
inputs. The restored 6,417-byte `c-stroke.npz` is byte-identical to the original
public v0.1.0 release's `project-assets-047.zip` member; the public release digest,
member digest and data contract are retained in its adjacent provenance JSON.
Input readiness is not a completed film or hardware qualification. Optional
legacy gesture21/21b modules remain unavailable rather than approximated.

## Source and licensing boundary

Existing GPLv2 and third-party notices are unchanged. No new project-wide
license is asserted. Unrelated public files and assets remain untouched in the
base tree. No private project history, private ARX/CAD/body data, credentials,
private storage URLs or account Library IDs are included. Publication uses
reviewed file overlays, not development commit ancestry.

The consumer-test oracle now points directly to the public default base above;
all sixteen referenced original scripts were verified byte-identical to the
previous public oracle revision. Numerical tests are not weakened. GitHub CI
retains the CPU differential matrix and adds authentic input/backend checks.
Historical CUDA receipts describe earlier hardware execution only; they do not
qualify the new runtime on this CPU-only publication worker.

## Reproduction and limitations

```sh
python -m pip install torch==2.6.0 numpy==2.2.6 Pillow==11.3.0
python work/element-motion/sigil_02_build_v2.py --check
python work/element-motion/test_flow_receipts.py
python work/element-motion/test_recipe_availability.py
python work/element-motion/verify_element_flow.py --device cpu --report parity.json
python work/element-motion/test_flow_consumers.py
```

Consumer tests also require ffmpeg/ffprobe. The full Git checkout retains the
public baseline used by the oracle. Full-grid, full-film convergence, continuous
visual quality, CUDA/browser execution and physical calibration remain separate
acceptance gates. The recorded full-grid CPU sample is feasibility evidence,
not a completed 294-frame production film. No merge, auto-merge, deployment,
binary release or new visual-quality claim is requested.

## Publication preflight

Fresh isolated-source CPU verification passed the generator provenance check,
5 receipt tests, 7 input/backend tests and 6 consumer tests. There were 24 exact
style-02 whole-step comparisons with two byte-identical 1920×1080 optical outputs,
and 180 exact legacy-consumer whole-step comparisons with 15 identical 1080p
RGB outputs. Local dependencies were Torch 2.15.0+cpu, NumPy 2.3.5 and Pillow
13.0.0; hosted CI uses its separately pinned matrix. No new GPU test was run.
