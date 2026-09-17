# GPU work — 15 September 2026

The user authorized GPU use where it actually helps. This revision adds an
opt-in CUDA linear-algebra path and a working CUDA Mitsuba optical proof.
It does **not** fix the fractured-basalt appearance, and no new frame or
video was promoted to the public lava page.

## Retained implementation

- `lava_mpm_linear27.py`: bounded FP64 CUDA Cholesky for unilateral pressure;
  repeated pressure substitutions remain on the CPU.
- `lava_mpm_cuda_contact27.py`: all contact right-hand sides are solved
  together on CUDA, including two refinement passes against the original
  physical matrix. The existing CPU Coulomb iteration, stationarity, cone,
  dissipation and nonlinear acceptance checks remain in force.
- `lava_mpm_friction.py`: CPU remains the default. CUDA batching is opt-in.
- `lava_mpm_reservoir.py`: reservoir boundary extracted from a CPU CLI
  module so importing the boundary no longer silently hides the GPU.
- `lava_mpm_native_optics26.py --device cuda`: native Mitsuba CUDA rendering;
  texture preparation and OIDN denoising remain on the CPU.

Simulation equations, material constants, particles, sources, damage
thresholds, geometry reconstruction, lights and camera were not modified
to manufacture a visual improvement.

## Evidence

The initial pressure-only route did not establish a whole-simulation gain.
It accepted only 0.375 seconds of simulation within its 120-second budget.
Moving thousands of small triangular solves individually to CUDA was also
slower. The private sparse-substitution experiment was rejected and removed.
An earlier hybrid process exited without a Python traceback; its cause was
not established and that run is not accepted evidence.

The retained **batched** route completed 0.5 simulated seconds in **47.735
seconds**: four accepted 0.125-second steps, 892 particles, 98 pressure
factors and 62 contact factors, with no CPU fallback. The PyTorch allocation
peak was 141,879,296 bytes. This excludes driver/context allocations and
other applications; it is not a total VRAM measurement.

A fresh CPU run with exactly the same core source hashes reached the
0.25-second checkpoint in **110.25 seconds**, versus **26.25 seconds** for
CUDA: an observed 4.2x gain at that checkpoint. The CPU run then stopped
at its 120-second budget, so there is no completed same-core 0.5-second
CPU timing. Other user workloads were active; this is a short operational
comparison, not an isolated hardware benchmark or a guaranteed speedup.
The same-core numerical comparison is recorded in
`cuda-batched-27-cpu-batched-reference-27-0250-comparison.json`.

Against the archived CPU checkpoint at 0.5 seconds, maximum position
difference was 4.383e-12 m, relative velocity difference 6.123e-9,
temperature difference 3.904e-10 K, damage difference 1.977e-13 and mass
difference zero. The archived CPU run used an older equivalent pressure
predictor. Source hashes and this limitation are preserved in
`cuda-batched-27-resolved-feed-0500-comparison.json`.

The complete captured real Coulomb system has 1,914 degrees of freedom
and 738 contact directions. CUDA passed the unchanged acceptance thresholds
with maximum velocity difference 8.251e-8 m/s. See
`batched-contact/solve-check.json` for CPU/GPU timings and separately measured
CUDA startup. The earlier scaled-residual result failed the absolute
velocity threshold; it remains in `solve-scaled-rejected.json`. The fix
was refinement against the original matrix, not a relaxed threshold.

The native CUDA Mitsuba proof is at
`../rebuild-25/thermal-unloaded/cuda-optical-proof/state.png`. It is
640 × 400 at 16 spp, with a 50.578-second cold total including atlas
preparation, startup, CPU denoising and output. It was visually inspected:
the underlying geometry is still an unbroken rounded cap. There is no
like-for-like renderer speedup claim from that cold proof.

## What still prevents the requested lava

The coarse lobe remains unfractured: zero broken edges after 0.5 seconds.
Only 144 of 868 initial particles are fully solid. Its mapped thermal
profile has a fully solid layer approximately 3.30 mm deep, while vertical
particle spacing is 4 mm and fracture length is 16 mm. That is inadequate
resolution for the intended thin crust and separated plates.

The initial aged profile is stress-free: it omits the actual 3D cooling and
thermal-stress history. Faster algebra does not restore that history or
create missing geometric fracture surfaces. A larger particle count alone
does not correct those physical and discretization limitations.

The next useful simulation work is resolved crust formation and breakup,
with actual open gaps and solid/molten interaction checked before another
beauty render. The public preview remains unchanged because these tests
demonstrate performance and numerical agreement, not visual acceptance.

## Reproduction

From `work/element-motion/mitsuba-rebuild`, use the existing `.venv` Python.
For the opt-in batched route set both environment variables:

```powershell
$env:LAVA_MPM_LINEAR_BACKEND = 'cuda_dense'
$env:LAVA_MPM_FRICTION_BACKEND = 'cuda_batched'
$env:CUDA_VISIBLE_DEVICES = '0'
& .venv/Scripts/python.exe lava_mpm_scene26.py --name gpu-review-new --until 0.5 --dt 0.125 --wall 120
```

Always use a new case after core code changes. CPU uses both backends set
to `cpu`. CUDA pressure is bounded to 6,144 DOFs; batched contact to 4,096
DOFs and a conservative 1.5 GiB estimated allocation gate. Larger systems
explicitly fall back and record the reason. These dense paths are not a
scalable GPU-native MPM implementation for millions of particles.
