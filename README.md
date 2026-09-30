# CYBR ELEMENTS

Offline graphics and simulation experiments by **Alejandro Figueroa / Cybrdelic**.
The project turns custom sigil geometry into liquid, reactive fire, smoke,
fractured solids and branching electrical channels, then renders the results
into a browser showcase.

![Montage of the actual fire, water, earth, air, ice, lava and lightning films](docs/media/elements-02.gif)

The montage is assembled from the included renders at 10 fps. The individual
films are **1920 × 1080, 30 fps**, without audio. The browser plays those films;
the simulation and rendering pipelines run offline.

## Run the showcase

Requires **Python 3.11+** and a browser. The current films, posters and fonts are
included in Git; viewing them needs no GPU, Python packages or npm install.

```sh
git clone https://github.com/cybrdelic/cybr-elements.git
cd cybr-elements
python scripts/serve.py
```

Open **[http://127.0.0.1:8767/](http://127.0.0.1:8767/)** for the current player.
The [font specimen](http://127.0.0.1:8767/typefaces/) is served by the same command.

## Current films

| Material | Implementation | Film |
| --- | --- | --- |
| Fire | 3D fuel/oxidizer transport, reaction, cooling and buoyancy; custom volume rendering | [9.8 s](outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-02.mp4) |
| Water | Particle-grid APIC/FLIP, pressure projection, surface reconstruction and Cycles rendering | [11.2 s](outputs/cybrdelic-type/elements/motion/bending/sigils/02/water-02-r8.mp4) |
| Earth | Guided fractured geometry, Bullet collisions and floor settling | [10 s](outputs/cybrdelic-type/elements/motion/bending/sigils/02/earth-02-r6.mp4) |
| Air | Advected 3D smoke and turbulent forcing | [9.8 s](outputs/cybrdelic-type/elements/motion/bending/sigils/02/air-02.mp4) |
| Ice | Transmissive fractured solids, rigid-body release and advected cold mist | [10 s](outputs/cybrdelic-type/elements/motion/bending/sigils/02/ice-02.mp4) |
| Lava | Displaced basalt crust, emissive interior geometry, rigid fragments and smoke | [10 s](outputs/cybrdelic-type/elements/motion/bending/sigils/02/lava-02.mp4) |
| Lightning | Branching 3D growth trees, authored discharge pulses and volumetric lighting | [10 s](outputs/cybrdelic-type/elements/motion/bending/sigils/02/lightning-02-r5.mp4) |

GitHub may download MP4 links. The local player provides native playback,
scrubbing and fullscreen controls, earlier water/earth/lightning revisions,
artwork comparison, film downloads and shareable selection URLs. Keyboard
navigation and reduced-motion handling are included.

## Engineering scope

- **Fluid solver:** the vendored JavaScript APIC/FLIP implementation runs under
  Node.js for production water. It uses quadratic particle-grid transfers,
  multigrid-preconditioned conjugate-gradient pressure projection, surface
  tension and collider handling. Surface reconstruction separates the main
  liquid body from isolated particle clusters.
- **Gas volumes:** fire uses a PyTorch/CUDA graphics combustion model. The
  ice/lava/lightning atmospheres use CPU semi-Lagrangian advection, buoyancy,
  dissipation and Fourier-space pressure projection. Density atlases store
  3D fields for volumetric rendering.
- **Geometry and shading:** custom artwork defines source fields and fracture
  geometry. Blender handles Bullet rigid bodies, Cycles surface rendering and
  Eevee lightning volumes. Materials include absorption/transmission, basalt
  displacement and emissive seams.
- **Delivery:** a static media player, versioned archive restoration with
  SHA-256 verification, automated repository checks and browser regressions.

The suspended forms and assembly trajectories are art-directed. The current
water film joins an earlier opening to a new forward-simulated hold/release;
it is not one uninterrupted solve. Ice and lava are fractured-solid material
effects, and electricity is a visual discharge model. There is no calibrated
freezing, molten-lava rheology or plasma simulation. See
[pipeline details](docs/PIPELINES.md) for the actual algorithms and limitations.

## Check the project

```sh
# Check the current showcase and repository contracts
python scripts/check.py

# Python regression suite
python -m unittest discover -s scripts -p 'test_*.py'

# Also probe and fully decode the current films; requires FFmpeg/ffprobe
python scripts/check.py --media

# Player regression suite; requires Node.js 20+ and Chromium
npm ci
npx playwright install chromium
npm run test:browser
```

[Development notes](docs/DEVELOPMENT.md) describe the server, checks and optional
archive workflow. Numerical tests and successful decoding establish specific
properties; the rendered appearance still needs visual review.

## Physical studio renderer

The newer [studio pipeline](docs/STUDIO.md) fixes suppressed water illumination,
stone texture stretching and underlit ice, renders fire/air as perspective VDB
volumes, and includes a separate conservative viscous lava study. It preserves
the historical films above and records actual frame/source hashes for fresh
reviews and complete rebuilds. Reviews and full production timelines are labeled
separately; visual quality remains a frame-and-motion review requirement.

## Repository layout

| Path | Purpose |
| --- | --- |
| [`outputs/cybrdelic-type/elements/motion/bending/sigils/02/`](outputs/cybrdelic-type/elements/motion/bending/sigils/02/) | Current player, films, posters and selected earlier revisions |
| [`outputs/cybrdelic-type/typefaces/`](outputs/cybrdelic-type/typefaces/) | Font specimen, font files, vector masters and build sources |
| [`work/element-motion/`](work/element-motion/) | Simulation, reconstruction, material and rendering source; retained experiments |
| [`work/flip-lettering/vendor/`](work/flip-lettering/vendor/) | APIC/FLIP implementation and reconstruction tools |
| [`work/brand-font/`](work/brand-font/) | Typeface construction tools |
| [`scripts/`](scripts/) | Local server, checks, asset restoration and publication tools |
| [`docs/`](docs/) | Pipeline documentation, asset inventory and third-party notices |

The current showcase is the supported viewing entry point. Older research
galleries remain in the archive; they include prototypes with different
dependencies, visual quality and simulation methods.

## Optional archive and rebuilding

Larger historical media, cached browser meshes, textures and retained research
inputs are stored in the [v0.1.0 asset release](https://github.com/cybrdelic/cybr-elements/releases/tag/v0.1.0).
Restore original paths with the standard-library downloader:

```sh
python scripts/fetch_assets.py --site  # Historical galleries and browser assets
python scripts/fetch_assets.py --all   # Also geometry, textures and research inputs
```

The downloader verifies hashes, skips matching files and refuses to overwrite
modified files. The full archive requires several GB of disk space. After
`--site`, open the [historical gallery](http://127.0.0.1:8767/archive/).

**Rebuilding renders is a separate workflow.** It requires pipeline-specific
dependencies and regenerated caches; production was developed on Windows with
Blender 4.5.3 LTS and an RTX 4060 Laptop GPU. Several historical scripts retain
machine-specific paths and review gates. Start with [rebuild notes](docs/PIPELINES.md)
before launching a simulation. Archive restoration does not constitute a
portable, complete render environment.

## Custom typefaces

**Cybrdelic Sigil / 01** uses hooked, tapered forms; **Cybrdelic Cut / 02** uses
angular forms and diamond cuts. Both include TTF/WOFF2, uppercase, lowercase,
figures, punctuation and Latin accents. The lowercase `cybrdelic` wordmark is
available as a discretionary ligature or at **U+E000**. These are single-weight
display faces.

[Font files](outputs/cybrdelic-type/typefaces/fonts/) ·
[Usage and coverage](outputs/cybrdelic-type/typefaces/README.md) ·
[SVG masters](outputs/cybrdelic-type/typefaces/vector/)

## License and credits

[GNU GPL v2](LICENSE), with component-specific notices retained.
The basalt textures originate from Poly Haven CC0 scans; attribution and
dependency notices are in [THIRD_PARTY.md](docs/THIRD_PARTY.md).
The elemental bending vocabulary is inspired by *Avatar: The Last Airbender*
and *The Legend of Korra*. This is an independent project.
