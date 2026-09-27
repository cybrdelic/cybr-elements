"""Export the approved 02 *static emitter field* for the live fire renderer.

The PNGs contain no rendered video frame or animated simulation cache. They
describe where new gas enters the fluid, when each part of the source opens,
and the launch direction used by the offline reactive-flow solver.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / "work/element-motion/sigil_02_source.py").exists())
NPZ = ROOT / "work/element-motion/sigil-02-v2/source.npz"
ARTWORK = ROOT / "outputs/cybrdelic-type/exploration-v6/cybrdelic-brandmark-refined.png"
OUT_SIZE = (512, 288)  # Existing compact variant; native variant is 896 x 504.
ARRIVAL_MIN = 0.0
ARRIVAL_MAX = 10.0
HALFWIDTH_MAX = 0.27  # metres; offline fire clamps sdf to this before sheet depth


def regenerate() -> dict[str, np.ndarray]:
    """Mirror sigil_02_source.py in memory if its ignored NPZ is unavailable."""
    from scipy.ndimage import distance_transform_edt, gaussian_filter
    from skimage.graph import MCP_Geometric

    art = np.asarray(Image.open(ARTWORK).convert("L"))
    mask = (art[585:1005, 20:1005] < 100).astype("uint8")
    count, labels, stats, centres = cv2.connectedComponentsWithStats(mask)
    for component in range(1, count):
        if stats[component, 4] < 35 or (centres[component, 0] < 85 and centres[component, 1] < 130):
            mask[labels == component] = 0
    yy, xx = np.where(mask)
    mask = mask[yy.min():yy.max() + 1, xx.min():xx.max() + 1]
    height, width = mask.shape
    scale = 8.0 / width
    centre_z = 1.95
    sdf = (distance_transform_edt(mask) - distance_transform_edt(1 - mask)) * scale
    count, labels, _, _ = cv2.connectedComponentsWithStats(mask)
    arrival = np.full(mask.shape, np.nan, np.float64)
    yy_idx, xx_idx = np.indices(mask.shape)
    for component in range(1, count):
        region = labels == component
        _, xs = np.where(region)
        candidates = np.argwhere(region & (xx_idx <= xs.min() + 12))
        root = max(candidates, key=lambda q: sdf[tuple(q)])
        distance, _ = MCP_Geometric(np.where(region, 1.0, np.inf)).find_costs([tuple(root)])
        arrival[region] = root[1] * scale / 2.4 + distance[region] * scale / 3.2
    arrival[mask > 0] = .30 + (arrival[mask > 0] - np.nanmin(arrival)) / (np.nanmax(arrival) - np.nanmin(arrival)) * 3.60
    nearest = distance_transform_edt(1 - mask, return_distances=False, return_indices=True)
    arrival = np.where(mask, arrival, arrival[tuple(nearest)])
    gy, gx = np.gradient(gaussian_filter(arrival, 1.2), scale)
    gz = -gy
    norm = np.maximum(np.hypot(gx, gz), 1e-8)
    gx /= norm
    gz /= norm

    x_count, z_count = 896, 504
    lo = np.array([-7.0, -.6, -1.05])
    extent = np.array([14.0, 1.2, 7.875])
    world_x, world_z = np.meshgrid(
        np.linspace(lo[0], lo[0] + extent[0], x_count),
        np.linspace(lo[2], lo[2] + extent[2], z_count),
    )
    px = (world_x / scale + (width - 1) / 2).astype("f")
    py = ((height - 1) / 2 - (world_z - centre_z) / scale).astype("f")

    def sample(field: np.ndarray, border: float = 0.0) -> np.ndarray:
        return cv2.remap(field.astype("f"), px, py, cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=border)

    distance = sample(sdf, -1)
    dx = extent[0] / (x_count - 1)
    support = np.clip(distance / dx + .5, 0, 1).astype("f")
    return {
        "support": support,
        "sdf": distance,
        "arrival": sample(arrival, 999),
        "dirx": sample(gx),
        "dirz": sample(gz),
        "lo": lo,
        "extent": extent,
    }


def sample_to_output(field: np.ndarray) -> np.ndarray:
    height, width = field.shape
    xs, zs = np.meshgrid(
        np.linspace(0, width - 1, OUT_SIZE[0], dtype="float32"),
        np.linspace(0, height - 1, OUT_SIZE[1], dtype="float32"),
    )
    return cv2.remap(field.astype("float32"), xs, zs, cv2.INTER_LINEAR)


def topology(binary: np.ndarray) -> dict[str, int]:
    binary = binary.astype("uint8").copy()
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary)
    for component in range(1, count):
        if stats[component, 4] < 4:
            binary[labels == component] = 0
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return {"components": 0, "holes": 0}
    return {
        "components": int(np.sum(hierarchy[0, :, 3] < 0)),
        "holes": int(np.sum(hierarchy[0, :, 3] >= 0)),
    }


def encode_unit(field: np.ndarray) -> np.ndarray:
    return np.rint(np.clip(field, 0, 1) * 255).astype("uint8")


def main() -> None:
    if NPZ.exists():
        with np.load(NPZ) as npz:
            fields = {key: npz[key] for key in npz.files}
        origin = "sigil-02-v2/source.npz"
        origin_sha = hashlib.sha256(NPZ.read_bytes()).hexdigest()
    else:
        fields = regenerate()
        origin = "sigil_02_source.py regeneration from approved artwork"
        origin_sha = hashlib.sha256(ARTWORK.read_bytes()).hexdigest()

    support = sample_to_output(fields["support"])
    # The offline NPZ uses 999 only beyond its world-space remap. A direct
    # bilinear downsample could leak that sentinel into edge pixels with real
    # support. Interpolate the valid source separately to retain 0.3–3.9 s.
    valid = (fields["support"] > .01).astype("float32")
    arrival_weight = sample_to_output(valid)
    arrival = sample_to_output(np.where(valid > 0, fields["arrival"], 0)) / np.maximum(arrival_weight, 1e-5)
    arrival = np.where(arrival_weight > 1e-5, arrival, ARRIVAL_MAX)
    dir_x = sample_to_output(fields["dirx"])
    dir_z = sample_to_output(fields["dirz"])
    halfwidth = sample_to_output(np.maximum(fields["sdf"], 0))
    rgba = np.stack([
        encode_unit(support),
        encode_unit((arrival - ARRIVAL_MIN) / (ARRIVAL_MAX - ARRIVAL_MIN)),
        encode_unit((dir_x + 1) * .5),
        encode_unit((dir_z + 1) * .5),
    ], axis=-1)
    Image.fromarray(rgba, "RGBA").save(HERE / "source.png", optimize=True)
    halfwidth_r8 = encode_unit(halfwidth / HALFWIDTH_MAX)
    Image.fromarray(halfwidth_r8, "L").save(HERE / "halfwidth.png", optimize=True)
    (HERE / "source.rgba8.bin").write_bytes(rgba.tobytes(order="C"))
    (HERE / "halfwidth.r8.bin").write_bytes(halfwidth_r8.tobytes(order="C"))

    # Keep the actual offline source resolution for the quality-oriented live
    # renderer. This is the same single static emitter field, with no frames.
    native_support = fields["support"]
    native_valid = native_support > .01
    native_arrival = np.where(native_valid, fields["arrival"], ARRIVAL_MAX)
    native_rgba = np.stack([
        encode_unit(native_support),
        encode_unit((native_arrival - ARRIVAL_MIN) / (ARRIVAL_MAX - ARRIVAL_MIN)),
        encode_unit((fields["dirx"] + 1) * .5),
        encode_unit((fields["dirz"] + 1) * .5),
    ], axis=-1)
    native_halfwidth_r8 = encode_unit(np.maximum(fields["sdf"], 0) / HALFWIDTH_MAX)
    Image.fromarray(native_rgba, "RGBA").save(HERE / "source-native.png", optimize=True)
    Image.fromarray(native_halfwidth_r8, "L").save(HERE / "halfwidth-native.png", optimize=True)
    (HERE / "source-native.rgba8.bin").write_bytes(native_rgba.tobytes(order="C"))
    (HERE / "halfwidth-native.r8.bin").write_bytes(native_halfwidth_r8.tobytes(order="C"))

    source_active = fields["support"] > .5
    packed_active = rgba[..., 0] > 127
    assert topology(source_active) == {"components": 5, "holes": 1}
    assert topology(packed_active) == topology(source_active)
    assert .29 <= float(arrival[packed_active].min()) < float(arrival[packed_active].max()) <= 3.91
    native_packed_active = native_rgba[..., 0] > 127
    # In RGBA8, a source support of exactly .5 rounds to byte 128. Those 38
    # boundary pixels count as active at the byte threshold (>127).
    native_expected_active = native_support >= .5
    assert np.array_equal(native_packed_active, native_expected_active)
    assert .29 <= float(native_arrival[native_packed_active].min()) < float(native_arrival[native_packed_active].max()) <= 3.91
    # Validate shape against direct nearest-neighbour downsampling of the
    # original field, rather than against artwork pixels in another space.
    nearest = cv2.resize(source_active.astype("uint8"), OUT_SIZE, interpolation=cv2.INTER_NEAREST) > 0
    iou = np.count_nonzero(packed_active & nearest) / np.count_nonzero(packed_active | nearest)
    report = {
        "purpose": "Static 02 fuel emitter field for a live reactive-flow simulation; no temporal frames",
        "origin": origin,
        "originSha256": origin_sha,
        "approvedArtworkSha256": hashlib.sha256(ARTWORK.read_bytes()).hexdigest(),
        "preferredVariant": "native",
        "sourceTexture": "source.png",
        "halfwidthTexture": "halfwidth.png",
        "rawTextures": {
            "source": "source.rgba8.bin",
            "halfwidth": "halfwidth.r8.bin",
            "layout": "Row-major, RGBA8 interleaved, first byte is R at x=0,z=lo.z (row 0); upload typed arrays to WebGL for exact unpremultiplied bytes",
        },
        "size": {"x": OUT_SIZE[0], "z": OUT_SIZE[1]},
        "sourceSize": {"x": int(fields["support"].shape[1]), "z": int(fields["support"].shape[0])},
        "native": {
            "size": {"x": int(native_rgba.shape[1]), "z": int(native_rgba.shape[0])},
            "sourceTexture": "source-native.png",
            "halfwidthTexture": "halfwidth-native.png",
            "rawTextures": {"source": "source-native.rgba8.bin", "halfwidth": "halfwidth-native.r8.bin"},
            "orientation": "Row-major, row 0 world z=lo[2], column 0 world x=lo[0]; RGBA8 interleaved source bytes and R8 halfwidth bytes",
            "validation": {
                "topology": topology(native_packed_active),
                "pixelMaskExactVsSourceNpzAtHalfInclusive": bool(np.array_equal(native_packed_active, native_expected_active)),
                "supportPixels": int(np.count_nonzero(native_packed_active)),
                "activeArrivalSeconds": [round(float(native_arrival[native_packed_active].min()), 6), round(float(native_arrival[native_packed_active].max()), 6)],
            },
        },
        "world": {"lo": fields["lo"].tolist(), "extent": fields["extent"].tolist(), "unit": "metres"},
        "orientation": "PNG row 0 maps to world z=lo[2]; column 0 maps to world x=lo[0]. In the shader, sample at uv=((x-lo.x)/extent.x, (z-lo.z)/extent.z) with UNPACK_FLIP_Y_WEBGL=false; verify texture upload orientation if using an image abstraction.",
        "channels": {
            "r": {"name": "support", "decode": "byte/255", "range": [0, 1]},
            "g": {"name": "ignitionArrival", "decode": "byte/255*10", "rangeSeconds": [ARRIVAL_MIN, ARRIVAL_MAX]},
            "b": {"name": "launchDirectionX", "decode": "byte/255*2-1", "range": [-1, 1]},
            "a": {"name": "launchDirectionZ", "decode": "byte/255*2-1", "range": [-1, 1]},
        },
        "halfwidthDecode": "red/255*0.27 metres; feed .028 + .026*sqrt(clamp(halfwidth/.27,0,1))",
        "validation": {
            "nativeTopology": topology(source_active),
            "packedTopology": topology(packed_active),
            "packedVsNearestNativeIoU": round(float(iou), 6),
            "supportPixels": int(np.count_nonzero(packed_active)),
            "activeArrivalSeconds": [round(float(arrival[packed_active].min()), 6), round(float(arrival[packed_active].max()), 6)],
            "filesSha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in ("source.png", "halfwidth.png", "source.rgba8.bin", "halfwidth.r8.bin", "source-native.png", "halfwidth-native.png", "source-native.rgba8.bin", "halfwidth-native.r8.bin")},
            "filesBytes": {name: (HERE / name).stat().st_size for name in ("source.png", "halfwidth.png", "source.rgba8.bin", "halfwidth.r8.bin", "source-native.png", "halfwidth-native.png", "source-native.rgba8.bin", "halfwidth-native.r8.bin")},
        },
    }
    (HERE / "source.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(HERE), "compactSize": OUT_SIZE, "nativeSize": (native_rgba.shape[1], native_rgba.shape[0]), "native": report["native"], "fileBytes": report["validation"]["filesBytes"]}))


if __name__ == "__main__":
    main()
