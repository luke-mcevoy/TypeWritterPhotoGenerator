"""Connected color regions and short runs of overlapping upright characters.

No object recognition or source-pixel blending. Regions are geometric hue
groups; the recorded glyph impressions account for every added ink mark.
"""

from collections import deque

import numpy as np
from PIL import Image, ImageFilter

from drawing.ribbon_color import RIBBONS
from typewriter_engine import _sobel


def _regions(labels, minimum=10):
    """Four-connected components; discard tiny isolated color patches."""
    height, width = labels.shape
    visited = np.zeros(labels.shape, bool)
    ids = np.full(labels.shape, -1, np.int32)
    regions = []
    for y in range(height):
        for x in range(width):
            if visited[y, x] or labels[y, x] < 0:
                continue
            label = int(labels[y, x])
            queue = deque([(y, x)])
            visited[y, x] = True
            points = []
            while queue:
                py, px = queue.popleft()
                points.append((py, px))
                for ny, nx in ((py-1, px), (py+1, px), (py, px-1), (py, px+1)):
                    if 0 <= ny < height and 0 <= nx < width and not visited[ny, nx] and labels[ny, nx] == label:
                        visited[ny, nx] = True
                        queue.append((ny, nx))
            if len(points) >= minimum:
                yy, xx = np.array(points).T
                ids[yy, xx] = len(regions)
                regions.append({"ribbon": label, "area": len(points),
                                "top": bool(np.any(yy == 0)), "yy": yy, "xx": xx})
    return ids, regions


def region_plan(source, width, height):
    """Plan on a coarse grid before printing; suppress weak warm-color noise."""
    step = 6
    small = source.convert("RGB").resize((max(1, (width+step-1)//step),
                                          max(1, (height+step-1)//step)), Image.Resampling.BOX)
    small = small.filter(ImageFilter.MedianFilter(3))
    hsv = np.asarray(small.convert("HSV"), dtype=np.float32) / 255
    colors = np.array(list(RIBBONS.values()), dtype=np.uint8)
    hue = np.asarray(Image.fromarray(colors[None]).convert("HSV"))[0, :, 0] / 255
    delta = np.abs(hsv[:, :, 0, None] - hue)
    distance = np.minimum(delta, 1-delta)
    labels = distance.argmin(axis=-1).astype(np.int32)
    # Low-saturation warm hues are frequently reflected light or skin tones.
    # Require stronger chroma here; this is a palette heuristic, not skin detection.
    warm = (labels == 0) | (labels == 1)
    threshold = np.where(warm, .24, .20)
    strong = hsv[:, :, 1] > np.where(warm, .46, .32)
    eligible = (hsv[:, :, 1] > threshold) & (hsv[:, :, 2] > .19) & (distance.min(axis=-1) < .12)
    # Separate neighboring warm hues before judging a region's saturation:
    # reflected pink/orange light should not absorb an entire ochre garment.
    hue_bins = 48
    labels = labels*hue_bins + np.where(warm, np.floor(hsv[:, :, 0]*hue_bins).astype(np.int32) % hue_bins, 0)
    labels[~eligible] = -1
    ids, regions = _regions(labels, minimum=max(8, labels.size // 2200))
    gray = np.asarray(small.convert("L"), dtype=np.float32) / 255
    smooth = np.asarray(small.convert("L").filter(ImageFilter.GaussianBlur(1.2)), dtype=np.float32) / 255
    gx, gy = _sobel(smooth)
    magnitude = np.clip(np.hypot(gx, gy), 0, 1)
    magnitude = np.asarray(Image.fromarray((magnitude*255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(2)), dtype=np.float32)/255
    texture = np.asarray(Image.fromarray((np.clip(np.abs(gray-smooth)*5, 0, 1)*255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(2)), dtype=np.float32)/255
    votes = np.zeros(len(RIBBONS))
    for region in regions:
        region["ribbon"] //= hue_bins
        yy, xx = region["yy"], region["xx"]
        # Hysteresis: stable strongly colored regions retain their paler parts.
        # Weak regions with only a few colorful outliers are left monochrome.
        region["accepted"] = float(strong[yy, xx].mean()) > (.28 if region["ribbon"] in (0, 1) else .12)
        region["open"] = region["top"] and region["area"] > labels.size * .18
        region["saturation"] = float(hsv[yy, xx, 1].mean())
        score = np.sqrt(region["area"]) * region["saturation"]
        if region["accepted"]:
            votes[region["ribbon"]] += score
    selected = set(np.argsort(votes)[-3:][votes[np.argsort(votes)[-3:]] > 0].tolist())
    return ids, regions, selected, hsv, gray, gx, gy, magnitude, texture, step


def layered_underlay(source, width, height, paper_rgb, atlas_chars, atlas_masks,
                     amount=.7, seed=7, ink_rgb=(28, 22, 18), hatch_amount=.7):
    """Print continuous runs within selected regions, with dark overstrikes."""
    surface = np.empty((height+24, width+20, 3), dtype=np.float32)
    surface[:] = paper_rgb
    amount = float(np.clip(amount, 0, 1))
    hatch_amount = float(np.clip(hatch_amount, 0, 1))
    empty = {"ribbons": [], "color_strikes": [], "hatch_strikes": [], "region_count": 0}
    if amount == 0 and hatch_amount == 0:
        return surface[12:height+12, 10:width+10], empty
    ids, regions, selected, hsv, gray, gx, gy, mag, texture, step = region_plan(source, width, height)
    paint = np.full_like(ids, -1)
    for region in regions:
        if region["accepted"] and region["ribbon"] in selected:
            paint[region["yy"], region["xx"]] = region["ribbon"]
    names = list(RIBBONS)
    rng = np.random.default_rng(seed + 1009)
    strikes = []
    used = set()
    # Runs preserve upright characters while their positions follow a local
    # slope. Rows use controlled feed and carriage offsets rather than random dots.
    for row, y in enumerate(range(8, height-8, 15)):
        offset = int(rng.integers(0, 13))
        for start_x in range(8+offset, width-8, 60):
            cy, cx = min(y//step, ids.shape[0]-1), min(start_x//step, ids.shape[1]-1)
            rid = int(ids[cy, cx])
            if rid < 0:
                continue
            region = regions[rid]
            if not region["accepted"] or region["ribbon"] not in selected:
                continue
            quiet = region["open"] and texture[cy, cx] < .025
            if quiet and (mag[cy, cx] < .055 or rng.random() > .28):
                continue
            name = names[region["ribbon"]]
            # A handful of coherent textures; repeated runs remain readable.
            family = {"ochre": "o@", "vermilion": "o%", "blue": "o@",
                      "green": "x*", "teal": "o=", "violet": "o%"}[name]
            if region["open"]:
                family = "-~="
            available = [ch for ch in family if ch in atlas_chars] or [atlas_chars[0]]
            ch = available[(row//3 + rid) % len(available)]
            glyph = atlas_masks[atlas_chars.index(ch)]
            # Tangent to the local intensity contour, restricted to a gradual
            # carriage slope so upright text stays legible.
            slope = float(np.clip(-gx[cy, cx] / (gy[cy, cx] + 1e-5), -.35, .35)) if mag[cy, cx] > .08 else 0
            phase = float(rng.uniform(-1, 1))
            for k in range(int(rng.integers(2, 4)) if region["open"] else 6):
                x = start_x + k*10
                py = round(y + slope*k*10 + phase)
                if not (10 <= x < width-10 and 12 <= py < height-12):
                    continue
                sy, sx = py//step, x//step
                # Entire keys must fit a stable region. Preserve full letter
                # shapes instead of clipping colored strokes at region edges.
                corners = paint[max(0,(py-7)//step):min(ids.shape[0],(py+8)//step+1),
                                max(0,(x-5)//step):min(ids.shape[1],(x+6)//step+1)]
                if paint[sy, sx] != region["ribbon"] or np.mean(corners == region["ribbon"]) < .85:
                    continue
                dark = float(1-gray[sy, sx])
                sat = float(hsv[sy, sx, 1])
                pressure = float(np.clip(amount*(.64+.34*sat+.22*dark), .1, .96))
                # Saturation alone overstates color in nearly black blue casts.
                # Absolute chroma lets weak reflected color fade continuously.
                chroma = sat * float(hsv[sy, sx, 2])
                pressure *= float(np.clip((chroma-.07)/.16, 0, 1))
                if region["open"]:
                    pressure *= .6
                if pressure < .06:
                    continue
                patch = surface[py:py+24, x:x+20]
                transmission = np.clip(np.array(RIBBONS[name], dtype=np.float32)/paper_rgb, 0, 1)
                patch *= 1-glyph[:, :, None]*pressure*(1-transmission)
                strikes.append((ch, x, py, pressure, name))
                used.add(name)
                # A second, offset pass builds a colored dark mass while
                # preserving the key texture and a stable highlight boundary.
                if dark > .52 and not region["open"]:
                    dy = 5
                    strength = pressure * min(.8, (dark-.38)*1.5)
                    patch = surface[py+dy:py+dy+24, x+2:x+22]
                    patch *= 1-glyph[:, :, None]*strength*(1-transmission)
                    strikes.append((ch, x+2, py+dy, strength, name))
    # Build connected shadow hatching from broad local shade. This adds dark
    # mass around forms without filling a uniformly dark photographic backdrop.
    broad = np.asarray(Image.fromarray((gray*255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(10)), dtype=np.float32)/255
    shadow = np.clip((broad-gray)*2 + (1-gray)*mag*.6, 0, .65)
    hatch_strikes = []
    transmission = np.clip(np.array(ink_rgb, dtype=np.float32)/paper_rgb, 0, 1)
    for row, y in enumerate(range(12, height-12, 14)):
        for start_x in range(12+(row%3)*3, width-12, 50):
            cy, cx = y//step, start_x//step
            if shadow[cy, cx] < .11:
                continue
            sx, sy = float(gx[cy, cx]), float(gy[cy, cx])
            family = "o@"
            if abs(sx) > 2*abs(sy):
                family = "I|"
            elif abs(sy) > 2*abs(sx):
                family = "_="
            available = [ch for ch in family if ch in atlas_chars] or [atlas_chars[0]]
            ch = available[(row//3) % len(available)]
            glyph = atlas_masks[atlas_chars.index(ch)]
            slope = float(np.clip(-sx/(sy+1e-5), -.3, .3))
            for k in range(5):
                x, py = start_x+k*10, round(y+slope*k*10)
                if not (10 <= x < width-10 and 12 <= py < height-12):
                    continue
                value = float(shadow[py//step, x//step])
                if value < .08:
                    continue
                strength = min(.64, value*1.3)*hatch_amount
                if strength <= 0:
                    continue
                surface[py:py+24, x:x+20] *= 1-glyph[:, :, None]*strength*(1-transmission)
                hatch_strikes.append((ch, x, py, strength))
    return surface[12:height+12, 10:width+10], {
        "ribbons": [name for name in names if name in used],
        "color_strikes": strikes, "hatch_strikes": hatch_strikes,
        "region_count": sum(r["accepted"] for r in regions),
    }
