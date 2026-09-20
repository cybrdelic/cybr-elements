"""Verification for the CYBR / ELEMENTS flamethrower reference study.

The checks are deliberately split between numerical/structural invariants and
visual-proxy warnings.  Passing this file does not prove photorealism; it proves
that the delivered movie is complete and that the simulated jet actually
reaches/interacts with the target instead of being composited there afterward.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--video", type=Path, default=None)
    return p.parse_args()


def ffprobe(video: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,nb_frames:format=duration",
        "-of", "json", str(video),
    ]
    return json.loads(subprocess.check_output(cmd, text=True))


def main() -> None:
    a = parse_args()
    report = json.loads(a.report.read_text(encoding="utf-8"))
    video = a.video or Path(report["output"])
    if not video.exists():
        raise SystemExit(f"FAIL: video does not exist: {video}")

    probe = ffprobe(video)
    stream = probe["streams"][0]
    width, height = int(stream["width"]), int(stream["height"])
    expected_w, expected_h = report["resolution"]
    assert [width, height] == [expected_w, expected_h], (width, height, report["resolution"])

    duration = float(probe["format"]["duration"])
    expected_duration = report["frames"] / report["fps"]
    assert abs(duration - expected_duration) < 0.08, (duration, expected_duration)

    frames = int(stream.get("nb_frames") or report["frames"])
    assert abs(frames - report["frames"]) <= 1, (frames, report["frames"])
    assert report["jetReachMaxX"] >= 4.45, report["jetReachMaxX"]
    if report["targetEnabled"]:
        assert report["impactHeatMax"] > 0.10, report["impactHeatMax"]

    assert math.isfinite(report["divergenceRMSMax"])
    assert math.isfinite(report["linearPeakMax"])
    assert report["peakGpuGiB"] > 0

    warnings = []
    if report["divergenceRMSMax"] > 8.0:
        warnings.append(f"high divergence proxy: {report['divergenceRMSMax']:.3f}")
    if report["linearPeakMax"] > 80.0:
        warnings.append(f"very high HDR peak: {report['linearPeakMax']:.2f}")
    if report["impactReactionFractionMax"] < 0.03 and report["targetEnabled"]:
        warnings.append("weak target interaction; inspect impact roll-up")

    result = {
        "status": "pass",
        "video": str(video),
        "resolution": [width, height],
        "frames": frames,
        "duration": duration,
        "jetReachMaxX": report["jetReachMaxX"],
        "impactReactionFractionMax": report["impactReactionFractionMax"],
        "impactHeatMax": report["impactHeatMax"],
        "divergenceRMSMax": report["divergenceRMSMax"],
        "warnings": warnings,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
