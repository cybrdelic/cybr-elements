# Corrected scalar advection

The live Fire demo loads `corrected-advection.js` before `fire.js`. Each simulation step runs a MacCormack predictor over the current GPU volume. The main simulation shader then traces backward from that prediction, corrects fuel, oxygen, temperature, and soot, and clamps each corrected value to the eight source cells around its departure point. Velocity, chemistry, pressure correction, pointer force, and rendering continue to evolve from live GPU state. This path reads no prerecorded frames or temporal motion fields.

The predictor adds one RGBA16F atlas and one full-volume draw per step. Fuel, oxygen, temperature, and soot occupy the four lanes of `chemTex`; velocity and instantaneous reaction occupy `vfTex`. The predictor samples only `chemTex` at its departure point, and the limiter needs eight texture reads rather than sixteen. All source-cell extrema and the forward/reverse correction are retained.

The live page uses 640 × 360 × 32 cells with the native 896 × 504 static emitter and 896 × 504 optical projection. `?grid=896` selects the slower 896 × 504 × 32 variant. Measured frame rate depends on accumulated smoke and GPU scheduling; current smoke and drag benchmarks live in `work/fire-smoke-qa/report.json`. The simulation remains capped at 30 fixed steps per second.

The visual gain is sharper, more coherent internal flame detail than first-order advection. The remaining gap against the offline Fire includes its deeper 56-layer volume, 90 solver steps per second, resolved 3D vorticity, and full-grid spectral pressure projection. The live volume's coarse pressure solve and procedural turbulent force are still approximations.
