# Development

## Local viewing

Use Python 3.11 or newer:

```sh
python scripts/serve.py
```

The server binds to `127.0.0.1:8767` and serves
`outputs/cybrdelic-type/`. The root URL redirects to the current 02 player while
preserving query parameters. Useful routes:

| Route | Contents |
| --- | --- |
| `/` | Current seven-film player |
| `/typefaces/` | Font specimen |
| `/archive/` | Historical motion gallery; restore optional assets first |

The current player is a rendered-media viewer. It does not run the offline
solvers. Media URLs remain relative to the static site root, so keep the output
directory structure intact when hosting it elsewhere.

The player stores selection in the URL, for example
`/?element=water&version=previous&compare=1`. Browser Back/Forward restores that
state. Left/Right/Home/End move focus among material links; Enter selects one.
Play/pause, scrubbing and fullscreen use the browser's native video controls.
Reduced-motion and data-saving preferences disable autoplay, and switching
away from the tab pauses playback.

## Checks

Run from the repository root:

```sh
python scripts/check.py
python -m unittest discover -s scripts -p 'test_*.py'
```

`check.py` checks the supported current delivery. Optional archive assets are
not required for a clean checkout to pass. The Python regression suite covers
tool behavior without installing render dependencies or launching a GPU bake.

To include media probing and full video decoding, put FFmpeg and ffprobe on
PATH and run:

```sh
python scripts/check.py --media
```

Player tests use Node.js 20+ and Playwright:

```sh
npm ci
npx playwright install chromium
npm run test:browser
```

Keep the lockfile with dependency changes. Browser checks should run against the
supported server and current films, including narrow viewports and playback
transitions. A successful automated check does not establish the realism of a
material or the visual quality of an edited film.

## Optional asset restoration

```sh
python scripts/fetch_assets.py --site
python scripts/fetch_assets.py --all
```

`--site` restores historical output/gallery assets. `--all` also restores
retained geometry, textures and research inputs. Use one scope per invocation.
The inventory is `docs/assets.json`; the downloader restores original paths,
checks SHA-256, skips matching files and protects modified local files.

To check an already restored archive without downloading:

```sh
python scripts/fetch_assets.py --site --verify-only
```

Missing or modified assets cause a nonzero exit. Archive restoration is
optional for viewing and testing the current player. The release excludes
regenerable solver/render caches; rebuilding is documented in
[PIPELINES.md](PIPELINES.md).

## Updating the showcase

Keep a film, its poster, player metadata and README link on the same revision.
Decode a replacement fully before selecting it in the player, then run the
repository and browser checks. Preserve retained comparison versions unless
their removal is intentional.

To regenerate the README montage from existing films:

```sh
python -m pip install Pillow
python scripts/build_showcase.py
```

This requires FFmpeg on PATH, writes the GIF/still/source metadata under
`docs/media/`, and uses temporary working files under `work/publication/`.
It does not simulate or render new materials.

## Optional fresh CPU renders

The CPU render batch restores the exact release inputs needed for one element
and writes a separate film plus receipts:

```sh
python scripts/rerender_batch.py --kind earth --preflight
python scripts/rerender_batch.py --kind earth --threads 4
```

Valid elements are `fire`, `water`, `earth`, `air`, `ice`, `lava` and `lightning`.
The first command only lists inputs; the second starts the full render. Install
the dependencies from `.github/workflows/rerender.yml` in Python 3.11, or use the
optional workflow. Blender jobs use the genuine `bpy==4.5.3` renderer through
`scripts/blender_python.py`; `--blender` selects a compatible standalone Blender
executable. Fire/air additionally need the CPU PyTorch installation.

Deliveries appear under `work/rerenders/<element>/delivery/` and contain the
film, render diagnostics and a summary with source/input hashes. The recipes
export 720p30 and include full decoding and frame-count checks. A partial or
completed run requires a fresh `--output-root` for that element. Existing current
1080p films remain selected in the player. Inspect the new film before any
deliberate player update. [Pipeline settings](PIPELINES.md#fresh-cpu-rerender-recipes)
document the numerical methods, samples and editorial differences.

For isolated rendering, `.github/workflows/rerender.yml` defines seven parallel
GitHub Actions jobs. A push on `codex/elements-showcase-hardening` starts them
only when the commit message contains `[render-elements]`. The workflow also
defines `workflow_dispatch` for manual invocation when available in GitHub.
Ordinary pushes continue to use the separate repository-check workflow.

Successful job artifacts are named `elements-<element>-<run-id>`. Failed jobs
upload available logs and reports with `diagnostics` in the artifact name.
These render artifacts have **one-day retention**; download the films and
receipts promptly. Check each job's result and delivery receipt before promoting
its film.

## Asset publication

`docs/assets.json` describes the existing published archive. Treat it as release
data: a clean checkout intentionally lacks many files in that inventory. Do
not replace it with an inventory of only the files present in that checkout.

Publication tooling is separate from viewer development and should run only
with complete restored inputs. New inventories are staged under
`work/publication/` so preparing an archive cannot silently change the live
downloader contract. A new version must use a new tag and an existing draft
GitHub release:

```sh
python scripts/fetch_assets.py --all
python scripts/prepare_publication.py --tag v0.2.0
gh release create v0.2.0 --repo cybrdelic/cybr-elements --draft --title "Cybr Elements v0.2.0"
python scripts/publish_assets.py
```

The tag above is an example for a future archive release. Preparation refuses
missing previously released inputs or reuse of the recorded release tag.
Publishing derives its tag/repository from the staged manifest and requires
the release to remain a draft. It verifies remote pack sizes and hashes before
promoting the new manifest and receipts into `docs/`. Public release publication
is a separate maintainer action after review. See [RELEASE.md](RELEASE.md) for
archive scope and run each publication command's `--help` for its options.
