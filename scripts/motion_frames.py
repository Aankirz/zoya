"""Frame-by-frame check of a motion recording (S2-Feel): finds the pill in every recorded frame
and flags a jump (the pill's bottom-centre anchor moving), a flash (the pill area's brightness
spiking or dipping for one frame) or a theme change mid-run, then writes a contact sheet of
every transition.

    uv run python scripts/motion_frames.py design/s2/recorded/light-daylight

The backdrop is still, so the per-pixel median of the frames is the picture with nothing on
it; whatever differs from it is Zoya's. The bottom edge is left out: a glow around a window
that reaches the screen's bottom draws there.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

SCALE = 2
SAMPLE_FRAMES = 60
DIFF = 18
PILL_BAND_PT = 70
GLOW_EDGE_PT = 7
ANCHOR_PX = 3
FLASH = 12.0
STEP_FRAMES = 6
TILE = "6x8"


def _size(video: Path) -> tuple[int, int]:
    probe = ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries"]
    probe += ["stream=width,height", "-of", "csv=p=0", str(video)]
    width, height = subprocess.run(probe, capture_output=True, text=True, check=True).stdout.split(
        ","
    )
    return int(width) // SCALE, int(height) // SCALE


def frames(video: Path) -> np.ndarray:
    width, height = _size(video)
    command = ["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"scale={width}:{height}"]
    command += ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(command, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, height, width, 3)


def _background(video: np.ndarray) -> np.ndarray:
    picks = np.linspace(0, len(video) - 1, min(SAMPLE_FRAMES, len(video))).astype(int)
    return np.median(video[picks], axis=0)


def _pill(frame: np.ndarray, background: np.ndarray) -> dict | None:
    rows = slice(-PILL_BAND_PT, -GLOW_EDGE_PT)
    band = frame[rows]
    mask = np.abs(band.astype(float) - background[rows]).max(axis=2) > DIFF
    columns, rows = np.where(mask.any(axis=0))[0], np.where(mask.any(axis=1))[0]
    if not len(columns):
        return None
    left, right, bottom = columns[0], columns[-1], rows[-1]
    light = float(band[rows[0] : bottom + 1, left : right + 1].mean())
    return {
        "centre": (left + right) / 2,
        "bottom": int(bottom),
        "width": int(right - left),
        "light": light,
    }


def _issues(pills: list[dict | None], times: list[float]) -> list[str]:
    found = []
    for index in range(1, len(pills) - 1):
        before, now, after = pills[index - 1], pills[index], pills[index + 1]
        if not (before and now and after):
            continue
        at = f"{times[index]:.3f}"
        moved = abs(now["centre"] - before["centre"]) > ANCHOR_PX
        back = abs(after["centre"] - before["centre"]) <= ANCHOR_PX
        if moved and back:
            found.append(
                f"{at} jump: centre {before['centre']} → {now['centre']} → {after['centre']}"
            )
        spike = now["light"] - (before["light"] + after["light"]) / 2
        steady = abs(before["light"] - after["light"]) < FLASH / 2
        if abs(spike) > FLASH and steady:
            found.append(f"{at} flash: brightness {before['light']:.0f} → {now['light']:.0f}")
    return found


def _sheet(video_path: Path, changed: list[int], out: Path) -> None:
    keep = sorted({i for c in changed for i in range(c, c + STEP_FRAMES)})[:48]
    if not keep:
        return
    select = "+".join(f"eq(n\\,{i})" for i in keep)
    command = ["ffmpeg", "-v", "error", "-y", "-i", str(video_path)]
    command += ["-vf", f"select={select},scale=380:-1,tile={TILE}", "-frames:v", "1", str(out)]
    subprocess.run(command, check=True)


def check(folder: Path) -> list[str]:
    video_path = folder / "motion.mp4"
    times = [float(t) for t in (folder / "motion.times").read_text().split()]
    video = frames(video_path)
    background = _background(video)
    pills = [_pill(frame, background) for frame in video]
    issues = _issues(pills, times)
    widths = [p["width"] if p else -1 for p in pills]
    changed = [i for i in range(1, len(widths)) if widths[i] != widths[i - 1]]
    _sheet(video_path, changed[:8], folder / "transitions.png")
    summary = {"frames": len(video), "pill_frames": sum(p is not None for p in pills)}
    summary["issues"] = issues
    (folder / "frames.json").write_text(json.dumps(summary, indent=1))
    return issues


def main() -> int:
    for folder in map(Path, sys.argv[1:]):
        issues = check(folder)
        print(f"{folder.name}: {len(issues)} issues", *issues[:10], sep="\n  ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
