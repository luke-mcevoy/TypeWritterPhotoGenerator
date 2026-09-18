"""Compare the unchanged Vibrant renderer with a local shadow-floor candidate."""
import hashlib
import html
import json
from pathlib import Path
import shutil
import time
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from drawing.contour_engine import ContourEngine
from experiments.tonal_target import drawing_target


def main():
    audit = Path("output/algorithm-comparison/nature-buildings")
    root = Path("output/algorithm-comparison/shadow-coverage")
    root.mkdir(parents=True, exist_ok=True)
    cases = [
        {"id": "post30", "title": "Post 30: black cows", "source": "https://carriage-typewriter.fly.dev/p/30", "path": "/private/tmp/carriage-post30-source.jpg"},
        {"id": "post31", "title": "Post 31: black raven", "source": "https://carriage-typewriter.fly.dev/p/31", "path": "/private/tmp/carriage-post31-source.jpg"},
    ]
    scenes = json.loads(Path("experiments/scene_validation.json").read_text())
    cases += [dict(case, path=str(audit/"sources"/f"{case['id']}.jpg"), baseline=n) for n, case in enumerate(scenes)]
    template = (audit/"gallery-template.html").read_text().split("<body>", 1)[0]
    font = ImageFont.load_default(size=17)
    engine = ContourEngine()
    cards = []
    for case in cases:
        stem = case["id"]
        with Image.open(case["path"]) as opened:
            source = ImageOps.exif_transpose(opened).convert("RGB")
        source.thumbnail((2000, 2000), Image.Resampling.BILINEAR)
        source.save(root/f"{stem}-photo.jpg", quality=95)
        panels = {}
        if "baseline" in case:
            base = f"study-{case['baseline']}-vibrant"
            for suffix in (".jpg", "-none.png", "-full.png"):
                shutil.copyfile(audit/f"{base}{suffix}", root/f"{stem}-before{suffix}")
            panels["before"] = Image.open(root/f"{stem}-before.jpg")
        else:
            panels["before"], meta = engine.convert(source, columns=150, color_mode="vibrant", color_amount=.7, shadow_fill=0, include_color_endpoints=True)
            panels["before"].save(root/f"{stem}-before.jpg", quality=96)
            for suffix, endpoint in zip(("none", "full"), meta["color_endpoints"]):
                endpoint.save(root/f"{stem}-before-{suffix}.png")
        start = time.perf_counter()
        # Process-local substitution: no production files or app modes change.
        with patch("drawing.contour_engine.drawing_target", drawing_target):
            panels["candidate"], meta = engine.convert(source, columns=150, color_mode="vibrant", color_amount=.7, include_color_endpoints=True)
        case["seconds"] = round(time.perf_counter()-start, 2)
        case["strikes"] = meta["strike_count"]
        panels["candidate"].save(root/f"{stem}-candidate.jpg", quality=96)
        for suffix, endpoint in zip(("none", "full"), meta["color_endpoints"]):
            endpoint.save(root/f"{stem}-candidate-{suffix}.png")
        width = 1500
        height = round(width*source.height/source.width)
        luma = np.asarray(source.convert("L").resize((width, height)), dtype=np.float32)/255
        dark = luma < .15
        case["dark_source_mean_output_luma"] = {}
        for key in panels:
            mono = Image.open(root/f"{stem}-{key}-none.png")
            margin = (mono.width-width)//2
            pixels = np.asarray(mono.crop((margin, margin, margin+width, margin+height)).convert("L"), dtype=np.float32)/255
            case["dark_source_mean_output_luma"][key] = round(float(pixels[dark].mean()), 3) if dark.any() else None
        max_height = max(ImageOps.contain(p, (490, 730)).height for p in [source, *panels.values()])
        sheet = Image.new("RGB", (1500, max_height+55), "#eee8da")
        draw = ImageDraw.Draw(sheet)
        for i, (label, panel) in enumerate((("Source", source), ("Current Vibrant · 70%", panels["before"]), ("Local shadow candidate · 70%", panels["candidate"]))):
            thumb = ImageOps.contain(panel, (490, 730))
            sheet.paste(thumb, (i*500+(500-thumb.width)//2, 40))
            draw.text((i*500+10, 10), label, font=font, fill="#252922")
        sheet.save(root/f"{stem}-comparison.jpg", quality=95)
        title = html.escape(case["title"])
        ribbons = html.escape(", ".join(meta["ribbons"]))
        section = f'''<p><a href="./">← All shadow comparisons</a> · <a href="{case['source']}">Photo source</a></p>
        <h1>{title}</h1><p>Local experiment only. Identical settings and color planner; additional black character strikes preserve dark interiors.</p>
        <section data-stem="{stem}"><div class="versions">
        <button data-version="before" data-color-controls data-ribbons="{ribbons}" aria-pressed="false">Current Vibrant</button>
        <button data-version="candidate" data-color-controls data-ribbons="{ribbons}" aria-pressed="true">Local shadow candidate</button>
        <button data-version="photo" data-ribbons="source photograph" aria-pressed="false">Photo</button></div>
        <p class="showing">Showing: <strong>Local shadow candidate</strong></p>
        <div class="color-controls"><label for="amount">Color amount <output for="amount">70%</output></label>
        <input id="amount" type="range" min="0" max="100" value="70" disabled><p class="hint">Color fades independently of black shading.</p><p class="color-status" role="status"></p></div>
        <a class="full" href="{stem}-candidate.jpg"><img src="{stem}-candidate.jpg" alt="Local shadow candidate"><canvas class="color-preview" hidden></canvas></a>
        <p>Ribbons: <span class="ribbons">{ribbons}</span> · <a class="download" href="{stem}-candidate.jpg" download>Download this version</a></p></section>'''
        (root/f"{stem}.html").write_text(template+"<body>"+section+'<script src="color-controls.js"></script></body></html>')
        cards.append(f'<section><h2>{title}</h2><a href="{stem}.html"><img style="max-height:none;width:100%" loading="lazy" src="{stem}-comparison.jpg" alt="Source, current Vibrant and local shadow candidate"></a><p><a href="{stem}.html">Compare versions and color amounts</a> · <a href="{case["source"]}">Photo source</a></p></section>')
        print(stem, case["seconds"], case["dark_source_mean_output_luma"], flush=True)
    (root/"index.html").write_text(template+'''<body><h1>Why do dark subjects look hollow?</h1>
    <p>The current contour target suppresses broad, uniform darkness. The local candidate keeps an absolute shadow target so the fitter deposits more overlapping characters inside dark shapes.</p>
    <p>14 comparisons at the same settings: your cows and raven, plus all 12 nature/building tests. These are local experiments; saved posts and the live renderer are unchanged.</p>
    <p><a href="../nature-buildings/">Full color audit</a> · <a href="results.json">Settings and diagnostics</a></p>'''+"".join(cards)+"</body></html>")
    shutil.copyfile("experiments/color_controls.js", root/"color-controls.js")
    (root/"results.json").write_text(json.dumps({"settings": {"columns": 150, "color_mode": "vibrant", "color_amount": .7, "overstrike": 1, "pressure": .88, "contrast": 1.4, "simplify": .55}, "target_sha256": hashlib.sha256(Path("experiments/tonal_target.py").read_bytes()).hexdigest(), "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
