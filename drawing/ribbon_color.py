"""Selective ribbon color made from glyph impressions beneath black outlines.

The photo chooses ribbon and placement probabilities. Every colored pixel comes
from a glyph mask; no continuous photograph or color wash enters the drawing.
"""

import numpy as np
from PIL import Image, ImageFilter

from typewriter_engine import _sobel


# A deliberately small simulated ribbon collection, not a claim about a
# particular artist's equipment. Hue centers are measured from these colors.
RIBBONS = {
    "ochre": (218, 148, 24),
    "vermilion": (193, 53, 39),
    "blue": (27, 99, 173),
    "green": (48, 125, 64),
    "teal": (26, 127, 132),
    "violet": (128, 65, 145),
}


def _color_fields(source, width, height):
    rgb = source.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    # Smooth color at roughly a key's footprint to avoid photographic speckle.
    smooth = rgb.filter(ImageFilter.GaussianBlur(5))
    hsv = np.asarray(smooth.convert("HSV"), dtype=np.float32) / 255
    gray = np.asarray(rgb.convert("L").filter(ImageFilter.GaussianBlur(2.1)), dtype=np.float32) / 255
    gx, gy = _sobel(gray)
    edge = np.clip(np.hypot(gx, gy) * 3, 0, 1)
    activity = np.asarray(Image.fromarray((edge * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(10)), dtype=np.float32) / 255
    return hsv, activity


def color_underlay(source, width, height, paper_rgb, atlas_chars, atlas_masks,
                   amount=.7, seed=7):
    """Return paper with colored strikes, plus a replayable strike list."""
    amount = float(np.clip(amount, 0, 1))
    surface = np.empty((height + 24, width + 20, 3), dtype=np.float32)
    surface[:] = paper_rgb
    hsv, activity = _color_fields(source, width, height)
    names = list(RIBBONS)
    pigments = np.array(list(RIBBONS.values()), dtype=np.uint8)
    pigment_hue = np.asarray(Image.fromarray(pigments[None, :, :]).convert("HSV"))[0, :, 0] / 255
    # Only retain the three most useful ribbons in this source.
    probe = hsv[::12, ::12]
    hue_delta = np.abs(probe[:, :, 0, None] - pigment_hue)
    distance = np.minimum(hue_delta, 1 - hue_delta)
    nearest = distance.argmin(axis=-1)
    eligible = (probe[:, :, 1] > .25) & (probe[:, :, 2] > .20)
    weights = probe[:, :, 1] * eligible * (.15 + activity[::12, ::12])
    votes = np.bincount(nearest.ravel(), weights=weights.ravel(), minlength=len(names))
    selected = np.argsort(votes)[-3:][::-1]
    selected = selected[votes[selected] > 0]
    if amount == 0 or not len(selected):
        return surface[12:height + 12, 10:width + 10], {"ribbons": [], "color_strikes": []}

    # Related marks repeat in small regions, rather than changing randomly at
    # every pixel. Blue/teal use short horizontal marks; warm colors use loops.
    textures = {"blue": "-=~", "teal": "-=o", "ochre": "o@*",
                "vermilion": "o@%", "green": "x*+", "violet": "o%*"}
    rng = np.random.default_rng(seed + 403)
    stamps = []
    palette_used = set()
    for row, y in enumerate(range(5, height, 8)):
        row_shift = int(rng.integers(0, 8))
        for x0 in range(0, width, 8):
            x = min(width - 1, max(0, x0 + row_shift + int(rng.integers(-2, 3))))
            py = min(height - 1, max(0, y + int(rng.integers(-2, 3))))
            hue, saturation, value = hsv[py, x]
            if saturation < .25 or value < .20:
                continue
            delta = np.abs(pigment_hue[selected] - hue)
            delta = np.minimum(delta, 1 - delta)
            pick = int(selected[delta.argmin()])
            # Do not force a fourth source hue into an unrelated ribbon.
            if float(delta.min()) > .13:
                continue
            probability = amount * saturation * (.025 + 5 * float(activity[py, x]))
            if rng.random() > min(.88, probability):
                continue
            name = names[pick]
            texture = textures[name]
            if name in ("blue", "teal") and activity[py, x] > .10:
                texture = "o@="
            family = [ch for ch in texture if ch in atlas_chars]
            if not family:
                family = [atlas_chars[0]]
            ch = family[(x // 60 + py // 52 + row // 4) % len(family)]
            mask = atlas_masks[atlas_chars.index(ch)]
            strength = float(np.clip(.55 + .38 * saturation + rng.uniform(-.07, .07), .4, .96))
            patch = surface[py:py + 24, x:x + 20]
            alpha = mask[:, :, None] * strength
            # Multiplicative transmission makes overprinted ribbons deepen
            # existing ink. Bare paper is unchanged wherever the key has no ink.
            transmission = np.clip(pigments[pick].astype(np.float32) / paper_rgb, 0, 1)
            patch *= 1 - alpha * (1 - transmission)
            stamps.append((ch, x, py, strength, name))
            palette_used.add(name)
    return surface[12:height + 12, 10:width + 10], {
        "ribbons": [name for name in names if name in palette_used],
        "color_strikes": stamps,
    }
