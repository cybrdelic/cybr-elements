"""Static finite-wood donor masses and nearest exterior destinations.

Input is the actual 64^3 RGBA16F SDF asset, never a rendered fire frame.
Coordinates and masses are MODEL metres/kg at objectScale=1. The runtime
applies the structural rigid pose and scale^3. The dynamic fine-fluid kernel
normalizer is authoritative; these nearest exterior centres are not a claim
that one static SDF lookup resolves later fracture collisions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt

DRY_DENSITY_KG_M3 = 495.0
MODEL_SPAN_M = 3.0


def build_metadata(solid: np.ndarray) -> tuple[np.ndarray, dict]:
    if solid.ndim != 4 or solid.shape[-1] != 4 or len(set(solid.shape[:3])) != 1:
        raise ValueError("Expected a cubic z,y,x,RGBA solid field")
    if not np.isfinite(solid).all():
        raise ValueError("Nonfinite SDF/material asset")
    size = solid.shape[0]
    if size < 2:
        raise ValueError("Wood grid must contain at least two cells per axis")
    distance, capacity, material = solid[..., 0], solid[..., 1], solid[..., 3]
    wood = (capacity > 0) & (material > .5) & (material < 2.5) & (distance <= 0)
    foliage = (capacity > 0) & (material > 7.5) & (distance < .07)
    donors = wood | foliage
    # Include inert solids in the search: vapor must not deliberately be
    # placed inside a chimney/metal coating merely because it has no wood mass.
    obstacle = (material < 7.5) & (distance <= 0)
    # Real space outside the asset bounds is air. Padding admits a full-solid
    # boundary cell without an arbitrary clearance offset or nearest edge clamp.
    padded = np.pad(obstacle, 1, mode="constant", constant_values=False)
    indices = distance_transform_edt(padded, return_distances=False,
                                     return_indices=True)[:, 1:-1, 1:-1, 1:-1] - 1
    h = MODEL_SPAN_M / size
    nearest = (indices[::-1].transpose(1, 2, 3, 0) + .5) * h - MODEL_SPAN_M / 2
    positions = nearest.astype("<f4")
    # Foliage is the existing porous lamina proxy, not an impermeable solid.
    # Its own centre is a valid static destination; dynamic normalization still
    # rejects any actual solid occupying its transfer kernel.
    z, y, x = np.indices((size, size, size))
    centres = (np.stack((x, y, z), axis=-1) + .5) * h - MODEL_SPAN_M / 2
    positions[foliage] = centres[foliage]
    metadata = np.zeros((*solid.shape[:3], 4), dtype="<f4")
    metadata[..., :3][donors] = positions[donors]
    # Same dry-capacity convention as woodThermoStep. Do not give the thermal
    # numerical capacity floor (.01) a fictitious donor mass.
    mass = DRY_DENSITY_KG_M3 * np.maximum(capacity, 0) / 1.5 * h ** 3
    metadata[..., 3][donors] = mass[donors]
    stats = {"layout": "nearestExteriorLocalXYZ,initialDryMassKg;RGBA32F z/y/x",
             "size": size, "spanModelM": MODEL_SPAN_M,
             "dryDensityKgM3": DRY_DENSITY_KG_M3,
             "woodDonors": int(wood.sum()), "foliageDonors": int(foliage.sum()),
             "dryMassModelKg": float(metadata[..., 3].sum(dtype=np.float64)),
             "outsideAssetDestinations": int((donors & np.any(np.abs(positions) > 1.5, axis=-1)).sum()),
             "staticDestinationsOnly": True}
    return metadata, stats


def generate(source: Path, output: Path, size: int = 64) -> dict:
    data = source.read_bytes()
    if len(data) != size ** 3 * 8:
        raise ValueError("Invalid RGBA16F solid asset size")
    solid = np.frombuffer(data, dtype="<f2").reshape(size, size, size, 4).astype(np.float32)
    metadata, stats = build_metadata(solid)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = metadata.tobytes(order="C")
    output.write_bytes(payload)
    stats.update({"source": str(source), "sourceSha256": hashlib.sha256(data).hexdigest(),
                  "output": str(output), "bytes": len(payload),
                  "sha256": hashlib.sha256(payload).hexdigest()})
    output.with_suffix(output.suffix + ".json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--object", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.object, args.out), separators=(",", ":")))
