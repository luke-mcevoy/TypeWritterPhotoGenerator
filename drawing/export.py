"""Bounded, high-resolution PNG output from the existing whole-glyph strike plan.

Rasterize the font again at the output size. Horizontal strips keep working
memory independent of the total pixel count; no enlarged preview is used.
"""
import math

import numpy as np
from PIL import Image, ImageDraw

from typewriter_engine import find_typewriter_font


MAX_PIXELS = 12_000_000
MAX_SIDE = 6000
PHONE_SIZES = {"phone_tall": (2160, 4680), "phone_classic": (2160, 3840)}
EXPORT_PROFILES = {"maximum", *PHONE_SIZES}


def output_size(plan_size, profile):
    if profile in PHONE_SIZES:
        return PHONE_SIZES[profile]
    if profile != "maximum":
        raise ValueError("Unknown export size")
    width, height = plan_size
    factor = min(MAX_SIDE/max(width, height), math.sqrt(MAX_PIXELS/(width*height)))
    return max(1, math.floor(width*factor)), max(1, math.floor(height*factor))


def print_plan(meta, paper, ink, profile, fit="contain", progress=None):
    if fit not in ("contain", "cover"):
        raise ValueError("Unknown wallpaper framing")
    width, height = meta["plan_size"]
    margin = max(20, round(width*.035))
    page_size = (width+2*margin, height+2*margin)
    size = output_size(page_size, profile)
    ratio = [size[i]/page_size[i] for i in (0, 1)]
    scale = max(ratio) if profile in PHONE_SIZES and fit == "cover" else min(ratio)
    if scale > 16:
        raise ValueError("Crop closer to the phone shape, or choose Keep whole drawing")
    origin = ((size[0]-page_size[0]*scale)/2+margin*scale,
              (size[1]-page_size[1]*scale)/2+margin*scale)
    clip = (max(0, round(origin[0])), max(0, round(origin[1])),
            min(size[0], round(origin[0]+width*scale)),
            min(size[1], round(origin[1]+height*scale)))
    glyph_size = (max(1, round(20*scale)), max(1, round(24*scale)))
    font = find_typewriter_font(max(1, round(20*scale)))
    glyphs = {}

    def glyph(char):
        if char not in glyphs:
            mask = Image.new("L", glyph_size)
            box = font.getbbox(char)
            ImageDraw.Draw(mask).text(((glyph_size[0]-box[2]+box[0])/2-box[0],
                                      (glyph_size[1]-box[3]+box[1])/2-box[1]),
                                     char, font=font, fill=255)
            glyphs[char] = np.asarray(mask, dtype=np.float32)/255
        return glyphs[char]

    # Each key appears only in the strips it actually touches.
    strip_height = 128
    buckets = [[] for _ in range(math.ceil(size[1]/strip_height))]
    for kind, strikes in (("hatch", meta.get("hatch_strikes", [])),
                           ("color", meta.get("color_strikes", [])),
                           ("black", meta["strikes"])):
        for strike in strikes:
            char, x, y, strength = strike[:4]
            left = round(origin[0]+(x-10)*scale)
            top = round(origin[1]+(y-12)*scale)
            if left >= clip[2] or left+glyph_size[0] <= clip[0]:
                continue
            start, end = max(clip[1], top), min(clip[3], top+glyph_size[1])
            if end <= start:
                continue
            record = (kind, char, left, top, strength, strike[4] if kind == "color" else None)
            for band in range(start//strip_height, (end-1)//strip_height+1):
                buckets[band].append(record)

    if meta["color_mode"] in ("vibrant", "illustrated"):
        from drawing.vibrant_color import RIBBONS
    else:
        from drawing.ribbon_color import RIBBONS
    paper = np.asarray(paper, dtype=np.float32)
    ink = np.asarray(ink, dtype=np.float32)
    transmissions = {name: 1-np.clip(np.asarray(rgb, dtype=np.float32)/paper, 0, 1)
                     for name, rgb in RIBBONS.items()}
    hatch_transmission = 1-np.clip(ink/paper, 0, 1)
    amount = meta["color_amount"]
    page = Image.new("RGB", size, tuple(paper.astype(int)))
    for band, strikes in enumerate(buckets):
        y0 = band*strip_height
        rows = min(strip_height, size[1]-y0)
        mono_base = np.empty((rows, size[0], 3), dtype=np.float32)
        mono_base[:] = paper
        full_base = mono_base.copy()
        black = np.zeros((rows, size[0]), dtype=np.float32)
        for kind, char, left, top, strength, ribbon in strikes:
            x1, x2 = max(clip[0], left), min(clip[2], left+glyph_size[0])
            y1, y2 = max(clip[1], y0, top), min(clip[3], y0+rows, top+glyph_size[1])
            alpha = glyph(char)[y1-top:y2-top, x1-left:x2-left]*strength
            box = (slice(y1-y0, y2-y0), slice(x1, x2))
            if kind == "black":
                patch = black[box]
                patch += (1-patch)*alpha
            elif kind == "hatch":
                transmission = 1-alpha[:, :, None]*hatch_transmission
                mono_base[box] *= transmission
                full_base[box] *= transmission
            else:
                full_base[box] *= 1-alpha[:, :, None]*transmissions[ribbon]
        # Match the existing renderer's lossless 8-bit layer boundaries.
        a = np.clip(black*255, 0, 255).astype(np.uint8).astype(np.float32)[:, :, None]/255
        mono_base = np.clip(mono_base, 0, 255).astype(np.uint8).astype(np.float32)
        full_base = np.clip(full_base, 0, 255).astype(np.uint8).astype(np.float32)
        mono = np.clip(mono_base-a*(mono_base-ink), 0, 255).astype(np.uint8)
        full = np.clip(full_base-a*(full_base-ink), 0, 255).astype(np.uint8)
        rgb = np.rint(mono.astype(np.float32)*(1-amount)+full.astype(np.float32)*amount).astype(np.uint8)
        page.paste(Image.fromarray(rgb), (0, y0))
        if progress:
            progress((band+1)/len(buckets), "Printing high-resolution glyphs…")
    return page
