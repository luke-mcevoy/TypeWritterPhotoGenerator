"""Build a local gallery: python -m experiments.color_study PHOTO [PHOTO ...]."""

import argparse
import html
import json
from pathlib import Path
import shutil
import time

import numpy as np

from PIL import Image, ImageDraw, ImageOps

from experiments.contour_engine import ContourEngine
from typewriter_engine import TypewriterEngine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photos", type=Path, nargs="+")
    parser.add_argument("--columns", type=int, default=150)
    parser.add_argument("--color-amount", type=float, default=.7)
    parser.add_argument("--refined", action="store_true", help="Include connected color regions and shadow hatching")
    parser.add_argument("--output", type=Path, default=Path("output/algorithm-comparison/color"))
    args = parser.parse_args()
    if not np.isfinite(args.color_amount):
        parser.error("--color-amount must be finite")
    args.color_amount = float(np.clip(args.color_amount, 0, 1))
    args.output.mkdir(parents=True, exist_ok=True)
    cards, timings = [], []
    labels = {"original": "Original algorithm", "mono": "New monochrome",
              "color": "Earlier color" if args.refined else "New color"}
    if args.refined:
        labels["refined"] = "Refined color"
    labels["photo"] = "Photo"
    active = "refined" if args.refined else "color"
    for number, path in enumerate(args.photos, 1):
        # Numbered names keep URLs reliable for photos with spaces or Unicode.
        stem = f"study-{number}"
        with Image.open(path) as opened:
            source = ImageOps.exif_transpose(opened).convert("RGB")
        source.thumbnail((2000, 2000))
        source.save(args.output / f"{stem}-photo.jpg", quality=95)
        panels = {}
        palettes = {}
        variants = [
            ("original", TypewriterEngine(), {}),
            ("mono", ContourEngine(), {}),
            ("color", ContourEngine(), {"color_mode": "ribbon", "color_amount": args.color_amount}),
        ]
        if args.refined:
            variants.append(("refined", ContourEngine(), {"color_mode": "layered", "color_amount": args.color_amount}))
        for key, engine, options in variants:
            start = time.perf_counter()
            settings = dict(columns=args.columns, scale=2, charset="classic", paper="white", ink="carbon", fast=True)
            if key in ("color", "refined"):
                options = {**options, "color_amount": 1}
                full, meta = engine.convert(source, **settings, **options)
                mono, _ = engine.convert(source, **settings, **{**options, "color_amount": 0})
                for endpoint, suffix in ((mono, "none"), (full, "full")):
                    endpoint.thumbnail((3200, 3200), Image.Resampling.LANCZOS)
                    endpoint.save(args.output / f"{stem}-{key}-{suffix}.png")
                drawing = Image.fromarray(np.rint(np.asarray(mono, dtype=np.float32)*(1-args.color_amount)
                    + np.asarray(full, dtype=np.float32)*args.color_amount).astype(np.uint8))
            else:
                drawing, meta = engine.convert(source, **settings, **options)
            seconds = round(time.perf_counter() - start, 3)
            drawing.thumbnail((3200, 3200), Image.Resampling.LANCZOS)
            drawing.save(args.output / f"{stem}-{key}.jpg", quality=96)
            panels[key] = drawing
            palettes[key] = meta.get("ribbons", [])
            timings.append({"photo": path.name, "version": key, "seconds": seconds,
                            "ribbons": meta.get("ribbons", []),
                            "color_strikes": len(meta.get("color_strikes", [])),
                            "hatch_strikes": len(meta.get("hatch_strikes", []))})
        sheet = Image.new("RGB", (1440, 740), "#eee8da")
        draw = ImageDraw.Draw(sheet)
        sheet_keys = ["mono", "color", "refined"] if args.refined else ["original", "mono", "color"]
        for i, key in enumerate(sheet_keys):
            panel, label = panels[key], labels[key]
            thumbnail = ImageOps.contain(panel, (464, 670))
            sheet.paste(thumbnail, (480 * i + (480 - thumbnail.width) // 2, 42 + (670 - thumbnail.height) // 2))
            draw.text((480 * i + 16, 16), label, fill="black")
        draw.text((16, 722), "Every mark is a character. Refined color groups related hues and adds connected shadow hatching.", fill="black")
        sheet.save(args.output / f"{stem}-comparison.jpg", quality=95)
        buttons = "".join(f'<button type="button" data-version="{key}" data-ribbons="{html.escape(", ".join(palettes.get(key, [])) or ("photo" if key == "photo" else "black only"), quote=True)}" aria-pressed="{str(key == active).lower()}">{label}</button>'
                          for key, label in labels.items())
        cards.append(f'''<section data-stem="{stem}"><h2>{html.escape(path.stem)}</h2>
        <div class="versions" role="group" aria-label="Drawing version">{buttons}</div>
        <p class="showing" aria-live="polite">Showing: <strong>{labels[active]}</strong></p>
        <div class="color-controls">
          <label for="{stem}-amount">Color amount <output for="{stem}-amount">{round(args.color_amount*100)}%</output></label>
          <input id="{stem}-amount" type="range" min="0" max="100" step="1" value="{round(args.color_amount*100)}" disabled>
          <div class="range-labels"><span>No color</span><span>Full color</span></div>
          <p class="control-hint">Black outlines and shadows stay fixed. <span class="color-status" role="status"></span></p>
        </div>
        <a class="full" href="{stem}-{active}.jpg" target="_blank" rel="noopener">
          <img src="{stem}-{active}.jpg" alt="{labels[active]} drawing of {html.escape(path.stem, quote=True)}">
          <canvas class="color-preview" hidden></canvas></a>
        <p>Ribbons: <span class="ribbons">{html.escape(', '.join(palettes[active]) or 'black only')}</span> ·
          <a class="download" href="{stem}-{active}.jpg" download>Download this version</a> ·
          <a href="{stem}-comparison.jpg">Side-by-side comparison</a> · Click the drawing to zoom.</p></section>''')
        print(f"Finished {path.name}", flush=True)
    page = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Carriage — color studies</title><style>
    *{box-sizing:border-box}body{margin:36px auto;padding:0 20px;max-width:1100px;background:#eee8da;color:#252922;font:16px/1.5 system-ui}
    h1{font:42px Georgia,serif}h2{font-size:21px}section{margin:50px 0 70px}a{color:#38544b}
    .versions{display:flex;gap:8px;flex-wrap:wrap}button{font:inherit;cursor:pointer;padding:9px 15px;border:1px solid #9b9d91;border-radius:6px;background:transparent;color:inherit}
    button[aria-pressed=true]{background:#254d42;color:white;border-color:#254d42}
    .showing{margin:14px 0}.full{display:block;background:#e5dfd2;text-align:center}
    img,canvas{display:block;max-width:100%;max-height:85vh;width:auto;height:auto;margin:auto}
    [hidden]{display:none!important}.color-controls{max-width:620px;margin:18px 0 22px}
    .color-controls label{display:flex;justify-content:space-between;font-weight:600}
    .color-controls input{width:100%;margin:14px 0 0;accent-color:#254d42}
    .range-labels{display:flex;justify-content:space-between;font-size:13px;color:#526052}
    .control-hint{font-size:13px;margin:8px 0;color:#526052}a[aria-disabled=true]{opacity:.5}
    </style></head><body><h1>Carriage: color in type</h1>
    <p>Choose a version. <b>Original algorithm</b> is the earlier app renderer.
    <b>New monochrome</b> is the first contour drawing. The color versions add colored character strikes.</p>
    <p>The palette is limited to three colored ribbons plus black. Blank areas stay paper;
    every colored mark is a letter or symbol. Use Color amount to fade color from 0% to 100% without changing the black drawing.</p>
    <p><a href="../">Earlier comparisons</a></p>'''
    script = '<script src="color-controls.js"></script></body></html>'
    shutil.copyfile(Path(__file__).with_name("color_controls.js"), args.output / "color-controls.js")
    (args.output / "index.html").write_text(page + "".join(cards) + script)
    (args.output / "timings.json").write_text(json.dumps(timings, indent=2) + "\n")
    print(f"Review: {(args.output / 'index.html').resolve()}")


if __name__ == "__main__":
    main()
