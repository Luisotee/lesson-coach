# /// script
# requires-python = ">=3.12"
# dependencies = ["opencv-python-headless==4.11.0.86", "numpy>=2"]
# ///
"""Draw the transcription eval images: handwriting-like math, with no real photos or people.

Run `uv run evals/transcription/make_images.py`. It is seeded, so the same images come out
each time. Glyphs come from OpenCV's Hershey script stroke font (built in, no font file).
Each glyph gets its own jitter (size, slant, baseline, stroke width), so no two digits are
alike. Fractions can be drawn stacked. Photo-like variants add rotation, perspective, blur,
noise, a paper tint, low contrast and JPEG compression. The ground truth is `truth.yaml`.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
FONT = cv2.FONT_HERSHEY_SCRIPT_SIMPLEX
INK = (60, 45, 30)  # dark blue-grey ink, BGR
PENCIL = (120, 115, 110)


@dataclass
class Frac:
    top: str
    bottom: str


Part = str | Frac
Line = tuple[list[Part], str]  # what is written, and the margin op ("" for none)


@dataclass
class Style:
    scale: float = 1.4
    jitter: float = 0.0  # 0 neat .. 1 messy
    ink: tuple[int, int, int] = INK
    thickness: int = 2
    paper: str = "squared"  # squared | white


def _glyph(canvas: np.ndarray, ch: str, x: int, base: int, st: Style, rng: random.Random) -> int:
    """Draw one character with its own jitter; return the x after it."""
    if ch == " ":
        return x + int(14 * st.scale)
    scale = st.scale * (1 + rng.uniform(-0.12, 0.12) * st.jitter)
    thick = max(1, st.thickness + rng.choice([0, 0, 1] if st.jitter > 0.3 else [0]))
    (w, h), _ = cv2.getTextSize(ch, FONT, scale, thick)
    pad = int(h * 0.8) + 6
    tile = np.zeros((h + 2 * pad, w + 2 * pad), np.uint8)
    cv2.putText(tile, ch, (pad, pad + h), FONT, scale, 255, thick, cv2.LINE_AA)
    angle = rng.uniform(-8, 8) * st.jitter
    m = cv2.getRotationMatrix2D((tile.shape[1] / 2, tile.shape[0] / 2), angle, 1.0)
    tile = cv2.warpAffine(tile, m, (tile.shape[1], tile.shape[0]))
    dy = int(rng.uniform(-5, 5) * st.jitter * st.scale)
    y0, x0 = base - h - pad + dy, x - pad
    _blend(canvas, tile, x0, y0, st.ink)
    return x + w + int(rng.uniform(1, 4 + 4 * st.jitter) * st.scale)


def _blend(canvas: np.ndarray, mask: np.ndarray, x0: int, y0: int, ink: tuple[int, ...]) -> None:
    h, w = mask.shape
    ys, xs = max(0, y0), max(0, x0)
    ye, xe = min(canvas.shape[0], y0 + h), min(canvas.shape[1], x0 + w)
    if ye <= ys or xe <= xs:
        return
    a = mask[ys - y0 : ye - y0, xs - x0 : xe - x0].astype(np.float32)[..., None] / 255
    region = canvas[ys:ye, xs:xe].astype(np.float32)
    canvas[ys:ye, xs:xe] = (region * (1 - a) + np.array(ink, np.float32) * a).astype(np.uint8)


def _text(canvas: np.ndarray, text: str, x: int, base: int, st: Style, rng: random.Random) -> int:
    for ch in text:
        x = _glyph(canvas, ch, x, base, st, rng)
    return x


def _measure(text: str, st: Style) -> int:
    scratch = np.zeros((400, 2000, 3), np.uint8)
    return _text(scratch, text, 0, 200, st, random.Random(0))


def _line(canvas: np.ndarray, line: Line, x: int, base: int, st: Style, rng: random.Random) -> None:
    parts, op = line
    for part in parts:
        if isinstance(part, str):
            x = _text(canvas, part, x, base, st, rng)
            continue
        small = Style(st.scale * 0.75, st.jitter, st.ink, st.thickness, st.paper)
        width = max(_measure(part.top, small), _measure(part.bottom, small))
        mid = base - int(12 * st.scale)
        _text(canvas, part.top, x + (width - _measure(part.top, small)) // 2, mid - 10, small, rng)
        _text(
            canvas,
            part.bottom,
            x + (width - _measure(part.bottom, small)) // 2,
            mid + int(30 * st.scale),
            small,
            rng,
        )
        wobble = int(rng.uniform(-3, 3) * st.jitter)
        cv2.line(
            canvas,
            (x - 3, mid + wobble),
            (x + width + 3, mid - wobble),
            st.ink,
            st.thickness,
            cv2.LINE_AA,
        )
        x += width + int(10 * st.scale)
    if op:
        _text(canvas, f"| {op}", canvas.shape[1] - int(150 * st.scale), base, st, rng)


def page(
    lines: Sequence[Line], st: Style, seed: int, width: int = 900, gap: int = 110
) -> np.ndarray:
    rng = random.Random(seed)
    height = 80 + gap * len(lines)
    canvas = np.full((height, width, 3), 255, np.uint8)
    if st.paper == "squared":
        canvas[:] = (250, 248, 244)
        for i in range(0, max(width, height), 28):
            cv2.line(canvas, (i, 0), (i, height), (235, 215, 200), 1)
            cv2.line(canvas, (0, i), (width, i), (235, 215, 200), 1)
    for i, line in enumerate(lines):
        wave = int(rng.uniform(-8, 8) * st.jitter)
        _line(canvas, line, 50 + int(rng.uniform(0, 20) * st.jitter), 90 + i * gap + wave, st, rng)
    return canvas


def rotate(img: np.ndarray, angle: float) -> np.ndarray:
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    m[0, 2] += nw / 2 - w / 2
    m[1, 2] += nh / 2 - h / 2
    return cv2.warpAffine(img, m, (nw, nh), borderValue=(90, 95, 100))  # a desk behind the page


def photo(
    img: np.ndarray,
    seed: int,
    *,
    blur: int = 3,
    noise: float = 6,
    dim: float = 0.85,
    skew: float = 0.0,
) -> np.ndarray:
    """A phone photo of the page: perspective, uneven light, blur and sensor noise."""
    rng = np.random.default_rng(seed)
    h, w = img.shape[:2]
    if skew:
        d = skew * w
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = np.float32([[d, d * 0.4], [w - d * 0.3, 0], [w, h], [d * 0.2, h - d * 0.2]])
        img = cv2.warpPerspective(
            img, cv2.getPerspectiveTransform(src, dst), (w, h), borderValue=(90, 95, 100)
        )
    light = np.linspace(dim, 1.0, w, dtype=np.float32)[None, :, None]
    out = img.astype(np.float32) * light * np.array([0.93, 0.97, 1.0], np.float32)  # warm tint
    out = cv2.GaussianBlur(out, (blur | 1, blur | 1), 0) if blur else out
    out += rng.normal(0, noise, out.shape).astype(np.float32)
    return np.clip(out, 0, 255).astype(np.uint8)


def low_contrast(img: np.ndarray) -> np.ndarray:
    return (110 + img.astype(np.float32) * (145 / 255)).astype(np.uint8)


def main() -> None:
    neat, messy = Style(jitter=0.2), Style(jitter=0.9, thickness=2)
    two = [(["3x + 5 = 20"], "-5"), (["3x = 15"], "/3"), (["x = 5"], "")]
    images: dict[str, np.ndarray] = {
        "01-clean-sum.png": page([(["3/4 + 1/6"], "")], neat, 1),
        "02-stacked-fraction.png": page([([Frac("5", "8"), " - ", Frac("1", "4")], "")], neat, 2),
        "03-negatives.png": page([(["-7 - (-3)"], "")], neat, 3),
        "04-working-ops.png": page(two, neat, 4),
        "05-messy-working.png": page(
            [(["2x - 4 = 10"], "+4"), (["2x = 14"], "/2"), (["x = 7"], "")], messy, 5
        ),
        "06-rotated.jpg": photo(rotate(page([(["5x + 2 = 3x + 8"], "")], messy, 6), 8), 6),
        "07-sideways.jpg": photo(rotate(page([(["4(x + 1) = 20"], "")], neat, 7), 90), 7),
        "08-dim-skewed.jpg": photo(
            low_contrast(
                page([(["-2 + (-6) = -8"], "")], Style(jitter=0.6, ink=PENCIL, thickness=1), 8)
            ),
            8,
            blur=5,
            noise=9,
            dim=0.6,
            skew=0.08,
        ),
        "09-drawing-board.png": page(
            [([Frac("2", "3"), " * 9 = 6"], "")], Style(jitter=0.7, thickness=3, paper="white"), 9
        ),
        "10-no-math.png": page([(["milk  eggs  bread"], "")], neat, 10),
    }
    for name, img in images.items():
        params = [cv2.IMWRITE_JPEG_QUALITY, 70] if name.endswith(".jpg") else []
        cv2.imwrite(str(HERE / name), img, params)
        print(name, img.shape[1], "x", img.shape[0])


if __name__ == "__main__":
    main()
