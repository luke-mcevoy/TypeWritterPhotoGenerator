import io
import os
import base64

from flask import Flask, render_template, request, jsonify
from PIL import Image, ImageOps

from typewriter_engine import TypewriterEngine

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
engine = TypewriterEngine()

MAX_IMAGE_DIMENSION = 4096


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert():
    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No image selected"}), 400

    try:
        image = ImageOps.exif_transpose(Image.open(file.stream)).convert("RGB")
    except Exception as e:
        return jsonify({"error": f"Invalid image: {e}"}), 400

    if max(image.size) > MAX_IMAGE_DIMENSION:
        image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.LANCZOS)

    try:
        columns = int(request.form.get("columns", request.form.get("width", 180)))
        contrast = float(request.form.get("contrast", 1.4))
        brightness = float(request.form.get("brightness", 0.0))
        detail = float(request.form.get("detail", 0.45))
        simplify = float(request.form.get("simplify", 0.55))
        overstrike = int(request.form.get("overstrike", 1))
        tightness = float(request.form.get("tightness", 0.90))
        wander = float(request.form.get("wander", 0.7))
        pressure = float(request.form.get("pressure", 0.88))
        scale = int(request.form.get("scale", 2))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid numeric setting"}), 400

    charset = request.form.get("charset", request.form.get("theme", "portrait"))
    paper = request.form.get("paper", "cream")
    ink = request.form.get("ink", request.form.get("bg_color", "blue_black"))
    inscription = request.form.get("inscription", "")[:240]
    invert = request.form.get("invert", "0") in ("1", "true", "on")

    preview = request.form.get("preview", "0") in ("1", "true", "on")
    if preview:
        scale = 1

    try:
        rendered, meta = engine.convert(
            image,
            columns=columns,
            charset=charset,
            paper=paper,
            ink=ink,
            contrast=contrast,
            brightness=brightness,
            detail=detail,
            simplify=simplify,
            overstrike=overstrike,
            tightness=tightness,
            wander=wander,
            pressure=pressure,
            scale=scale,
            inscription=inscription,
            invert=invert,
            fast=preview,
        )
    except Exception as e:
        return jsonify({"error": f"Could not draw the page: {e}"}), 500

    if preview and max(rendered.size) > 1280:
        rendered = rendered.copy()
        rendered.thumbnail((1280, 1280), Image.Resampling.BILINEAR)

    buf = io.BytesIO()
    if preview:
        rendered.save(buf, format="JPEG", quality=72)
        mime = "image/jpeg"
    else:
        rendered.save(buf, format="PNG", compress_level=6)
        mime = "image/png"
    buf.seek(0)
    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return jsonify(
        {
            "image_data": f"data:{mime};base64,{img_b64}",
            "html_data": meta["html"],
            "text_data": meta["text"],
            "dimensions": {
                "img_width": rendered.width,
                "img_height": rendered.height,
                "chars_wide": meta["chars_wide"],
                "chars_tall": meta["chars_tall"],
                "overstrike": meta["overstrike"],
            },
        }
    )


@app.route("/health")
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", host="0.0.0.0", port=port)
