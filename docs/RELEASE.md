# Cybr Elements — 01 / 02 project archive

Seven current 1080p sigil films: fire, water, earth, air, ice, lava and lightning.
The repository includes the current player, films, custom display fonts, source
code and an animated README showcase.

This release carries the larger historical gallery assets, browser mesh caches,
scan textures, geometry and retained research inputs. The ZIPs are independent
asset packs, not split parts of one ZIP. The downloader in the checkout knows
which pack contains each file and verifies both pack and file checksums.

From the checkout:

```sh
python scripts/fetch_assets.py --site
python scripts/fetch_assets.py --all
```

Use `--site` for all historical site media, or `--all` for site media plus research
inputs. Matching files are skipped. The seven current films and typeface page
work without this download. Raw per-frame render/solver caches, local Python
environments, node_modules, logs and compiled GPU caches are not included.

See the README and `docs/PIPELINES.md` for setup, scope, material methods and
limitations. The root GPL v2 license and component notices are retained.
