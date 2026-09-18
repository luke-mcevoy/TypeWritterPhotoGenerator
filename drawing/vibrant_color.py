"""Coherent, saturated ribbon impressions that retain local subject colors.

Color stays on glyphs. A wider fixed ribbon palette includes yellow-green,
and local support replaces global palette voting and whole-region rejection.
"""
import numpy as np
from PIL import Image, ImageFilter

from drawing.layered_color import _regions, layered_underlay
from typewriter_engine import _sobel


RIBBONS = {
    "vermilion": (205, 38, 38),
    "terracotta": (185, 81, 43),
    "gold": (222, 171, 20),
    "leaf_green": (87, 153, 20),
    "green": (27, 126, 49),
    "teal": (15, 134, 133),
    "blue": (24, 93, 190),
    "violet": (112, 44, 172),
    "magenta": (191, 39, 113),
}


def color_plan(source, width, height):
    step = 4
    small = source.convert("RGB").resize(((width+step-1)//step, (height+step-1)//step), Image.Resampling.BOX)
    small = small.filter(ImageFilter.MedianFilter(3))
    hsv = np.asarray(small.convert("HSV"), dtype=np.float32) / 255
    # Source hue centers are separate from the punchier printed pigments.
    # In particular 60–100 degree foliage must not collapse into orange ochre.
    hues = np.array([0, 20, 43, 77, 128, 180, 220, 275, 330], dtype=np.float32) / 360
    delta = np.abs(hsv[:, :, 0, None] - hues)
    labels = np.minimum(delta, 1-delta).argmin(axis=-1).astype(np.int32)
    saturation, value = hsv[:, :, 1], hsv[:, :, 2]
    chroma = saturation * value
    # Dark foliage keeps its hue; weak near-neutral casts and white glints do not.
    confidence = np.clip((saturation-.10)/.30, 0, 1) * np.clip((chroma-.025)/.12, 0, 1)
    confidence *= np.clip((value-.16)/.14, 0, 1)
    labels[confidence < .10] = -1
    ids, regions = _regions(labels, minimum=4)
    labels[ids < 0] = -1
    gray = np.asarray(small.convert("L"), dtype=np.float32) / 255
    smooth = np.asarray(small.convert("L").filter(ImageFilter.GaussianBlur(1.3)), dtype=np.float32) / 255
    gx, gy = _sobel(smooth)
    texture = np.clip(np.abs(gray-smooth)*7, 0, 1)
    return labels, confidence, hsv, gx, gy, texture, step, len(regions)


def vibrant_underlay(source, width, height, paper_rgb, atlas_chars, atlas_masks,
                     amount=1, seed=7, ink_rgb=(28, 22, 18), hatch_amount=.7,
                     progress=None):
    report = progress if callable(progress) else (lambda fraction, label: None)
    # Reuse exactly the same black shadow impressions as Refined color.
    def hatch_progress(fraction, label):
        report(0.5 * float(fraction), label)
    black, meta = layered_underlay(source, width, height, paper_rgb, atlas_chars,
        atlas_masks, amount=0, seed=seed, ink_rgb=ink_rgb, hatch_amount=hatch_amount,
        progress=hatch_progress)
    surface = np.empty((height+24, width+20, 3), dtype=np.float32)
    surface[:] = paper_rgb
    surface[12:height+12, 10:width+10] = black
    amount = float(np.clip(amount, 0, 1))
    if amount == 0:
        return surface[12:height+12, 10:width+10], meta
    labels, confidence, hsv, gx, gy, texture, step, count = color_plan(source, width, height)
    names = list(RIBBONS)
    transmissions = [np.clip(np.asarray(rgb, dtype=np.float32)/paper_rgb, 0, 1) for rgb in RIBBONS.values()]
    families = {"leaf_green": "xo*", "green": "xo*", "gold": "o@%",
                "terracotta": "o=%", "vermilion": "o@%", "teal": "o=+",
                "blue": "o@=", "violet": "o%+", "magenta": "o@%"}
    banks = [[atlas_chars.index(ch) for ch in families[name] if ch in atlas_chars] or [0] for name in names]
    rng = np.random.default_rng(seed+2081)
    strikes, used = [], set()
    rows, cols = labels.shape
    # Three offset feeds build visible color masses from overlapping typed runs.
    # Keys remain upright, and each run follows the local intensity slope.
    report(0.55, "Mixing color · ribbons")
    for layer in range(3):
        report(0.55 + 0.15 * layer, f"Mixing color · pass {layer + 1} of 3")
        for row, y in enumerate(range(12+layer*4, height-12, 13)):
            offset = int(rng.integers(0, 10))
            for start in range(10+offset, width-10, 40):
                cy, cx = min(y//step, rows-1), min(start//step, cols-1)
                slope = float(np.clip(-gx[cy, cx]/(gy[cy, cx]+1e-5), -.25, .25))
                phase = float(rng.uniform(-1, 1))
                for k in range(4):
                    x, py = start+k*10+layer*3, round(y+slope*k*10+phase)
                    if not (10 <= x < width-10 and 12 <= py < height-12):
                        continue
                    sy, sx = py//step, x//step
                    pick = int(labels[sy, sx])
                    if pick < 0:
                        continue
                    name = names[pick]
                    neighbors = labels[max(0, sy-1):min(rows, sy+2), max(0, sx-1):min(cols, sx+2)]
                    supported = neighbors == pick
                    # Adjacent leaf shades belong to one color family; a shadow
                    # or sunlit leaf should not punch a hole in a tree canopy.
                    if name in ("leaf_green", "green"):
                        supported |= (neighbors == 3) | (neighbors == 4)
                    coverage = float(supported.mean())
                    if coverage < .55:
                        continue
                    confidence_here = float(confidence[sy, sx])
                    if layer and confidence_here < (.30 if layer == 1 else .50):
                        continue
                    # Smooth pale areas get a lighter feed; textured colored
                    # objects receive enough impressions to read at page size.
                    value = float(hsv[sy, sx, 2])
                    strength = amount * .96 * np.sqrt(confidence_here) * (.65+.35*coverage)
                    if layer:
                        strength *= .85 if layer == 1 else .70
                    if value > .85 and texture[sy, sx] < .10:
                        strength *= .65
                    if strength < .08:
                        continue
                    bank = banks[pick]
                    index = bank[(row//2 + start//80 + layer) % len(bank)]
                    surface[py:py+24, x:x+20] *= 1-atlas_masks[index, :, :, None]*strength*(1-transmissions[pick])
                    strikes.append((atlas_chars[index], x, py, strength, name))
                    used.add(name)
    report(1.0, "Mixing color…")
    meta.update(ribbons=[name for name in names if name in used], color_strikes=strikes, region_count=count)
    return surface[12:height+12, 10:width+10], meta
