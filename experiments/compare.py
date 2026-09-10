"""Run: python -m experiments.compare PHOTO [PHOTO ...] --columns 140."""

import argparse
import html
import json
from pathlib import Path
import time

from PIL import Image, ImageDraw, ImageOps

from experiments.strike_engine import StrikeEngine
from experiments.contour_engine import ContourEngine
from typewriter_engine import TypewriterEngine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photos", type=Path, nargs="+")
    parser.add_argument("--columns", type=int, default=140)
    parser.add_argument("--mode", choices=["tone", "contour"], default="contour")
    parser.add_argument("--output", type=Path, default=Path("output/algorithm-comparison"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results, cards = [], []
    for index, path in enumerate(args.photos):
        with Image.open(path) as opened:
            source = ImageOps.exif_transpose(opened).convert("RGB")
        stem = f"{index + 1}-{path.stem}"
        source.thumbnail((2000, 2000))
        source.save(args.output / f"{stem}-photo.jpg", quality=95)
        panels = [source]
        alternative = ContourEngine() if args.mode == "contour" else StrikeEngine()
        for label, engine in [("current", TypewriterEngine()), ("experimental", alternative)]:
            start = time.perf_counter()
            rendered, meta = engine.convert(source, columns=args.columns, scale=2, fast=True,
                                            charset="classic", paper="white", ink="carbon")
            elapsed = time.perf_counter() - start
            # Same final size cap as the production app.
            rendered.thumbnail((3200, 3200), Image.Resampling.LANCZOS)
            rendered.save(args.output / f"{stem}-{label}.jpg", quality=95)
            panels.append(rendered)
            results.append({"photo": path.name, "engine": label,
                            "seconds": round(elapsed, 3), "size": rendered.size,
                            "columns": args.columns, "rows": meta["chars_tall"],
                            "candidates": meta.get("candidate_count")})
        sheet = Image.new("RGB", (1440, 740), "#eee8da")
        draw = ImageDraw.Draw(sheet)
        for i, (panel, label) in enumerate(zip(panels, ["Photo", "Current (production fast path)", f"Experimental {args.mode}"])):
            preview = ImageOps.contain(panel, (464, 670))
            sheet.paste(preview, (480 * i + (480 - preview.width) // 2, 42 + (670 - preview.height) // 2))
            draw.text((480 * i + 16, 16), label, fill="black")
        draw.text((16, 722), f"{args.columns} columns requested, classic keys, contrast 1.4, simplify 0.55; contour mode uses free placement.", fill="black")
        sheet.save(args.output / f"{stem}-comparison.jpg", quality=95)
        safe = html.escape(stem, quote=True)
        cards.append(f'''<section><h2>{html.escape(path.stem)}</h2>
          <div class="compare"><img src="{safe}-current.jpg" alt="Current drawing">
            <img class="new" src="{safe}-experimental.jpg" alt="Experimental drawing"></div>
          <label>Current ← <input type="range" min="0" max="100" value="50"
            oninput="this.closest('section').style.setProperty('--split',this.value+'%')"> → Experimental</label>
          <p><a href="{safe}-comparison.jpg">Three-way comparison</a> ·
          <a href="{safe}-photo.jpg">Photo</a> · <a href="{safe}-experimental.jpg">Full experimental drawing</a></p></section>''')
    report = '''<!doctype html><html lang="en"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Carriage algorithm comparison</title><style>
    body{background:#eee8da;color:#252922;font:16px/1.5 system-ui;margin:32px auto;max-width:1000px;padding:0 20px}
    h1{font-family:Georgia,serif;font-weight:normal}section{--split:50%;margin:48px 0}
    .compare{display:grid;background:#f6ecd6;max-height:85vh;overflow:hidden}
    .compare img{grid-area:1/1;width:100%;height:100%;max-height:85vh;object-fit:contain}
    .new{clip-path:inset(0 0 0 var(--split))}input{width:min(65%,500px);vertical-align:middle}
    label{display:block;padding-top:16px}a{color:#38544b}
    </style><h1>Carriage: fitting the printed ink</h1>
    <p>Drag to compare the existing fast renderer (left) with the experiment (right).
    Both use classic keys, white paper and carbon ink. The contour experiment draws with freely placed
    glyphs, so its column setting controls detail rather than a literal text grid.</p>
    <p>These are algorithm studies, not a finished match to the reference artist.
    Inscriptions and HTML export are not implemented. The contour experiment uses geometric edges;
    it cannot yet choose textures based on what objects represent.</p>'''
    (args.output / "index.html").write_text(report + "".join(cards) + "</html>")
    (args.output / "timings.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))
    print(f"Review: {(args.output / 'index.html').resolve()}")


if __name__ == "__main__":
    main()
