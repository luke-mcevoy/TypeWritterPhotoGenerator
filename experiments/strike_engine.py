"""Experimental renderer: fit the ink that will actually reach the paper.

Kept separate from the production engine for visual A/B review. Uses only the
existing Pillow/NumPy dependencies. No source-photo pixels enter the final page.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from typewriter_engine import CHARSETS, INKS, PAPERS, find_typewriter_font, prepare_luma


def _features(tiles: np.ndarray) -> np.ndarray:
    """Compare tone, coarse shape and fine shape in the same ink units."""
    small = np.stack([
        np.asarray(Image.fromarray(np.asarray(t, dtype=np.float32)).resize((6, 8), Image.Resampling.BOX))
        for t in tiles
    ])
    mean = small.mean(axis=(1, 2))
    centered = small - mean[:, None, None]
    coarse = centered.reshape(-1, 4, 2, 3, 2).mean(axis=(2, 4))
    return np.concatenate([
        centered.reshape(-1, 48) * (0.65 / np.sqrt(48)),
        coarse.reshape(-1, 12) * (0.9 / np.sqrt(12)),
        mean[:, None] * np.sqrt(20),
    ], axis=1).astype(np.float32)


@lru_cache(maxsize=12)
def _bank(charset: str, tightness: float, overstrike: int):
    # One canonical atlas drives matching AND rendering at every export size.
    unit = 2
    w = max(22, round(26 * tightness))
    h = max(32, round(36 * tightness))
    font = find_typewriter_font(16 * unit)
    chars = list(dict.fromkeys(CHARSETS.get(charset, CHARSETS["classic"])))
    singles = []
    for ch in chars:
        tile = Image.new("L", (w, h))
        # Shared vertical origin: punctuation sits on the baseline. The old
        # engine vertically centers every mark independently.
        x = (w - font.getlength(ch)) / 2
        ImageDraw.Draw(tile).text((x, (h - 32) // 2), ch, font=font, fill=255,
                                 stroke_width=1, stroke_fill=255)
        singles.append(np.asarray(tile, dtype=np.float32) / 255)
    tiles = list(singles)
    keys = [(ch, "") for ch in chars]
    if overstrike:
        partners = [i for i, ch in enumerate(chars) if ch in "_-|/\\+=xo@#%&$M8"]
        seen = set()
        for i, a in enumerate(singles):
            if chars[i] == " ":
                continue
            for j in partners:
                pair = tuple(sorted((i, j)))
                if pair in seen:
                    continue
                seen.add(pair)
                b = np.zeros_like(a)
                b[1:, 1:] = singles[j][:-1, :-1]
                # Union, not summed glyph densities: overlapping ink cannot
                # make the paper darker than the ribbon.
                tiles.append(1 - (1 - a) * (1 - b))
                keys.append((chars[i], chars[j]))
    tiles = np.stack(tiles)
    features = _features(tiles)
    return tiles, features, keys, w, h


def _fit(target: np.ndarray, features: np.ndarray, keys: list, seed: int,
         overstrike: int) -> tuple[np.ndarray, np.ndarray]:
    """Bounded batches; choose the whole strike combination and its pressure."""
    norm = (features * features).sum(axis=1)
    penalty = np.array([0.00035 if b else 0 for a, b in keys], dtype=np.float32)
    if overstrike == 1:
        penalty *= 2
    rng = np.random.default_rng(seed)
    selected = np.empty(len(target), np.int32)
    pressure = np.empty(len(target), np.float32)
    # Peak score storage is batch_size × candidate_count, never page × bank.
    for start in range(0, len(target), 128):
        t = target[start:start + 128]
        dot = t @ features.T
        p = np.clip(dot / np.maximum(norm, 1e-9), 0.58, 1.0)
        scores = norm * p * p - 2 * dot * p + penalty
        # Tiny, seeded tie-breaking between nearly equivalent ink patterns.
        # Space is still compared normally and exact white always stays white.
        scores += rng.uniform(0, 0.000025, size=scores.shape).astype(np.float32)
        pick = scores.argmin(axis=1)
        selected[start:start + len(t)] = pick
        pressure[start:start + len(t)] = p[np.arange(len(t)), pick]
    return selected, pressure


class StrikeEngine:
    def convert(self, image: Image.Image, columns: int = 180,
                charset: str = "portrait", paper: str = "cream",
                ink: str = "blue_black", contrast: float = 1.4,
                brightness: float = 0, gamma: float = 1.05,
                detail: float = 0.45, simplify: float = 0.55,
                overstrike: int = 1, tightness: float = 0.90,
                wander: float = 0.7, pressure: float = 0.88,
                scale: int = 2, inscription: str = "", invert: bool = False,
                seed: int = 7, fast: bool = False):
        if inscription:
            raise ValueError("The experimental engine does not yet support inscriptions")
        columns = int(np.clip(columns, 40, 360))
        scale = int(np.clip(scale, 1, 4))
        overstrike = int(np.clip(overstrike, 0, 2))
        # Stable preparation and atlas for preview and print. fast only affects
        # export resolution at the caller, never the drawing's character grid.
        luma = prepare_luma(image, contrast, brightness, gamma, detail,
                            simplify=simplify, max_side=1400, fast=True)
        if invert:
            luma = 1 - luma
        tiles, features, keys, w, h = _bank(charset, round(float(np.clip(tightness, .75, 1.2)), 2), overstrike)
        rows = max(8, round(columns * luma.shape[0] / luma.shape[1] * w / h))
        if rows * columns > 200_000:
            raise ValueError("Image is too tall for this column count")
        target = np.asarray(Image.fromarray(1 - luma, "F").resize(
            (columns * 6, rows * 8), Image.Resampling.BOX))
        target = target.reshape(rows, 8, columns, 6).transpose(0, 2, 1, 3).reshape(-1, 8, 6)
        # Fit within the atlas's printable gamut, retaining relative shades.
        # Rest is a smooth highlight lift, not random deletion after fitting.
        target = np.clip(target, 0, 1) ** (1 + 0.35 * np.clip(simplify, 0, 1))
        capacity = float(tiles.mean(axis=(1, 2)).max()) * 0.95
        target *= capacity * float(np.clip(pressure, 0.1, 1.2))
        chosen, strengths = _fit(_features(target), features, keys, seed, overstrike)

        # Render one row at a time. Avoid page-sized RGB float intermediates
        # and a page × glyph_height × glyph_width tile gather.
        out_w, out_h = max(1, round(w * scale / 2)), max(1, round(h * scale / 2))
        margin = round(1.2 * out_h)
        page_w, page_h = columns * out_w + 2 * margin, rows * out_h + 2 * margin
        if page_w * page_h > 24_000_000:
            raise ValueError("Page exceeds the experimental 24-megapixel limit; reduce columns or scale")
        paper_rgb = np.array(PAPERS.get(paper, PAPERS["cream"]), dtype=np.float32)
        ink_rgb = np.array(INKS.get(ink, INKS["blue_black"]), dtype=np.float32)
        page = Image.new("RGB", (page_w, page_h), tuple(paper_rgb.astype(int)))
        rng = np.random.default_rng(seed + 1)
        chosen = chosen.reshape(rows, columns)
        strengths = strengths.reshape(rows, columns)
        for y in range(rows):
            row = tiles[chosen[y]] * strengths[y, :, None, None]
            mask = row.transpose(1, 0, 2).reshape(h, columns * w)
            mask_im = Image.fromarray((mask * 255).astype(np.uint8)).resize(
                (columns * out_w, out_h), Image.Resampling.LANCZOS)
            # Small ribbon bleed; still composed entirely of the chosen keys.
            blurred = np.asarray(mask_im.filter(ImageFilter.GaussianBlur(.22 * scale)), dtype=np.float32) / 255
            alpha = .85 * np.asarray(mask_im, dtype=np.float32) / 255 + .15 * blurred
            grain = rng.normal(0, .75, size=alpha.shape).astype(np.float32)
            rgb = paper_rgb + grain[:, :, None] - alpha[:, :, None] * (paper_rgb - ink_rgb)
            strip = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
            shift = round(float(np.clip(wander, 0, 1)) * scale * rng.uniform(-.6, .6))
            page.paste(strip, (margin + shift, margin + y * out_h))
        text = "\n".join("".join(keys[i][0] for i in row) for row in chosen)
        return page, {"chars_wide": columns, "chars_tall": rows,
                      "charset": charset, "overstrike": overstrike,
                      "text": text, "html": "", "algorithm": "experimental-strike-fit",
                      "candidate_count": len(keys),
                      "overstrike_cells": sum(bool(keys[i][1]) for i in chosen.flat)}
