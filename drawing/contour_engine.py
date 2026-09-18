"""Place overlapping keys along form, outside a text grid.

This is a geometric experiment, not semantic scene understanding. Its ink
target deliberately suppresses flat photographic tone and emphasizes contours.
"""

from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from typewriter_engine import CHARSETS, INKS, PAPERS, find_typewriter_font, _sobel


def _blur(arr, radius):
    image = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))
    return np.asarray(image.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255


@lru_cache(maxsize=8)
def _atlas(charset):
    chars = list(dict.fromkeys(CHARSETS.get(charset, CHARSETS["classic"])))
    chars = [ch for ch in chars if ch != " "]
    font = find_typewriter_font(20)
    masks = []
    for ch in chars:
        image = Image.new("L", (20, 24))
        box = font.getbbox(ch)
        ImageDraw.Draw(image).text(((20 - box[2] + box[0]) / 2 - box[0],
                                   (24 - box[3] + box[1]) / 2 - box[1]),
                                  ch, fill=255, font=font)
        masks.append(np.asarray(image, dtype=np.float32) / 255)
    return chars, np.stack(masks)


def drawing_target(image, size, simplify=.55, contrast=1.4):
    """Three bands: restrained wash, local shadow, and dark-side contours."""
    gray = ImageOps.exif_transpose(image).convert("L").resize(size, Image.Resampling.LANCZOS)
    arr = np.asarray(gray.filter(ImageFilter.MedianFilter(3)), dtype=np.float32) / 255
    lo, hi = np.percentile(arr, [.5, 99.5])
    if hi - lo > .01:
        arr = np.clip((arr - lo) / (hi - lo), 0, 1)
    fine = _blur(arr, 1.1)
    mass = _blur(arr, 9)
    broad = _blur(arr, 24)
    local = np.maximum(mass - fine, 0)
    edge = np.clip(local * 5, 0, 1)
    gx, gy = _sobel(mass)
    activity = np.clip(_blur(np.hypot(gx, gy), 12) * 5, 0, 1)
    ink = 1 - fine
    # Flat dark sky/background is intentionally lighter, while local shadow
    # and silhouette contours retain ink. This cannot distinguish objects.
    wash = ink ** 1.65 * (.035 + .65 * activity)
    shadow = np.clip(broad - fine, 0, 1) * 1.15
    target = np.clip((wash + .52 * edge + shadow) * contrast / 1.25, 0, .78)
    target *= 1 - .2 * float(np.clip(simplify, 0, 1))
    return target.astype(np.float32)


class ContourEngine:
    def convert(self, image, columns=140, charset="classic", paper="white",
                ink="carbon", simplify=.55, contrast=1.4, pressure=.88,
                wander=.7, overstrike=1, seed=7, scale=2, fast=False,
                color_mode="none", color_amount=.7, hatch_amount=.7,
                shadow_fill=1, include_color_endpoints=False, progress=None, **settings):
        # progress(fraction, label) is called at stage boundaries and every
        # few hundred keys so the studio can show what the machine is doing.
        report = progress if callable(progress) else (lambda fraction, label: None)
        if color_mode not in ("none", "ribbon", "layered", "vibrant", "illustrated"):
            raise ValueError("Unknown color mode")
        color_amount = float(color_amount)
        hatch_amount = float(hatch_amount)
        if not np.isfinite(color_amount) or not np.isfinite(hatch_amount):
            raise ValueError("Color and hatch amounts must be finite numbers")
        color_amount = float(np.clip(color_amount, 0, 1))
        hatch_amount = float(np.clip(hatch_amount, 0, 1))
        shadow_fill = float(shadow_fill)
        if not np.isfinite(shadow_fill):
            raise ValueError("Shadow fill must be a finite number")
        shadow_fill = float(np.clip(shadow_fill, 0, 1))
        if settings.get("inscription"):
            raise ValueError("Hidden lines are available with the original drawing style")
        source = ImageOps.exif_transpose(image)
        width = int(np.clip(columns, 40, 240)) * 10
        height = max(24, round(width * source.height / source.width))
        if width * height > 5_000_000:
            raise ValueError("Reduce columns for this image aspect ratio")
        report(.02, "Reading the photograph…")
        plan = None
        if color_mode == "illustrated":
            from drawing.illustration import illustration_plan, KeySelector
            plan = illustration_plan(source, width, height, simplify, contrast, shadow_fill)
            target = plan.pop("target")
        else:
            target = drawing_target(source, (width, height), simplify, contrast)
        if color_mode == "vibrant":
            from drawing.shadow_tone import preserve_shadows
            target = preserve_shadows(source, (width, height), target, simplify, contrast,
                                     amount=shadow_fill)
        target *= float(np.clip(pressure, .1, 1.2))
        report(.05, "Tracing contours…")
        chars, glyphs = _atlas(charset)
        selector = KeySelector(plan, chars, width, height) if plan is not None else None
        canvas = np.zeros((height + 24, width + 20), np.float32)
        padded_target = np.pad(target, ((12, 12), (10, 10)))
        rng = np.random.default_rng(seed)
        strikes = []
        # Trace persistent edges with directional keys before laying shade.
        # Nonmaximum suppression thins edges so this follows a contour rather
        # than filling a thick Sobel band with letters.
        gray = np.asarray(source.convert("L").resize((width, height)), dtype=np.float32) / 255
        gx, gy = _sobel(_blur(gray, 2.4 if plan is not None else 2.1))
        magnitude = np.hypot(gx, gy)
        direction = (np.rint(np.arctan2(gy, gx) / (np.pi / 4)).astype(int) % 4)
        peaks = np.zeros_like(magnitude, dtype=bool)
        for axis, (dy, dx) in enumerate([(0, 1), (1, 1), (1, 0), (1, -1)]):
            before = np.roll(magnitude, (dy, dx), axis=(0, 1))
            after = np.roll(magnitude, (-dy, -dx), axis=(0, 1))
            peaks |= (direction == axis) & (magnitude >= before) & (magnitude >= after)
        peaks[:12] = peaks[-12:] = False
        peaks[:, :10] = peaks[:, -10:] = False
        minimum, percentile = (.22, 92) if plan is not None else (.16, 88)
        threshold = max(minimum, float(np.percentile(magnitude, percentile)))
        yy, xx = np.where(peaks & (magnitude > threshold))
        order = np.argsort(magnitude[yy, xx])[::-1]
        occupied = np.zeros((height, width), bool)
        line_chars, line_masks = _atlas("architecture")
        if plan is not None:
            # Fit curves, corners and punctuation to the actual edge shape,
            # instead of assigning every outline one of four straight keys.
            edge_ink = _blur(np.clip(peaks*magnitude/max(threshold, .01), 0, 1), .85)
            edge_ink = np.pad(np.clip(edge_ink*2.8, 0, 1), ((12, 12), (10, 10)))
            edge_indices = [line_chars.index(ch) for ch in "|/\\-_():,'" if ch in line_chars]
            edge_masks = line_masks[edge_indices].reshape(len(edge_indices), -1)
            edge_norms = (edge_masks*edge_masks).sum(axis=1)
        for item in order:
            x, y = int(xx[item]), int(yy[item])
            if occupied[y, x]:
                continue
            char = ["|", "/", "-", "\\"][direction[y, x]]
            if plan is not None:
                desired_edge = edge_ink[y:y+24, x:x+20].ravel()
                score = 2*(edge_masks @ desired_edge)/(edge_norms + float(desired_edge @ desired_edge) + 1e-8)
                char = line_chars[edge_indices[int(np.argmax(score))]]
            glyph = line_masks[line_chars.index(char)]
            strength = float(np.clip(magnitude[y, x] * 1.7, .55, .94))
            patch = canvas[y:y + 24, x:x + 20]
            patch += (1 - patch) * glyph * strength
            strikes.append((char, x, y, strength))
            # Continuous lines can join at fractional carriage positions.
            occupied[max(0,y-4):y+5, max(0,x-4):x+5] = True
        if plan is not None:
            del edge_ink, edge_masks, edge_norms, edge_indices
        # Half-line feeds and fractional carriage offsets let keys join across
        # nominal cells. Every candidate is fitted against already printed ink.
        passes = 2 + 2 * int(np.clip(overstrike, 0, 2))
        if plan is not None:
            passes += 2
        # Share of the progress bar given to key fitting; color mixing is
        # roughly a third of the wall time when a color mode is selected.
        fit_span = .80 if color_mode == "none" else .50
        # Flattened glyph bank so each candidate is scored with three small
        # matrix-vector products instead of three N×24×20 temporaries.
        glyph_rows = glyphs.reshape(len(chars), -1)
        glyph_rows_sq = glyph_rows * glyph_rows
        # Summed-area table of the target: the residual under a key can never
        # exceed the target there, so keys over near-bare paper are dropped in
        # bulk before the fitting loop (identical to failing the mean test).
        integral = np.pad(np.cumsum(np.cumsum(padded_target, axis=0, dtype=np.float64), axis=1), ((1, 0), (1, 0)))
        for layer in range(passes):
            positions = []
            xs = np.arange(0, width, 12, dtype=np.float64)
            for y in range(0, height, 16):
                if plan is None:
                    # Preserve the earlier modes' random sequence exactly.
                    row_offset = rng.uniform(0, 12)
                    jitter = rng.uniform(-3, 3, size=(len(xs), 2))
                else:
                    # Shared carriage drift keeps keys on a legible baseline.
                    row_offset = (layer*5) % 12
                    jitter = np.full((len(xs), 2), rng.uniform(-.5, .5))
                px = np.clip(xs + row_offset + jitter[:, 0], 0, width - 1).astype(int)
                py = np.clip(y + (layer * 6) % 16 + jitter[:, 1], 0, height - 1).astype(int)
                positions.extend(zip(px.tolist(), py.tolist()))
            pos = np.array(positions, dtype=np.intp).reshape(-1, 2)
            px, py = pos[:, 0], pos[:, 1]
            # Most important residual first; keys added later see the ink laid
            # down by earlier keys, including overlaps across row boundaries.
            # Stable descending order matches list.sort(reverse=True).
            order = np.argsort(-target[np.minimum(py, height - 1), np.minimum(px, width - 1)], kind="stable")
            px, py = px[order], py[order]
            # Sum of the 24×20 target window under each key, from the summed-area table.
            window = (integral[py + 24, px + 20] - integral[py, px + 20]
                      - integral[py + 24, px] + integral[py, px])
            keep = window / 480 >= .012 - 1e-6
            candidates = list(zip(px[keep].tolist(), py[keep].tolist()))
            pass_label = f"Striking keys · pass {layer + 1} of {passes}"
            report(.08 + fit_span * layer / passes, pass_label)
            for count, (x, y) in enumerate(candidates):
                if count and count % 500 == 0:
                    report(.08 + fit_span * (layer + count / len(candidates)) / passes, pass_label)
                patch = canvas[y:y + 24, x:x + 20]
                desired = padded_target[y:y + 24, x:x + 20]
                residual = desired - patch
                mean = float(residual.sum()) / 480
                if mean < .012:
                    continue
                # deposited_n = glyph_n * (1 - patch); every per-glyph sum below
                # is a dot product of the flattened glyph with a local vector.
                headroom = (1 - patch).ravel()
                rows, rows_sq = glyph_rows, glyph_rows_sq
                # Multiscale residual matching: pixel fit follows contours;
                # cell-mean fit controls the amount of shade deposited.
                gd = rows @ headroom / 480
                dot = rows @ (headroom * residual.ravel()) / 480 + 5 * gd * mean
                norm = rows_sq @ (headroom * headroom) / 480 + 5 * gd * gd
                strength = np.minimum(np.maximum(dot / np.maximum(norm, 1e-8), .60), .97)
                improvement = 2 * strength * dot - strength * strength * norm
                # A small cost per mark leaves highlights as actual bare paper.
                index = int(np.argmax(improvement))
                if improvement[index] < .0008:
                    continue
                if selector is not None:
                    index = selector.choose(improvement, x, y)
                alpha = float(strength[index])
                patch += glyphs[index] * (1 - patch) * alpha
                strikes.append((chars[index], x, y, alpha))
        body = canvas[12:height + 12, 10:width + 10]
        # Export scale resamples an identical strike plan.
        mask = Image.fromarray((np.clip(body, 0, 1) * 255).astype(np.uint8))
        multiplier = max(.5, min(2, float(scale) / 2))
        mask = mask.resize((round(width * multiplier), round(height * multiplier)), Image.Resampling.LANCZOS)
        # The color stage does not need the large fitting/edge workspaces.
        del canvas, padded_target, target, body, gray, gx, gy, magnitude
        del direction, peaks, occupied, yy, xx, order, before, after
        margin = max(20, round(mask.width * .035))
        paper_rgb = np.array(PAPERS.get(paper, PAPERS["white"]), dtype=np.float32)
        ink_rgb = np.array(INKS.get(ink, INKS["carbon"]), dtype=np.float32)
        color_meta = {"ribbons": [], "color_strikes": []}
        underlay = None
        hatch_underlay = None
        color_start = .08 + fit_span
        report(color_start, "Mixing color…" if color_mode != "none" else "Pressing the page…")
        if color_mode != "none":
            if color_mode == "illustrated":
                from drawing.illustration import illustrated_underlay as color_underlay
            elif color_mode == "vibrant":
                from drawing.vibrant_color import vibrant_underlay as color_underlay
            elif color_mode == "layered":
                from drawing.layered_color import layered_underlay as color_underlay
            else:
                from drawing.ribbon_color import color_underlay
            color_span = .92 - color_start

            def color_progress(fraction, label):
                report(color_start + color_span * float(fraction), label)

            pixels, color_meta = color_underlay(source, width, height, paper_rgb,
                chars, glyphs, amount=1, seed=seed, progress=color_progress,
                **({"plan": plan} if plan is not None else {}),
                **({"ink_rgb": ink_rgb, "hatch_amount": hatch_amount} if color_mode in ("layered", "vibrant") else {}))
            # Keep a stable set of colored marks at every amount. The control
            # fades only their contribution, leaving black hatching unchanged.
            # A fixed pair of endpoints also lets the viewer render instantly.
            if color_meta.get("hatch_strikes"):
                hatch = np.empty((height + 24, width + 20, 3), dtype=np.float32)
                hatch[:] = paper_rgb
                transmission = np.clip(ink_rgb / paper_rgb, 0, 1)
                for ch, x, y, strength in color_meta["hatch_strikes"]:
                    patch = hatch[y:y + 24, x:x + 20]
                    patch *= 1-glyphs[chars.index(ch), :, :, None]*strength*(1-transmission)
                hatch_underlay = Image.fromarray(np.clip(hatch[12:height+12, 10:width+10], 0, 255).astype(np.uint8)).resize(
                    mask.size, Image.Resampling.LANCZOS)
                del hatch
            if color_meta["color_strikes"]:
                underlay = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8)).resize(
                    mask.size, Image.Resampling.LANCZOS)
            del pixels
        report(.92, "Pressing the page…")
        page = Image.new("RGB", (mask.width + 2 * margin, mask.height + 2 * margin), tuple(paper_rgb.astype(int)))
        endpoints = [page.copy(), page.copy()] if include_color_endpoints and color_mode != "none" else []
        for y in range(0, mask.height, 64):
            a = np.asarray(mask.crop((0, y, mask.width, min(y + 64, mask.height))), dtype=np.float32) / 255
            box = (0, y, mask.width, min(y + 64, mask.height))
            base = paper_rgb
            if hatch_underlay is not None:
                base = np.asarray(hatch_underlay.crop(box), dtype=np.float32)
            mono = np.clip(base - a[:, :, None]*(base-ink_rgb), 0, 255).astype(np.uint8)
            if underlay is not None:
                full_base = np.asarray(underlay.crop(box), dtype=np.float32)
                full = np.clip(full_base - a[:, :, None]*(full_base-ink_rgb), 0, 255).astype(np.uint8)
                # Match interpolation of the exported, lossless endpoints.
                rgb = np.rint(mono.astype(np.float32)*(1-color_amount) + full.astype(np.float32)*color_amount).astype(np.uint8)
            else:
                full = mono
                rgb = mono
            page.paste(Image.fromarray(rgb), (margin, margin + y))
            if endpoints:
                endpoints[0].paste(Image.fromarray(mono), (margin, margin + y))
                endpoints[1].paste(Image.fromarray(full), (margin, margin + y))
        if color_amount == 0:
            color_meta["ribbons"] = []
            color_meta["color_strikes"] = []
        return page, {"algorithm": "contour", "strike_count": len(strikes),
                      "chars_wide": columns, "chars_tall": round(height / 16),
                      "overstrike": int(np.clip(overstrike, 0, 2)),
                      "text": "", "html": "", "strikes": strikes,
                      "color_mode": color_mode, "color_amount": color_amount,
                      "shadow_fill": shadow_fill,
                      "hatch_amount": hatch_amount, "color_endpoints": endpoints, **color_meta}
