Water r7 / Earth r6: loosened floor entrances

The revised entrances use reverse playback of the accepted native-simulation
falling sequences. This is a CPU video edit, not a newly solved forward FLIP or
Bullet entrance. No GPU rendering was performed for this revision.

Water's prior path used a strong per-particle position/velocity servo, producing
a stiff, coherent ribbon. Earth's prior authored path stored seeded yaw as
seed * 2.399 radians and linearly interpolated that unwrapped Euler value to
zero. Seed 173 therefore unwound about 66.05 full turns. A future forward earth
choreography must use shortest-arc quaternions or wrapped, bounded angles.
This edit bypasses both authored entrances and uses the irregular breakup
motion already approved by the user as the basis for the gathering lift.

Two 960 x 540 CPU timing previews were reviewed. The longer edit held the
settled puddle/pile for too long, so the selected version begins at original
frame 330. Original frames 330 down to 210 form the entrance. Original frames
211 through 389 then play forward. There is no duplicate middle frame, optical
flow interpolation, fade, particle synthesis, material change, or new geometry.
The gentle held-state motion changes direction at the midpoint; this is a
reverse-playback treatment, not a claim of forward physical causality.

Both final videos are 1920 x 1080, 30 fps, 300 frames, 10 seconds. Original
falling frames 243 through 389 map exactly in order to output frames 153 through
299. Their timing and physical motion are preserved. The MP4s are re-encoded,
so pixel values are not bit-identical; all falling frames were compared to the
source at 480 x 270. Minimum PSNR exceeds 51 dB; maximum mean absolute pixel
error is below 0.2 on a 0-255 scale. All frames decoded successfully. The
hold-direction change has no frame-difference spike.

Water source: water-02-r6.mp4. Earth source: earth-02-r5.mp4. Those files, plus
fire, air and lightning, remain unchanged. New player versions are water r7 and
earth r6, with previous-version buttons retaining those source videos.

Agent visual review passed. User acceptance remains pending. Source-frame
maps, hashes, per-frame comparisons, CPU previews and final contact sheets
are stored alongside this note. Entry points are sigil_02_return_preview.py and
sigil_02_return_finish.py in the parent directory.
