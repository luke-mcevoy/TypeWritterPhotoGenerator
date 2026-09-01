"""
Typewriter drawing engine.

A vintage typewriter has about forty-four keys. James Cook builds
drawings by choosing those keys for texture, overlaying strikes for
tone, and varying pressure for shade. This engine does the same
job computationally:

  1. Measure each key's ink footprint (coverage + structure).
  2. Fit a character to every cell of the source (tone + edges).
  3. Overstrike where one key cannot carry the darkness.
  4. Render onto paper with ribbon, wander, and ink bleed.

From a distance the page should read as a drawing. Up close it
must be type. Numbers in the output come from this process, not
from decoration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = os.path.dirname(os.path.abspath(__file__))

TYPEWRITER_FONT_CANDIDATES = [
    os.path.join(ROOT, "fonts", "SpecialElite-Regular.ttf"),
    "/System/Library/Fonts/Supplemental/Courier New.ttf",
    "/Library/Fonts/Courier New.ttf",
    "/System/Library/Fonts/Supplemental/AmericanTypewriter.ttc",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "C:/Windows/Fonts/cour.ttf",
]

# Forty-four-ish vintage keyboard, grouped by the textures Cook describes.
# @  — soft shade (large ink area)
# () — small curves (pupils, arches)
# I_ — masonry, mullions, horizon lines
# #%&$WM — the darkest single strikes
CHARSETS = {
    "classic": (
        " .,'-`:;\"^~_!|iIl1tfjrxcunvzoaes"
        "<>+=*?/\\()[]{}#@$%&WM80"
        "ABCDEFGHJKLNOPQRSTUVXYZ"
        "2345679"
    ),
    "portrait": (
        " .,'`:;~-_"
        "ocO0()@*+=#&%$'\"!"
        "ilI1tfjrsnm"
        "aeu"
    ),
    "architecture": (
        " .,'-_`:"
        "Iil1|!/\\-_=[]{}()#"
        "HFEELT"
        "oO0@%&$WM"
        "+=*"
    ),
    "heavy": (
        " .,'-:"
        "@#%&$WM8HXB"
        "ocO0()[]{}"
        "Iil1|/\\-_="
        "*+aesnm"
    ),
    "scene": (
        " .,'-`:"
        "_-=I|!/\\"
        "ocO0()@*%#&$"
        "nm*"
    ),
}

# Glyphs that follow a direction. Cook uses I for mullions, _ for brick,
# () for small curves — not the same key for every texture.
VERT_MARKS = set("Iil1|![]HFTL")
HORIZ_MARKS = set("-_=.~")
ROUND_MARKS = set("ocO0()@*%")

PAPERS = {
    "cream": (246, 236, 214),
    "ivory": (240, 227, 200),
    "white": (248, 246, 240),
    "aged": (226, 208, 176),
}

INKS = {
    "carbon": (28, 22, 18),
    "blue_black": (18, 28, 42),
    "navy": (16, 24, 48),
    "sepia": (52, 34, 22),
}

MATCH_W, MATCH_H = 6, 8
_BANK_CACHE: dict[tuple, "GlyphBank"] = {}


def find_typewriter_font(size: int) -> ImageFont.FreeTypeFont:
    for path in TYPEWRITER_FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _sobel(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """3×3 Sobel via sliding windows. arr is 2D float."""
    kx = np.array([[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]])
    ky = kx.T
    padded = np.pad(arr, 1, mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(padded, (3, 3))
    gx = np.einsum("ijkl,kl->ij", windows, kx)
    gy = np.einsum("ijkl,kl->ij", windows, ky)
    return gx, gy


def _auto_contrast(arr: np.ndarray, cutoff: float = 0.6) -> np.ndarray:
    lo, hi = np.percentile(arr, [cutoff, 100.0 - cutoff])
    if hi - lo < 1e-4:
        return arr
    return np.clip((arr - lo) / (hi - lo), 0.0, 1.0)


def simplify_drawing(arr: np.ndarray, amount: float, fast: bool = False) -> np.ndarray:
    """
    Flatten photographic grain; keep silhouettes.

    A typewriter drawing is not a photocopy. Cobblestones, foliage
    glitter, and sensor noise should collapse to mass. Edges that
    would actually be drawn — a lamp post, a bird, a jaw — stay.
    """
    if amount <= 0.02:
        return arr
    amount = float(np.clip(amount, 0.0, 1.0))
    im = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), "L")
    if fast:
        radius = max(1.2, min(arr.shape) / 90.0 * (0.4 + 0.8 * amount))
        mass = np.asarray(
            im.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32
        ) / 255.0
        gx, gy = _sobel(mass)
        mag = np.hypot(gx, gy)
        hi = np.percentile(mag, 90)
        edge = np.clip(mag / (hi + 1e-6), 0.0, 1.0) ** 1.15
        drawn = mass * (1.0 - edge) + arr * edge
        return np.clip((1.0 - amount) * arr + amount * drawn, 0.0, 1.0).astype(np.float32)

    med = np.asarray(im.filter(ImageFilter.MedianFilter(size=5)), dtype=np.float32) / 255.0
    radius = max(1.8, min(arr.shape) / 75.0 * (0.45 + 0.85 * amount))
    mass = np.asarray(
        Image.fromarray((med * 255).astype(np.uint8), "L").filter(
            ImageFilter.GaussianBlur(radius=radius)
        ),
        dtype=np.float32,
    ) / 255.0
    gx, gy = _sobel(med)
    mag = np.hypot(gx, gy)
    hi = np.percentile(mag, 90)
    edge = np.clip(mag / (hi + 1e-6), 0.0, 1.0) ** 1.15
    drawn = mass * (1.0 - edge) + med * edge
    # Soft posterize so tone reads as a value study, not a photo.
    levels = 7.0
    poster = np.round(drawn * (levels - 1.0)) / (levels - 1.0)
    drawn = 0.62 * drawn + 0.38 * poster
    return np.clip((1.0 - amount) * arr + amount * drawn, 0.0, 1.0).astype(np.float32)


def prepare_luma(
    image: Image.Image,
    contrast: float = 1.25,
    brightness: float = 0.0,
    gamma: float = 1.05,
    detail: float = 0.55,
    simplify: float = 0.55,
    max_side: int = 1200,
    fast: bool = False,
) -> np.ndarray:
    """Return paper-white=1, ink-needed=0 luma in [0, 1]."""
    gray = ImageOps.exif_transpose(image).convert("L")
    if max(gray.size) > max_side:
        gray = gray.copy()
        gray.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
    arr = np.asarray(gray, dtype=np.float32) / 255.0
    arr = _auto_contrast(arr)
    arr = simplify_drawing(arr, simplify, fast=fast)

    if abs(brightness) > 1e-6:
        arr = np.clip(arr + brightness, 0.0, 1.0)
    if abs(contrast - 1.0) > 1e-6:
        arr = np.clip((arr - 0.5) * contrast + 0.5, 0.0, 1.0)
    if abs(gamma - 1.0) > 1e-6:
        arr = np.clip(arr, 1e-6, 1.0) ** gamma

    # Open lights (pavement, sky, skin highlight) so the page can rest.
    lift = np.clip(arr, 0.0, 1.0) ** 0.88
    arr = 0.55 * arr + 0.45 * lift
    arr = np.clip((arr - 0.5) * 1.06 + 0.5, 0.0, 1.0)

    if detail > 0:
        src = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), "L")
        blur = np.asarray(
            src.filter(ImageFilter.GaussianBlur(radius=1.2 if fast else 1.4)), dtype=np.float32
        ) / 255.0
        arr = np.clip(arr + detail * 0.65 * (arr - blur), 0.0, 1.0)

    return arr.astype(np.float32)


@dataclass
class Glyph:
    char: str
    ink: np.ndarray  # (h, w) in [0, 1], 1 = full ribbon
    density: float
    gx: float
    gy: float
    edge: float


class GlyphBank:
    def __init__(self, charset: str, font: ImageFont.ImageFont, cell_w: int, cell_h: int):
        self.cell_w = cell_w
        self.cell_h = cell_h
        self.glyphs: list[Glyph] = []
        seen: set[str] = set()
        for ch in charset:
            if ch in seen:
                continue
            seen.add(ch)
            glyph = self._measure(ch, font)
            if glyph is None:
                continue
            self.glyphs.append(glyph)

        if not self.glyphs:
            raise RuntimeError("No renderable typewriter characters in charset")

        self.chars = [g.char for g in self.glyphs]
        self.ink = np.stack([g.ink for g in self.glyphs], axis=0)  # (N, h, w)
        self.density = np.array([g.density for g in self.glyphs], dtype=np.float32)
        self.orient = np.array([[g.gx, g.gy] for g in self.glyphs], dtype=np.float32)
        self.edge = np.array([g.edge for g in self.glyphs], dtype=np.float32)
        self.flat = self.ink.reshape(len(self.glyphs), -1)
        match = np.stack(
            [
                np.asarray(
                    Image.fromarray((g.ink * 255).astype(np.uint8), "L").resize(
                        (MATCH_W, MATCH_H), Image.Resampling.BILINEAR
                    ),
                    dtype=np.float32,
                )
                / 255.0
                for g in self.glyphs
            ],
            axis=0,
        )
        self.match_flat = match.reshape(len(self.glyphs), -1)
        self._tiles: dict[tuple[int, int, int], np.ndarray] = {}

        # Space is always index 0 if present; otherwise the lightest glyph.
        if " " in self.chars:
            self.space_index = self.chars.index(" ")
        else:
            self.space_index = int(np.argmin(self.density))

    def tiles(self, cell_w: int, cell_h: int, font_size: int) -> np.ndarray:
        key = (cell_w, cell_h, font_size)
        cached = self._tiles.get(key)
        if cached is not None:
            return cached
        font = find_typewriter_font(font_size)
        out = np.zeros((len(self.chars), cell_h, cell_w), dtype=np.float32)
        for i, ch in enumerate(self.chars):
            if ch == " ":
                continue
            img = Image.new("L", (cell_w, cell_h), 0)
            draw = ImageDraw.Draw(img)
            bbox = font.getbbox(ch)
            x = (cell_w - (bbox[2] - bbox[0])) // 2 - bbox[0]
            y = (cell_h - (bbox[3] - bbox[1])) // 2 - bbox[1]
            draw.text((x, y), ch, font=font, fill=255)
            out[i] = np.asarray(img, dtype=np.float32) / 255.0
        self._tiles[key] = out
        return out

    def _measure(self, ch: str, font: ImageFont.ImageFont) -> Glyph | None:
        img = Image.new("L", (self.cell_w, self.cell_h), 255)
        draw = ImageDraw.Draw(img)
        bbox = font.getbbox(ch)
        gw = bbox[2] - bbox[0]
        gh = bbox[3] - bbox[1]
        x = (self.cell_w - gw) // 2 - bbox[0]
        y = (self.cell_h - gh) // 2 - bbox[1]
        draw.text((x, y), ch, font=font, fill=0)
        bits = 1.0 - np.asarray(img, dtype=np.float32) / 255.0
        density = float(bits.mean())
        if ch != " " and density < 1e-4:
            return None
        gx, gy = _sobel(bits)
        mag = np.hypot(gx, gy)
        edge = float(mag.mean())
        if edge > 1e-6:
            ox = float((gx * mag).sum() / mag.sum())
            oy = float((gy * mag).sum() / mag.sum())
        else:
            ox = oy = 0.0
        return Glyph(ch, bits, density, ox, oy, edge)


def _cell_grid(arr: np.ndarray, rows: int, cols: int, gh: int, gw: int) -> np.ndarray:
    """Resample to (rows, cols, gh, gw) for per-cell matching."""
    hi = np.array(
        Image.fromarray((arr * 255).astype(np.uint8), mode="L").resize(
            (cols * gw, rows * gh), Image.Resampling.BILINEAR
        ),
        dtype=np.float32,
    ) / 255.0
    return hi.reshape(rows, gh, cols, gw).transpose(0, 2, 1, 3)


def _box_downsample(arr: np.ndarray, cols: int, rows: int) -> np.ndarray:
    """Mean-pool a 2D array to (rows, cols)."""
    im = Image.fromarray(np.ascontiguousarray(arr, dtype=np.float32), "F")
    return np.asarray(im.resize((cols, rows), Image.Resampling.BOX), dtype=np.float32)


def _cell_gradients(luma: np.ndarray, rows: int, cols: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # Structure at drawing scale, not the grain of unsharp-masking.
    radius = max(1.1, min(luma.shape) / 220.0)
    im = Image.fromarray((np.clip(luma, 0, 1) * 255).astype(np.uint8), "L")
    smooth = np.asarray(im.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32) / 255.0
    gx, gy = _sobel(smooth)
    mag = np.hypot(gx, gy)
    return (
        _box_downsample(gx, cols, rows),
        _box_downsample(gy, cols, rows),
        _box_downsample(mag, cols, rows),
    )


def assign_keys(
    luma: np.ndarray,
    bank: GlyphBank,
    rows: int,
    cols: int,
    overstrike: int = 1,
    rest: float = 0.45,
    seed: int = 7,
    fast: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Pick a primary key and an optional overstrike key per cell.

    Target ink = 1 - luma. Matching is squared error on the glyph
    bitmap, plus a density term (so skies stay open) and an
    orientation term (so I, _, / follow structure). Residual
    darkness after the first strike is Floyd–Steinberg diffused,
    then spent on a second key if overstrike >= 1.
    """
    cells = _cell_grid(luma, rows, cols, MATCH_H, MATCH_W)
    # cells are paper-white; convert to ink-needed
    target = 1.0 - cells
    target_flat = target.reshape(rows * cols, -1).astype(np.float32)
    target_mean = target_flat.mean(axis=1)

    G = bank.match_flat.astype(np.float32)  # (N, P)

    # Split tone from structure. A typewriter key only inks ~10–40% of its
    # cell, so comparing raw darkness to a near-black patch would reject
    # every glyph. Match zero-mean pattern (NCC) and density separately.
    t_center = target_flat - target_mean[:, None]
    g_center = G - bank.density[:, None]
    t_norm = np.sqrt((t_center ** 2).sum(axis=1, keepdims=True)) + 1e-4
    g_norm = np.sqrt((g_center ** 2).sum(axis=1, keepdims=True)) + 1e-4
    ncc = (t_center @ g_center.T) / (t_norm * g_norm.T)
    structure = 1.0 - ncc  # 0 = identical hatch

    tone_target = target_mean * float(bank.density.max())
    density_err = (tone_target[:, None] - bank.density[None, :]) ** 2

    gx, gy, mag = _cell_gradients(luma, rows, cols)
    mag = np.nan_to_num(mag, nan=0.0)
    mag_n = mag / (float(np.percentile(mag, 98)) + 1e-6)
    mag_n = np.clip(mag_n, 0.0, 1.0)
    gx_f = np.nan_to_num(gx).reshape(-1)
    gy_f = np.nan_to_num(gy).reshape(-1)
    cell_orient = np.stack([gx_f, gy_f], axis=1)
    cell_norm = np.sqrt((cell_orient ** 2).sum(axis=1, keepdims=True)) + 1e-6
    cell_orient = cell_orient / cell_norm
    glyph_norm = np.sqrt((bank.orient ** 2).sum(axis=1, keepdims=True)) + 1e-6
    glyph_orient = bank.orient / glyph_norm
    alignment = 1.0 - np.abs(cell_orient @ glyph_orient.T)
    orient_term = (mag_n.reshape(-1, 1) ** 1.15) * alignment

    # Prefer keys whose shape matches the local axis: I on a lamp post,
    # _ on a kerb, o/@ in foliage.
    vert_idx = np.array([i for i, ch in enumerate(bank.chars) if ch in VERT_MARKS], dtype=np.int32)
    horiz_idx = np.array([i for i, ch in enumerate(bank.chars) if ch in HORIZ_MARKS], dtype=np.int32)
    round_idx = np.array([i for i, ch in enumerate(bank.chars) if ch in ROUND_MARKS], dtype=np.int32)
    abs_gx = np.abs(gx_f)
    abs_gy = np.abs(gy_f)
    axis = abs_gx + abs_gy + 1e-6
    vertness = (mag_n.reshape(-1) * np.clip(abs_gx - abs_gy, 0, None) / axis)
    horizness = (mag_n.reshape(-1) * np.clip(abs_gy - abs_gx, 0, None) / axis)
    roundness = mag_n.reshape(-1) * (1.0 - np.abs(abs_gx - abs_gy) / axis) * 0.65

    axis_bias = np.zeros_like(alignment)
    if len(vert_idx):
        axis_bias[:, vert_idx] -= 0.55 * vertness[:, None]
        axis_bias[:, vert_idx] += 0.28 * horizness[:, None]
    if len(horiz_idx):
        axis_bias[:, horiz_idx] -= 0.55 * horizness[:, None]
        axis_bias[:, horiz_idx] += 0.28 * vertness[:, None]
    if len(round_idx):
        axis_bias[:, round_idx] -= 0.22 * roundness[:, None]

    scores = 0.62 * structure + 1.05 * density_err + 0.42 * orient_term + axis_bias
    scores = np.nan_to_num(scores, nan=1e6, posinf=1e6, neginf=1e6)

    # Open paper: sunlit ground and sky should be rest, not a screen of keys.
    light = target_mean < (0.09 + 0.06 * rest)
    scores[light] = 1e6
    scores[light, bank.space_index] = 0.0

    # Soft shade: on a cheek or sky, vertical I/l/1 look like scratches.
    # Restrict low-edge lights and midtones to punctuation and round
    # marks — the same keys Cook uses for tone rather than structure.
    scratch = set("Iil1tfj|/\\![]{}HFEELT")
    scratch_idx = np.array(
        [i for i, ch in enumerate(bank.chars) if ch in scratch], dtype=np.int32
    )
    if len(scratch_idx) > 0:
        low_edge = mag_n.reshape(-1) < 0.32
        skin = low_edge & (target_mean < 0.40) & (target_mean >= 0.06)
        if np.any(skin):
            scores[np.ix_(np.flatnonzero(skin), scratch_idx)] = 1e6

    primary = np.argmin(scores, axis=1).astype(np.int32)

    if not fast:
        # Error diffusion on leftover ink so midtones do not band.
        leftover = (tone_target - bank.density[primary]).reshape(rows, cols)
        diffused = leftover.copy()
        for y in range(rows):
            for x in range(cols):
                err = diffused[y, x]
                if x + 1 < cols:
                    diffused[y, x + 1] += err * 0.4375
                if y + 1 < rows:
                    if x > 0:
                        diffused[y + 1, x - 1] += err * 0.1875
                    diffused[y + 1, x] += err * 0.3125
                    if x + 1 < cols:
                        diffused[y + 1, x + 1] += err * 0.0625

        needed = diffused.reshape(-1)
        bump = needed > 0.02
        if np.any(bump):
            denser = scores.copy()
            denser += 2.4 * np.clip(
                bank.density[None, :] - (tone_target + needed)[:, None], 0, None
            )
            too_light = bank.density[None, :] < (bank.density[primary][:, None] + 0.008)
            denser[too_light] += 0.4
            alt = np.argmin(denser, axis=1).astype(np.int32)
            primary = np.where(bump, alt, primary)

    over = np.full_like(primary, -1)
    if overstrike >= 1:
        # Only the wells get a second key. Midtones stay a single
        # strike so faces do not fill in like the background.
        strike = target_mean > (0.48 if overstrike == 1 else 0.38)
        if np.any(strike):
            dense_scores = scores.copy()
            dense_scores -= 1.4 * bank.density[None, :]
            dense_scores[:, bank.space_index] = 1e6
            dense_scores += 0.8 * (bank.density[None, :] < 0.05)
            over_pick = np.argmin(dense_scores, axis=1).astype(np.int32)
            over = np.where(strike, over_pick, over)

        if overstrike >= 2:
            very = target_mean > 0.62
            if np.any(very):
                darkest = int(np.argmax(bank.density))
                over = np.where(very, darkest, over)

    rng = np.random.RandomState(seed)
    # Break wallpaper in flat shade so a field of @ does not read as a screen.
    flat_shade = mag_n.reshape(-1) < 0.22
    if np.any(flat_shade):
        k = min(5, scores.shape[1])
        top = np.argpartition(scores[flat_shade], kth=k - 1, axis=1)[:, :k]
        choice = rng.randint(0, k, size=int(flat_shade.sum()))
        primary[flat_shade] = top[np.arange(top.shape[0]), choice]

    # Rest: skip keys in quiet midtones. Cook does not type every
    # cobblestone; he suggests the street and draws the bird.
    if rest > 0.02:
        flat = mag_n.reshape(-1) < 0.20
        keep_p = np.clip(target_mean ** (0.75 + 0.6 * rest), 0.05, 1.0)
        keep_p = np.where(target_mean < 0.28, keep_p * (0.25 + 0.4 * (1.0 - rest)), keep_p)
        skip = flat & (rng.rand(target_mean.size) > keep_p)
        # Never skip a strong edge or a true well.
        skip &= mag_n.reshape(-1) < 0.28
        skip &= target_mean < 0.72
        primary[skip] = bank.space_index
        over[skip] = -1

    return primary.reshape(rows, cols), over.reshape(rows, cols)


def inscribe_text(primary: np.ndarray, bank: GlyphBank, text: str, luma_cells: np.ndarray) -> np.ndarray:
    """
    Weave `text` through mid-tone cells, only where the letter's
    density is close to the cell's — the way Cook hides names in
    masonry and crowd-shade without punching holes.
    """
    if not text:
        return primary
    message = "".join(ch if ch in bank.chars else " " for ch in text)
    if not message.strip():
        return primary
    char_to_idx = {c: i for i, c in enumerate(bank.chars)}
    rows, cols = primary.shape
    ink_needed = 1.0 - luma_cells
    out = primary.copy()
    mi = 0
    eligible = 0
    placed = 0
    budget = max(len(message) * 8, 48)
    for y in range(rows):
        for x in range(cols):
            ch = message[mi % len(message)]
            if ch not in char_to_idx:
                continue
            idx = char_to_idx[ch]
            cell_d = float(ink_needed[y, x])
            glyph_d = float(bank.density[idx])
            if 0.08 < cell_d < 0.82 and abs(cell_d - glyph_d) < 0.28:
                eligible += 1
                if eligible % 3 != 0:
                    continue
                out[y, x] = idx
                mi += 1
                placed += 1
                if placed >= budget:
                    return out
            elif ch == " ":
                mi += 1
    return out


def _paper_texture(h: int, w: int, color: tuple[int, int, int], seed: int) -> np.ndarray:
    rng = np.random.RandomState(seed)
    paper = np.zeros((h, w, 3), dtype=np.float32)
    paper[:] = np.array(color, dtype=np.float32)
    grain = rng.randn(h, w).astype(np.float32)
    # Fine tooth of laid paper.
    paper += grain[:, :, None] * 3.4
    # Longer fibres.
    fibre = rng.randn(max(1, h // 3), max(1, w // 3)).astype(np.float32)
    fibre = np.array(
        Image.fromarray(fibre, mode="F").resize((w, h), Image.Resampling.BILINEAR)
    )
    paper += fibre[:, :, None] * 2.2
    return np.clip(paper, 0, 255)


def render_page(
    primary: np.ndarray,
    over: np.ndarray,
    bank: GlyphBank,
    font: ImageFont.ImageFont,
    paper_color: tuple[int, int, int],
    ink_color: tuple[int, int, int],
    luma: np.ndarray,
    tightness: float = 0.90,
    wander: float = 0.65,
    pressure: float = 0.85,
    scale: int = 2,
    seed: int = 7,
    fast: bool = False,
) -> Image.Image:
    """Assemble the page from glyph tiles."""
    rows, cols = primary.shape
    look = 0.72 if fast else 1.0
    font_size = max(8, int(getattr(font, "size", 16) * scale))
    t = tightness * look
    cell_w = max(4, int(round(bank.cell_w * t * scale)))
    cell_h = max(5, int(round(bank.cell_h * t * scale)))
    tiles = bank.tiles(cell_w, cell_h, font_size)

    body = tiles[primary].transpose(0, 2, 1, 3).reshape(rows * cell_h, cols * cell_w)

    small_luma = np.array(
        Image.fromarray((np.clip(luma, 0, 1) * 255).astype(np.uint8), "L").resize(
            (cols, rows), Image.Resampling.BILINEAR
        ),
        dtype=np.float32,
    ) / 255.0
    local_ink = 1.0 - small_luma
    weight = np.clip(pressure * (0.58 + 0.55 * local_ink), 0.18, 1.0)
    body = np.clip(body * np.repeat(np.repeat(weight, cell_h, axis=0), cell_w, axis=1), 0.0, 1.0)

    has_over = over >= 0
    if np.any(has_over):
        ov_idx = np.where(has_over, over, 0)
        ov_body = tiles[ov_idx].transpose(0, 2, 1, 3).reshape(rows * cell_h, cols * cell_w)
        ov_mask = np.repeat(np.repeat(has_over.astype(np.float32), cell_h, axis=0), cell_w, axis=1)
        shifted = np.zeros_like(ov_body)
        src = ov_body * ov_mask
        if fast:
            shifted[:, 1:] = src[:, :-1]
        else:
            shifted[1:, 2:] = src[:-1, :-2]
        body = np.clip(body + shifted * 0.82, 0.0, 1.0)

    if wander > 0.25 and not fast:
        rng = np.random.RandomState(seed + 1)
        for r in range(rows):
            shift = int(rng.randint(-1, 2))
            if shift:
                y0, y1 = r * cell_h, (r + 1) * cell_h
                body[y0:y1] = np.roll(body[y0:y1], shift, axis=1)

    margin = max(16, int(1.2 * cell_h))
    page_h = body.shape[0] + 2 * margin
    page_w = body.shape[1] + 2 * margin
    paper = np.empty((page_h, page_w, 3), dtype=np.float32)
    paper[:] = np.array(paper_color, dtype=np.float32)
    rng = np.random.RandomState(seed)
    step = 4 if fast else 2
    grain = rng.randn(max(1, page_h // step), max(1, page_w // step)).astype(np.float32)
    grain = np.asarray(Image.fromarray(grain, mode="F").resize((page_w, page_h), Image.Resampling.BILINEAR))
    paper += grain[:, :, None] * (2.2 if fast else 3.2)

    ink = np.zeros((page_h, page_w), dtype=np.float32)
    ink[margin:margin + body.shape[0], margin:margin + body.shape[1]] = body

    if not fast:
        bleed = Image.fromarray((np.clip(ink, 0, 1) * 255).astype(np.uint8), "L")
        bleed = bleed.filter(ImageFilter.GaussianBlur(radius=max(0.4, 0.28 * scale)))
        ink = np.clip(0.74 * (np.asarray(bleed, dtype=np.float32) / 255.0) + 0.36 * ink, 0.0, 1.0)

    rgb = np.array(ink_color, dtype=np.float32)
    page = np.clip(paper, 0, 255) * (1.0 - ink[:, :, None]) + rgb[None, None, :] * ink[:, :, None]
    return Image.fromarray(np.clip(page, 0, 255).astype(np.uint8), mode="RGB")


def grid_to_text(primary: np.ndarray, bank: GlyphBank) -> str:
    rows = ["".join(bank.chars[int(i)] for i in row) for row in primary]
    return "\n".join(rows)


def grid_html(primary: np.ndarray, bank: GlyphBank, paper: tuple[int, int, int], ink: tuple[int, int, int]) -> str:
    text = grid_to_text(primary, bank)
    # Escape nothing but the characters that would break HTML.
    text = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    paper_hex = f"#{paper[0]:02x}{paper[1]:02x}{paper[2]:02x}"
    ink_hex = f"#{ink[0]:02x}{ink[1]:02x}{ink[2]:02x}"
    return (
        "<!DOCTYPE html>\n<html><head><meta charset='utf-8'>"
        "<title>Typewriter drawing</title>\n<style>\n"
        f"html,body{{background:{paper_hex};margin:0;}}"
        "body{display:flex;justify-content:center;padding:32px 24px;}"
        "pre{font-family:'Special Elite','Courier New',Courier,monospace;"
        f"color:{ink_hex};font-size:9px;line-height:0.92;"
        "letter-spacing:0;white-space:pre;margin:0;}}\n"
        "</style></head><body><pre>\n"
        f"{text}\n</pre></body></html>\n"
    )


class TypewriterEngine:
    def convert(
        self,
        image: Image.Image,
        columns: int = 180,
        charset: str = "portrait",
        paper: str = "cream",
        ink: str = "blue_black",
        contrast: float = 1.4,
        brightness: float = 0.0,
        gamma: float = 1.05,
        detail: float = 0.45,
        simplify: float = 0.55,
        overstrike: int = 1,
        tightness: float = 0.90,
        wander: float = 0.7,
        pressure: float = 0.88,
        scale: int = 2,
        inscription: str = "",
        invert: bool = False,
        seed: int = 7,
        match_font_size: int = 16,
        fast: bool = False,
    ) -> tuple[Image.Image, dict]:
        columns = int(max(40, min(360, columns)))
        overstrike = int(max(0, min(2, overstrike)))
        scale = int(max(1, min(4, scale)))
        simplify = float(np.clip(simplify, 0.0, 1.0))

        luma = prepare_luma(
            image,
            contrast,
            brightness,
            gamma,
            detail,
            simplify=simplify,
            max_side=720 if fast else 1400,
            fast=fast,
        )
        if invert:
            luma = 1.0 - luma

        extra = ""
        chars = CHARSETS.get(charset, CHARSETS["classic"])
        if inscription:
            extra = "".join(
                ch for ch in inscription if ch not in chars and ch.isprintable()
            )
            chars = chars + extra
        cache_key = (charset, match_font_size, extra)
        bank = _BANK_CACHE.get(cache_key)
        if bank is None:
            font = find_typewriter_font(match_font_size)
            probe = font.getbbox("M")
            raw_w = max(6, probe[2] - probe[0] + 2)
            raw_h = max(8, probe[3] - probe[1] + 3)
            bank = GlyphBank(chars, font, raw_w, raw_h)
            _BANK_CACHE[cache_key] = bank
        font = find_typewriter_font(match_font_size)

        aspect = luma.shape[0] / luma.shape[1]
        rows = max(8, int(round(columns * aspect * (bank.cell_w / bank.cell_h))))

        rest = float(np.clip(0.15 + 0.7 * simplify, 0.0, 0.85))
        primary, over = assign_keys(
            luma, bank, rows, columns, overstrike=overstrike, rest=rest, seed=seed, fast=fast
        )

        if inscription:
            small = np.array(
                Image.fromarray((luma * 255).astype(np.uint8)).resize(
                    (columns, rows), Image.Resampling.BILINEAR
                ),
                dtype=np.float32,
            ) / 255.0
            primary = inscribe_text(primary, bank, inscription, small)

        page = render_page(
            primary,
            over,
            bank,
            font,
            PAPERS.get(paper, PAPERS["cream"]),
            INKS.get(ink, INKS["blue_black"]),
            luma,
            tightness=tightness,
            wander=wander,
            pressure=pressure,
            scale=scale,
            seed=seed,
            fast=fast,
        )

        text = grid_to_text(primary, bank)
        html = "" if fast else grid_html(
            primary,
            bank,
            PAPERS.get(paper, PAPERS["cream"]),
            INKS.get(ink, INKS["blue_black"]),
        )
        meta = {
            "chars_wide": columns,
            "chars_tall": rows,
            "charset": charset,
            "overstrike": overstrike,
            "text": text,
            "html": html,
        }
        return page, meta
