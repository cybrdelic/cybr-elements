#!/usr/bin/env python3
"""Solve the retained 300-frame gas trajectory and export selected lossless VDBs."""
import argparse
import os
from pathlib import Path
import runpy
import sys
from render_materials import portable_sources


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--frames', type=int, nargs='+', default=list(range(90, 151, 2)))
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root/'work/element-motion'))
    a.output = a.output.resolve()
    if a.output.exists() and any(a.output.iterdir()):
        p.error('Choose a fresh output directory')
    a.output.mkdir(parents=True, exist_ok=True)
    material = a.output/'materials'
    os.environ.update(CYBR_ELEMENT_SOURCE_ROOT=str(root/'work/element-motion'),
                      CYBR_MATERIAL_DIR=str(material), CYBR_WRITE_VDB='1', OPENBLAS_NUM_THREADS='2')
    _, gas = portable_sources(root/'work/element-motion', a.output/'pipeline')
    chosen = set(a.frames)
    script = gas.read_text().replace("if os.environ.get('CYBR_WRITE_VDB')=='1':",
                                    f"if os.environ.get('CYBR_WRITE_VDB')=='1' and f in {chosen!r}:")
    gas.write_text(script)
    target = material/'lightning/channels.json'; target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((root/'work/element-motion/sigil-02-active-elements/lightning/channels.json').read_bytes())
    original = sys.argv; sys.argv = [str(gas), 'lightning']
    try:
        runpy.run_path(str(gas), run_name='__main__')
    finally:
        sys.argv = original


if __name__ == '__main__':
    main()
