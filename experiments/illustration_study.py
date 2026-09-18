"""Compare the deployed Vibrant renderer with Typed illustration on the same inputs."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import time

from PIL import Image, ImageDraw, ImageOps

from drawing.contour_engine import ContourEngine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photos", nargs="+", type=Path)
    parser.add_argument("--columns", type=int, default=150)
    parser.add_argument("--output", type=Path, default=Path("output/algorithm-comparison/illustrated"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    settings = dict(columns=args.columns, color_amount=.7, shadow_fill=1, scale=2,
                    contrast=1.4, simplify=.55, pressure=.88, overstrike=1, seed=7)
    cards, records = [], []
    for n, path in enumerate(args.photos):
        stem = f"study-{n}"
        with Image.open(path) as opened:
            photo = ImageOps.exif_transpose(opened).convert("RGB")
        photo.thumbnail((2000, 2000), Image.Resampling.BILINEAR)
        photo.save(args.output/f"{stem}-photo.jpg", quality=95)
        panels, buttons = [], []
        for key, mode, label in (("before", "vibrant", "Current Vibrant"),
                                 ("illustrated", "illustrated", "Typed illustration")):
            start = time.perf_counter()
            page, meta = ContourEngine().convert(photo, color_mode=mode, include_color_endpoints=True, **settings)
            elapsed = round(time.perf_counter()-start, 3)
            page.save(args.output/f"{stem}-{key}.jpg", quality=96)
            for suffix, endpoint in zip(("none", "full"), meta["color_endpoints"]):
                endpoint.save(args.output/f"{stem}-{key}-{suffix}.png")
            palettes = ", ".join(meta["ribbons"]).replace("_", " ") or "black only"
            buttons.append(f'<button data-version="{key}" data-color-controls data-ribbons="{palettes}" aria-pressed="{str(key == "illustrated").lower()}">{label}</button>')
            panels.append((label+" · 70%", page))
            records.append(dict(photo=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                mode=mode, settings=settings, seconds=elapsed, strikes=meta["strike_count"],
                color_strikes=len(meta["color_strikes"]), ribbons=meta["ribbons"]))
        panel_height = min(850, round(490*photo.height/photo.width)+30)
        sheet = Image.new("RGB", (1500, panel_height+40), "#eee8da")
        draw = ImageDraw.Draw(sheet)
        for i, (label, panel) in enumerate([("Source photograph", photo), *panels]):
            thumb = ImageOps.contain(panel, (490, panel_height))
            sheet.paste(thumb, (i*500+(500-thumb.width)//2, 40+(panel_height-thumb.height)//2))
            draw.text((i*500+12, 14), label, fill="#252922")
        sheet.save(args.output/f"{stem}-comparison.jpg", quality=95)
        cards.append(f'''<section data-stem="{stem}"><h2>{html.escape(path.stem)}</h2>
        <div class="versions">{"".join(buttons)}<button data-version="photo" data-ribbons="photograph" aria-pressed="false">Photo</button></div>
        <p class="showing" aria-live="polite">Showing: <strong>Typed illustration</strong></p>
        <div class="color-controls"><label for="{stem}-amount">Color amount <output for="{stem}-amount">70%</output></label>
        <input id="{stem}-amount" type="range" min="0" max="100" value="70" disabled>
        <p class="color-status" role="status"></p></div>
        <a class="full" href="{stem}-illustrated.jpg" target="_blank" rel="noopener"><img src="{stem}-illustrated.jpg" alt="Typed illustration"><canvas class="color-preview" hidden></canvas></a>
        <p>Ribbons: <span class="ribbons"></span> · <a class="download" href="{stem}-illustrated.jpg" download>Download this version</a>
        · <a href="{stem}-comparison.jpg">Source / current / new comparison</a></p></section>''')
        print(f"Finished {path.name}", flush=True)
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Carriage — detailed type study</title><style>
    *{box-sizing:border-box}body{max-width:1200px;margin:32px auto;padding:0 20px;background:#eee8da;color:#252922;font:16px/1.5 system-ui}
    h1{font:38px Georgia}section{margin:50px 0 80px}.versions{display:flex;gap:8px;flex-wrap:wrap}
    button{font:inherit;padding:10px 16px;border:1px solid #66766a;background:transparent;cursor:pointer;border-radius:5px}
    button[aria-pressed=true]{background:#254d42;color:white}.full{display:block;background:#e3dece}
    img,canvas{display:block;max-width:100%;width:auto;height:auto;max-height:88vh;margin:auto}[hidden]{display:none!important}
    .color-controls{max-width:600px;margin:20px 0}label{display:flex;justify-content:space-between}input{width:100%;accent-color:#254d42}
    a{color:#254d42}.color-status{font-size:13px}a[aria-disabled=true]{opacity:.5}
    </style><h1>Detailed type study</h1><p>Same photographs, settings and 70% color. Compare the current Vibrant renderer with the revised full-keyboard fit,
    varied colored impressions and shape-matched contours. Click the drawing to examine individual keys.</p>
    <p>This is a local preview, not a production replacement. More character variety is a measurable improvement, but does not establish artistic equivalence
    to the reference. The renderer still uses geometry rather than object understanding or deliberate lettering.</p>'''
    (args.output/"index.html").write_text(page+"".join(cards)+'<script src="color-controls.js"></script></html>')
    shutil.copyfile(Path(__file__).with_name("color_controls.js"), args.output/"color-controls.js")
    (args.output/"manifest.json").write_text(json.dumps(dict(records=records, renderer_sha256={
        name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
        for name in ("drawing/contour_engine.py", "drawing/illustration.py", "drawing/vibrant_color.py")}), indent=2))


if __name__ == "__main__":
    main()
