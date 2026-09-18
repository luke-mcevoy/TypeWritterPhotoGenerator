"""Render a reproducible comparison of refined and vibrant ribbon color."""
import argparse
import html
import json
from pathlib import Path
import shutil
import time

from PIL import Image, ImageDraw, ImageOps

from drawing.contour_engine import ContourEngine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photos", type=Path, nargs="+")
    parser.add_argument("--columns", type=int, default=150)
    parser.add_argument("--output", type=Path, default=Path("output/algorithm-comparison/vibrant"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cards, timings = [], []
    engine = ContourEngine()
    for n, path in enumerate(args.photos):
        stem = f"study-{n}"
        with Image.open(path) as opened:
            source = ImageOps.exif_transpose(opened).convert("RGB")
        source.thumbnail((2000, 2000), Image.Resampling.BILINEAR)
        source.save(args.output/f"{stem}-photo.jpg", quality=95)
        panels, palettes = {}, {}
        for key, mode in (("before", "layered"), ("vibrant", "vibrant")):
            start = time.perf_counter()
            page, meta = engine.convert(source, columns=args.columns, color_mode=mode,
                color_amount=.7, include_color_endpoints=True)
            for suffix, endpoint in zip(("none", "full"), meta["color_endpoints"]):
                endpoint.save(args.output/f"{stem}-{key}-{suffix}.png")
            page.save(args.output/f"{stem}-{key}.jpg", quality=96)
            panels[key] = page
            palettes[key] = ", ".join(meta["ribbons"]).replace("_", " ") or "black only"
            timings.append(dict(study=n, mode=mode, seconds=round(time.perf_counter()-start, 2),
                ribbons=meta["ribbons"], color_strikes=len(meta["color_strikes"])))
        sheet = Image.new("RGB", (1500, 780), "#eee8da")
        draw = ImageDraw.Draw(sheet)
        for i, (label, panel) in enumerate((("Source photograph", source),
            ("Previous color at 70%", panels["before"]), ("Improved color at 70%", panels["vibrant"]))):
            thumb = ImageOps.contain(panel, (490, 730))
            sheet.paste(thumb, (i*500+(500-thumb.width)//2, 35))
            draw.text((i*500+15, 12), label, fill="#252922")
        sheet.save(args.output/f"{stem}-comparison.jpg", quality=95)
        cards.append(f'''<section data-stem="{stem}"><h2>{html.escape(path.stem)}</h2>
        <div class="versions">
          <button data-version="before" data-color-controls data-ribbons="{palettes['before']}" aria-pressed="false">Previous color</button>
          <button data-version="vibrant" data-color-controls data-ribbons="{palettes['vibrant']}" aria-pressed="true">Vibrant color</button>
          <button data-version="photo" data-ribbons="source photograph" aria-pressed="false">Photo</button>
        </div>
        <p class="showing" aria-live="polite">Showing: <strong>Vibrant color</strong></p>
        <div class="color-controls"><label for="{stem}-amount">Color amount <output for="{stem}-amount">70%</output></label>
          <input id="{stem}-amount" type="range" min="0" max="100" step="1" value="70" disabled>
          <p class="hint">0% no color · 100% full color. Black outlines and shadows stay fixed.</p>
          <p class="color-status" role="status"></p></div>
        <a class="full" href="{stem}-vibrant.jpg" target="_blank" rel="noopener">
          <img src="{stem}-vibrant.jpg" alt="Vibrant color drawing"><canvas class="color-preview" hidden></canvas></a>
        <p>Ribbons: <span class="ribbons">{palettes['vibrant']}</span> ·
          <a class="download" href="{stem}-vibrant.jpg" download>Download this version</a> ·
          <a href="{stem}-comparison.jpg">Side-by-side comparison</a></p></section>''')
        print(f"Finished {path.name}", flush=True)
    page = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1"><title>Carriage — improved color</title>
    <style>*{box-sizing:border-box}body{margin:36px auto;padding:0 20px;max-width:1100px;background:#eee8da;color:#252922;font:16px/1.5 system-ui}
    h1{font:42px Georgia,serif}h2{font-size:21px}section{margin:40px 0 70px}a{color:#38544b}
    .versions{display:flex;gap:8px;flex-wrap:wrap}button{font:inherit;cursor:pointer;padding:9px 15px;border:1px solid #9b9d91;border-radius:6px;background:transparent;color:inherit}
    button[aria-pressed=true]{background:#254d42;color:white;border-color:#254d42}.full{display:block;background:#e5dfd2;text-align:center}
    img,canvas{display:block;max-width:100%;max-height:85vh;width:auto;height:auto;margin:auto}[hidden]{display:none!important}
    .color-controls{max-width:620px;margin:18px 0}.color-controls label{display:flex;justify-content:space-between;font-weight:600}
    .color-controls input{width:100%;margin-top:14px;accent-color:#254d42}.hint,.color-status{font-size:13px;margin:8px 0;color:#526052}
    a[aria-disabled=true]{opacity:.5}</style></head><body><h1>Carriage: richer ribbon color</h1>
    <p>Compare the previous color with the improvement. The new version keeps yellow-green foliage green,
    retains more local object colors, and builds stronger color through overlapping character impressions.</p>
    <p>Both versions start at 70%. Change the amount to compare them at the same intensity.</p>'''
    shutil.copyfile(Path(__file__).with_name("color_controls.js"), args.output/"color-controls.js")
    (args.output/"index.html").write_text(page+"".join(cards)+'<script src="color-controls.js"></script></body></html>')
    (args.output/"timings.json").write_text(json.dumps(timings, indent=2))


if __name__ == "__main__":
    main()
