"""Local scene audit: fixed settings, contact sheets, per-photo viewers and diagnostics.

Place the photos named in scene_validation.json in OUTPUT/sources first.
The renderer is never changed or tuned by this script.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


def color_diagnostics(root, n, columns):
    # Only compare the image body, excluding its paper margin. This measures
    # placement/coverage, not photographic fidelity or artistic quality.
    width = columns*10
    source = Image.open(root/f"study-{n}-photo.jpg").convert("RGB")
    height = max(24, round(width*source.height/source.width))
    source = source.resize((width, height), Image.Resampling.BILINEAR)
    src = np.asarray(source.convert("HSV"), dtype=np.float32)/255
    colorful = (src[:, :, 1] > .18) & (src[:, :, 1]*src[:, :, 2] > .04) & (src[:, :, 2] > .15)
    neutral = src[:, :, 1]*src[:, :, 2] < .03
    dark = colorful & (src[:, :, 2] < .30)
    output = {}
    for key in ("before", "vibrant"):
        full = Image.open(root/f"study-{n}-{key}-full.png")
        margin = (full.width-width)//2
        box = (margin, margin, margin+width, margin+height)
        pixels = np.asarray(full.crop(box), dtype=np.float32)
        mono = np.asarray(Image.open(root/f"study-{n}-{key}-none.png").crop(box), dtype=np.float32)
        colored_ink = (mono-pixels).max(axis=-1) > 8
        hsv = np.asarray(full.crop(box).convert("HSV"), dtype=np.float32)/255
        delta = np.abs(hsv[:, :, 0]-src[:, :, 0])
        agrees = np.minimum(delta, 1-delta)*360 < 35
        def percent(mask, value):
            return round(float(value[mask].mean())*100, 1) if mask.any() else None
        output[key] = {
            "coverage_of_source_color_pct": percent(colorful, colored_ink),
            "dark_color_coverage_pct": percent(dark, colored_ink),
            "hue_within_35_degrees_on_colored_marks_pct": percent(colorful & colored_ink, agrees),
            "color_ink_on_neutral_source_pct": percent(neutral, colored_ink),
        }
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/algorithm-comparison/nature-buildings"))
    parser.add_argument("--columns", type=int, default=150)
    parser.add_argument("--reuse", action="store_true", help="Rebuild review pages without rerendering")
    args = parser.parse_args()
    root = args.output
    previous = json.loads((root/"results.json").read_text()) if args.reuse and (root/"results.json").exists() else {}
    cases = json.loads(Path(__file__).with_name("scene_validation.json").read_text())
    if not args.reuse:
        subprocess.run([sys.executable, "-m", "experiments.vibrant_study", *[
            str(root/"sources"/f"{case['id']}.jpg") for case in cases],
            "--columns", str(args.columns), "--output", str(root)], check=True)
        (root/"gallery-template.html").write_text((root/"index.html").read_text())
    page = (root/"gallery-template.html").read_text()
    head = page.split("<body>", 1)[0]
    sections = re.findall(r'<section data-stem=.*?</section>', page, flags=re.S)
    assert len(sections) == len(cases)
    timings = json.loads((root/"timings.json").read_text())
    notes_path = Path(__file__).with_name("scene_findings.json")
    notes = json.loads(notes_path.read_text()) if notes_path.exists() else {}
    font = ImageFont.load_default(size=18)
    for n, case in enumerate(cases):
        case["sha256"] = hashlib.sha256((root/"sources"/f"{case['id']}.jpg").read_bytes()).hexdigest()
        case["diagnostics"] = color_diagnostics(root, n, args.columns)
        case["seconds"] = next(row["seconds"] for row in timings if row["study"] == n and row["mode"] == "vibrant")
        case["findings"] = notes.get(case["id"], {})
        section = re.sub(r"<h2>.*?</h2>", f"<h2>{html.escape(case['title'])}</h2>", sections[n], count=1)
        finding = case["findings"]
        review = html.escape(finding.get("note", "Visual review pending."))
        credit = html.escape(case.get("author", "Photographer credited on source page"))
        banner = f'<p><a href="./">← All 12 scenes</a></p><p>{review}</p><p>Photo: {credit} · <a href="{case["source"]}">Pexels source</a></p>'
        (root/f"{case['id']}.html").write_text(head+"<body>"+banner+section+'<script src="color-controls.js"></script></body></html>')
        # A normal-size comparison of amounts needs only the fixed endpoints.
        zero = Image.open(root/f"study-{n}-vibrant-none.png")
        full = Image.open(root/f"study-{n}-vibrant-full.png")
        panels = [("Source", Image.open(root/f"study-{n}-photo.jpg"))]
        panels += [(f"Vibrant {amount}%", Image.blend(zero, full, amount/100)) for amount in (40, 70, 100)]
        panel_height = max(ImageOps.contain(panel, (390, 660)).height for _, panel in panels)
        sheet = Image.new("RGB", (1600, panel_height+55), "#eee8da")
        draw = ImageDraw.Draw(sheet)
        for i, (label, panel) in enumerate(panels):
            thumb = ImageOps.contain(panel, (390, 660))
            sheet.paste(thumb, (i*400+(400-thumb.width)//2, 40))
            draw.text((i*400+12, 10), label, font=font, fill="#252922")
        sheet.save(root/f"{case['id']}-amounts.jpg", quality=94)
        comparison_panels = [("Source photograph", panels[0][1]),
            ("Previous Refined · 70%", Image.open(root/f"study-{n}-before.jpg")),
            ("Current Vibrant · 70%", Image.open(root/f"study-{n}-vibrant.jpg"))]
        panel_height = max(ImageOps.contain(panel, (490, 730)).height for _, panel in comparison_panels)
        comparison = Image.new("RGB", (1500, panel_height+55), "#eee8da")
        draw = ImageDraw.Draw(comparison)
        for i, (label, panel) in enumerate(comparison_panels):
            thumb = ImageOps.contain(panel, (490, 730))
            comparison.paste(thumb, (i*500+(500-thumb.width)//2, 40))
            draw.text((i*500+12, 10), label, font=font, fill="#252922")
        comparison.save(root/f"study-{n}-comparison.jpg", quality=95)
        print(case["id"], case["diagnostics"]["vibrant"], flush=True)
    files = [Path("typewriter_engine.py"), *sorted(Path("drawing").glob("*.py"))]
    manifest = {"created_utc": previous.get("created_utc", datetime.now(timezone.utc).isoformat()), "settings": {
        "columns": args.columns, "charset": "classic", "paper": "white", "ink": "carbon",
        "simplify": .55, "contrast": 1.4, "pressure": .88, "overstrike": 1, "scale": 2,
        "color_amounts_reviewed": [40, 70, 100], "source_max_side": 2000,
    }, "renderer_sha256": previous.get("renderer_sha256", {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),
        "metric_note": "Coverage diagnostics use full-color output and are not artistic quality scores. No object segmentation or ground-truth annotations.", "cases": cases}
    (root/"results.json").write_text(json.dumps(manifest, indent=2))
    cards = []
    for n, case in enumerate(cases):
        finding = case["findings"]
        cards.append(f'''<article id="{case['id']}" data-group="{case['group']}">
        <h2>{html.escape(case['title'])} <small>{html.escape(finding.get('verdict','Review pending'))}</small></h2>
        <p>{html.escape(finding.get('note',''))}</p>
        <a href="{case['id']}.html"><img loading="lazy" src="study-{n}-comparison.jpg" alt="Source, previous renderer and current Vibrant color for {html.escape(case['title'])}"></a>
        <p><a href="{case['id']}.html">Open color slider and download</a> · <a href="{case['id']}-amounts.jpg">Compare 40%, 70%, 100%</a> · <a href="{case['source']}">Photo source</a></p></article>''')
    overview = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Carriage — nature and buildings color test</title><style>
    *{box-sizing:border-box}body{max-width:1350px;margin:35px auto;padding:0 20px;background:#eee8da;color:#252922;font:16px/1.5 system-ui}
    h1{font:38px Georgia,serif}h2{font-size:23px}small{font-size:14px;margin-left:12px;color:#546450}
    a{color:#315647}img{width:100%;height:auto}article{margin:45px 0;border-top:1px solid #bbb8a8;padding-top:15px}
    nav{display:flex;gap:14px;flex-wrap:wrap}button{font:inherit;padding:9px 18px;background:transparent;border:1px solid #65735e;border-radius:5px;cursor:pointer}
    button[aria-pressed=true]{background:#315647;color:white}[hidden]{display:none!important}</style></head><body>
    <h1>Does the color hold up beyond Harvard?</h1>
    <p>12 additional photos: seven nature scenes and five buildings. Same current renderer, no image-specific tuning.
    Main comparisons show the source, previous Refined color and current Vibrant color at 70%.</p>
    <p>Open a scene to change its amount, or compare 40%, 70% and 100%. Each photo has a source link.
    <a href="results.json">Settings, image hashes and diagnostics</a> · <a href="report.md">Written findings</a></p>
    <p><strong>Finding:</strong> Bright object colors improve, but shaded subjects can look hollow and subtle hues still disappear.
    <a href="../shadow-coverage/">See the local shadow experiment on posts 30 and 31, plus these 12 scenes.</a></p>
    <nav><button data-filter="all" aria-pressed="true">All 12</button><button data-filter="Nature" aria-pressed="false">Nature</button><button data-filter="Buildings" aria-pressed="false">Buildings</button></nav>'''
    script = '''<script>document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{
    document.querySelectorAll('[data-filter]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
    document.querySelectorAll('article').forEach(a=>a.hidden=b.dataset.filter!=='all'&&a.dataset.group!==b.dataset.filter);
    }));</script></body></html>'''
    (root/"index.html").write_text(overview+"".join(cards)+script)
    (root/"report.md").write_text(Path(__file__).with_name("SCENE_REVIEW.md").read_text())


if __name__ == "__main__":
    main()
