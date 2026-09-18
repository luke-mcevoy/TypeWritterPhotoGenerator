"""Guide a full keyboard by shape, surface direction and local character diversity.

Surface direction and connected hue fields guide the keys; these are geometric
cues, not object recognition. All output ink is still a complete upright glyph.
"""
import numpy as np
from PIL import Image, ImageFilter

from drawing.contour_engine import _blur
from drawing.layered_color import _regions
from drawing.vibrant_color import RIBBONS, color_plan
from typewriter_engine import _sobel


def _mean(field, radius):
    """Box average, retaining small signed structure-tensor values."""
    padded = np.pad(field, radius, mode="edge")
    integral = np.pad(padded.cumsum(0, dtype=np.float64).cumsum(1), ((1, 0), (1, 0)))
    side = radius * 2 + 1
    return ((integral[side:, side:] - integral[:-side, side:]
             - integral[side:, :-side] + integral[:-side, :-side]) / side**2).astype(np.float32)


def illustration_plan(source, width, height, simplify=.55, contrast=1.4, shadow_fill=1):
    labels, confidence, hsv, _, _, texture, step, _ = color_plan(source, width, height)
    small = source.convert("L").resize((labels.shape[1], labels.shape[0]), Image.Resampling.BOX)
    gray = np.asarray(small.filter(ImageFilter.MedianFilter(3)), dtype=np.float32) / 255
    gx, gy = _sobel(_blur(gray, .7))
    jxx, jyy, jxy = _mean(gx*gx, 3), _mean(gy*gy, 3), _mean(gx*gy, 3)
    coherence = np.sqrt((jxx-jyy)**2 + 4*jxy*jxy) / (jxx+jyy+1e-6)
    # Tangent to the dominant gradient: keys stay upright; their shapes and
    # carriage feeds, rather than rotated glyph bitmaps, express direction.
    angle = .5 * np.arctan2(2*jxy, jxx-jyy) + np.pi/2
    direction = np.rint(angle / (np.pi/4)).astype(int) % 4
    directional = (coherence > .48) & (jxx+jyy > .002)
    families = np.zeros(labels.shape, np.uint8)
    families[directional] = (direction[directional]+1).astype(np.uint8)
    organic = ((labels == 3) | (labels == 4)) & (coherence < .72)
    families[organic] = 5
    # Regions guide color emphasis; they do not prescribe a repeated character.
    region_labels = np.where(labels == 4, 3, labels) + 1
    ids, regions = _regions(region_labels, minimum=1)
    emphasis = np.ones(labels.shape, np.float32)
    for region in regions:
        yy, xx = region["yy"], region["xx"]
        # Broad pale fields get fewer impressions. This includes smooth sky
        # gradients; small signs/flowers retain their full ribbon.
        open_blue = region["ribbon"] in (6, 7) and region["top"]
        broad_pale = xx.max()-xx.min() > labels.shape[1]*.6
        if ((open_blue or broad_pale) and region["area"] > labels.size*.025
                and float(texture[yy, xx].mean()) < .04
                and float(hsv[yy, xx, 2].mean()) > .76):
            emphasis[yy, xx] = .38
            families[yy, xx] = 6
    colored = confidence * (labels >= 0) * emphasis
    # Open midtones, decisive shadows. Reducing black in chromatic midtones
    # leaves room for the ribbon itself to describe the surface.
    tone = np.clip((.86-gray)/.86, 0, 1)
    shade = .32*tone**1.65 * (1-.78*colored)
    dark = .88 * shadow_fill * np.clip((.48-gray)/.48, 0, 1)**1.05
    local = np.maximum(_blur(gray, 2)-gray, 0)
    shade = np.maximum(shade, dark) + .14*local
    shade *= contrast/1.4 * (1-.3*float(np.clip(simplify, 0, 1)))
    target = np.asarray(Image.fromarray(shade).resize((width, height), Image.Resampling.BILINEAR))
    # Recover fine local shapes after the coarse tone plan: window frames,
    # foliage veins and small features must not disappear into a flat motif.
    fine = np.asarray(source.convert("L").resize((width, height), Image.Resampling.LANCZOS)
                      .filter(ImageFilter.MedianFilter(3)), dtype=np.float32)/255
    detail = np.maximum(_blur(fine, 3)-fine, 0)
    target = target + .30*detail
    slope = np.where(np.abs(np.cos(angle)) > .8, np.clip(np.tan(angle), -.4, .4), 0)
    slope[~directional] = 0
    return dict(labels=labels, confidence=confidence, hsv=hsv, texture=texture, slope=slope, fine=fine,
                families=families, regions=ids, emphasis=emphasis, step=step,
                target=np.clip(target, 0, .78).astype(np.float32))


# Soft preferences only: every key remains available for local shape matching.
FAMILIES = ("", "_-=zEFL", "/vVXAY47", "!ilIHT1[]", "\\vVXAY47", "ocax*O8()36", ".:-,;")


class KeySelector:
    """Favor shape-compatible keys that have not dominated a local patch."""
    def __init__(self, plan, chars, width, height):
        self.plan = plan
        self.preferences = np.array([[1.10 if ch in family else 1 for ch in chars]
                                     for family in FAMILIES], np.float32)
        self.usage = np.zeros(((height+95)//96, (width+95)//96, len(chars)), np.float32)

    def choose(self, improvement, x, y):
        best = float(improvement.max())
        sy = min(y//self.plan["step"], self.plan["labels"].shape[0]-1)
        sx = min(x//self.plan["step"], self.plan["labels"].shape[1]-1)
        family = int(self.plan["families"][sy, sx])
        usage = self.usage[y//96, x//96]
        # Diversity only breaks competition between plausible fits; it cannot
        # substitute a poor key merely to increase the alphabet count.
        score = improvement*self.preferences[family]/(1+.18*usage)
        score[improvement < best*.82] = -np.inf
        index = int(np.argmax(score))
        usage[index] += 1
        return index


def illustrated_underlay(source, width, height, paper_rgb, atlas_chars, atlas_masks,
                         amount=1, seed=7, progress=None, plan=None):
    """Fit varied whole keys to the local color shape, retaining their legibility."""
    report = progress if callable(progress) else (lambda fraction, label: None)
    if plan is None:
        plan = illustration_plan(source, width, height)
    labels, confidence, hsv = (plan[key] for key in ("labels", "confidence", "hsv"))
    names = list(RIBBONS)
    transmissions = [np.clip(np.asarray(rgb, np.float32)/paper_rgb, 0, 1) for rgb in RIBBONS.values()]
    surface = np.empty((height+24, width+20, 3), np.float32)
    surface[:] = paper_rgb
    rng = np.random.default_rng(seed+2081)
    selector = KeySelector(plan, atlas_chars, width, height)
    rows = atlas_masks.reshape(len(atlas_chars), -1)
    rows_sq = rows*rows
    # Full-resolution shape target. Color is still deposited exclusively by
    # glyphs; neither this target nor photograph pixels are composited onto paper.
    density = confidence*(labels >= 0)*(.16+.13*hsv[:, :, 1]+.10*(1-hsv[:, :, 2]))
    target = np.asarray(Image.fromarray(density).resize((width, height), Image.Resampling.BILINEAR))
    target = target + .35*np.maximum(_blur(plan["fine"], 3)-plan["fine"], 0)
    target = np.pad(target, ((12, 12), (10, 10)))
    coverage = np.zeros((height+24, width+20), np.float32)
    strikes, used = [], set()
    if amount <= 0:
        return surface[12:height+12, 10:width+10], dict(ribbons=[], color_strikes=[], hatch_strikes=[])
    for layer, (dx, dy) in enumerate(((0, 0), (5, 8), (2, 4))):
        report(layer/3, f"Typing ribbon patterns · pass {layer+1} of 3")
        for row, y in enumerate(range(12+dy, height-12, 18)):
            shift = int(rng.integers(-1, 2))
            for x in range(10+dx, width-10, 11):
                sy, sx = y//plan["step"], x//plan["step"]
                py = int(round(y+shift+float(plan["slope"][sy, sx])*((x//11 % 6)-2.5)*11))
                if not 12 <= py < height-12:
                    continue
                sy, sx = py//plan["step"], x//plan["step"]
                pick = int(labels[sy, sx])
                if pick < 0:
                    continue
                neighbors = labels[max(0, sy-2):sy+3, max(0, sx-1):sx+2]
                support = (neighbors == pick)
                if pick in (3, 4):
                    support |= (neighbors == 3) | (neighbors == 4)
                if float(support.mean()) < .65:
                    continue
                conf = float(confidence[sy, sx])
                emphasis = float(plan["emphasis"][sy, sx])
                value = float(hsv[sy, sx, 2])
                # Sparse open fields retain a recognizable repeated pattern.
                if emphasis < .5 and ((x//11 + row) % 3 or layer):
                    continue
                if layer == 1 and conf < .6:
                    continue
                if layer == 2 and (conf < .8 or value > .65):
                    continue
                patch = coverage[py:py+24, x:x+20]
                desired = target[py:py+24, x:x+20]
                residual = desired-patch
                mean = float(residual.mean())
                if mean < .012:
                    continue
                headroom = (1-patch).ravel()
                gd = rows @ headroom/480
                dot = rows @ (headroom*residual.ravel())/480 + 5*gd*mean
                norm = rows_sq @ (headroom*headroom)/480 + 5*gd*gd
                strength = np.clip(dot/np.maximum(norm, 1e-8), .65, .98)
                improvement = 2*strength*dot-strength*strength*norm
                if float(improvement.max()) < .0008:
                    continue
                index = selector.choose(improvement, x, py)
                strength = amount*float(strength[index])*np.sqrt(conf)
                patch += (1-patch)*atlas_masks[index]*strength
                surface[py:py+24, x:x+20] *= 1-atlas_masks[index, :, :, None]*strength*(1-transmissions[pick])
                strikes.append((atlas_chars[index], x, py, strength, names[pick]))
                used.add(names[pick])
    report(1, "Finishing ribbon patterns…")
    return surface[12:height+12, 10:width+10], dict(
        ribbons=[name for name in names if name in used], color_strikes=strikes, hatch_strikes=[])
