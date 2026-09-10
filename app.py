import base64
import io
import os
import re
import secrets
import uuid
from functools import wraps

from flask import (
    Flask,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from PIL import Image, ImageOps
from werkzeug.exceptions import RequestEntityTooLarge

import db
import storage
from typewriter_engine import TypewriterEngine

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
engine = TypewriterEngine()

MAX_IMAGE_DIMENSION = 4096
USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,23}$")


def _secret_key() -> str:
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    db.ensure_dirs()
    path = os.path.join(db.DATA_DIR, "secret.key")
    if os.path.exists(path):
        return open(path, encoding="utf-8").read().strip()
    key = secrets.token_hex(32)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(key)
    return key


app.secret_key = _secret_key()
db.init_db()


@app.errorhandler(RequestEntityTooLarge)
def too_large(_e):
    return jsonify({"error": "That file is too large"}), 413


@app.before_request
def load_user():
    g.user = None
    uid = session.get("user_id")
    if uid:
        g.user = db.get_user_by_id(uid)
        if g.user is None:
            session.clear()


@app.context_processor
def inject_user():
    return {"current_user": g.user, "invite_required": bool(os.environ.get("CARRIAGE_INVITE"))}


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if g.user is None:
            if request.is_json or request.headers.get("X-Requested-With") == "fetch":
                return jsonify({"error": "Sign in to post", "login": True}), 401
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)

    return wrapped


def public_user(row) -> dict:
    return {"id": row["id"], "username": row["username"], "display_name": row["display_name"]}


def serialize_post(row) -> dict:
    liked = bool(row["liked"]) if "liked" in row.keys() else False
    has_source = bool(row["source_name"]) if "source_name" in row.keys() else False
    return {
        "id": row["id"],
        "caption": row["caption"],
        "username": row["username"],
        "display_name": row["display_name"],
        "created_at": row["created_at"],
        "like_count": row["like_count"],
        "liked": liked,
        "image_url": media_url(row["image_name"], "post_image", row["id"]),
        "source_url": media_url(row["source_name"], "post_source", row["id"]) if has_source else None,
        "url": url_for("show_post", post_id=row["id"]),
        "profile_url": url_for("profile", username=row["username"]),
        "own": bool(g.user and g.user["username"] == row["username"]),
    }


def media_url(name: str | None, endpoint: str, post_id: int) -> str:
    """Public bucket URL when the object lives there, else the Flask route (local dev / legacy)."""
    if name and storage.enabled() and not os.path.exists(os.path.join(db.POSTS_DIR, name)):
        return storage.public_url(name)
    return url_for(endpoint, post_id=post_id)


def save_pil_image(image: Image.Image, max_side: int, quality: int) -> str:
    image = ImageOps.exif_transpose(image).convert("RGB")
    if max(image.size) > max_side:
        image = image.copy()
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    name = f"{uuid.uuid4().hex}.jpg"
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality, subsampling=0)
    storage.put_bytes(name, buf.getvalue(), "image/jpeg")
    return name


def save_posted_image(data_url: str, max_side: int, quality: int) -> str:
    if not data_url.startswith("data:image/"):
        raise ValueError("not an image")
    _header, b64 = data_url.split(",", 1)
    image = Image.open(io.BytesIO(base64.b64decode(b64)))
    return save_pil_image(image, max_side, quality)


def load_request_image() -> Image.Image:
    if "image" not in request.files:
        raise ValueError("No image provided")
    file = request.files["image"]
    if not file or (file.filename == "" and not file.content_type):
        raise ValueError("No image selected")
    image = ImageOps.exif_transpose(Image.open(file.stream)).convert("RGB")
    if max(image.size) > MAX_IMAGE_DIMENSION:
        image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.LANCZOS)
    return image


def settings_from_request() -> dict:
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
    except (TypeError, ValueError) as e:
        raise ValueError("Invalid numeric setting") from e
    return {
        "columns": columns,
        "charset": request.form.get("charset", request.form.get("theme", "portrait")),
        "paper": request.form.get("paper", "cream"),
        "ink": request.form.get("ink", request.form.get("bg_color", "blue_black")),
        "contrast": contrast,
        "brightness": brightness,
        "detail": detail,
        "simplify": simplify,
        "overstrike": overstrike,
        "tightness": tightness,
        "wander": wander,
        "pressure": pressure,
        "scale": scale,
        "inscription": request.form.get("inscription", "")[:240],
        "invert": request.form.get("invert", "0") in ("1", "true", "on"),
    }


def render_drawing(image: Image.Image, preview: bool = False) -> tuple[Image.Image, dict]:
    settings = settings_from_request()
    scale = 1 if preview else 2
    if not preview and max(image.size) > 2000:
        image = image.copy()
        image.thumbnail((2000, 2000), Image.Resampling.BILINEAR)
    settings["columns"] = min(settings["columns"], 200)
    rendered, meta = engine.convert(
        image,
        columns=settings["columns"],
        charset=settings["charset"],
        paper=settings["paper"],
        ink=settings["ink"],
        contrast=settings["contrast"],
        brightness=settings["brightness"],
        detail=settings["detail"],
        simplify=settings["simplify"],
        overstrike=settings["overstrike"],
        tightness=settings["tightness"],
        wander=settings["wander"],
        pressure=settings["pressure"],
        scale=scale,
        inscription=settings["inscription"],
        invert=settings["invert"],
        fast=True,
    )
    if preview and max(rendered.size) > 900:
        rendered = rendered.copy()
        rendered.thumbnail((900, 900), Image.Resampling.BILINEAR)
    elif not preview and max(rendered.size) > 3200:
        rendered = rendered.copy()
        rendered.thumbnail((3200, 3200), Image.Resampling.LANCZOS)
    return rendered, meta


MAX_POST_SIDE = 4800
MAX_SOURCE_SIDE = 2400


@app.route("/")
def wall():
    posts = [serialize_post(p) for p in db.list_posts(viewer_id=g.user["id"] if g.user else None)]
    return render_template("wall.html", posts=posts)


@app.route("/studio")
def studio():
    return render_template("index.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if g.user:
        return redirect(url_for("wall"))
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        display_name = (request.form.get("display_name") or "").strip()
        password = request.form.get("password") or ""
        invite = (request.form.get("invite") or "").strip()
        expected = os.environ.get("CARRIAGE_INVITE", "")
        if expected and invite != expected:
            error = "That family word is not right."
        elif not USERNAME_RE.match(username):
            error = "Username: start with a letter, 3–24 letters, numbers, or _."
        elif not display_name or len(display_name) > 40:
            error = "Please give a name (up to 40 characters)."
        elif len(password) < 6:
            error = "Password needs at least 6 characters."
        elif db.get_user_by_username(username):
            error = "That username is already taken."
        else:
            user = db.create_user(username, display_name, password)
            session["user_id"] = user["id"]
            dest = request.args.get("next") or url_for("studio")
            if not dest.startswith("/"):
                dest = url_for("studio")
            return redirect(dest)
    return render_template("auth.html", mode="signup", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("wall"))
    error = None
    if request.method == "POST":
        user = db.verify_login(
            (request.form.get("username") or "").strip(),
            request.form.get("password") or "",
        )
        if not user:
            error = "Username or password is wrong."
        else:
            session["user_id"] = user["id"]
            dest = request.args.get("next") or url_for("wall")
            if not dest.startswith("/"):
                dest = url_for("wall")
            return redirect(dest)
    return render_template("auth.html", mode="login", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("wall"))


@app.route("/u/<username>")
def profile(username):
    user = db.get_user_by_username(username)
    if user is None:
        return render_template("missing.html", message="No one by that name."), 404
    posts = [
        serialize_post(p)
        for p in db.list_posts(viewer_id=g.user["id"] if g.user else None, username=username)
    ]
    return render_template(
        "profile.html",
        profile=public_user(user),
        posts=posts,
        count=db.post_count(user["id"]),
    )


@app.route("/p/<int:post_id>")
def show_post(post_id):
    row = db.get_post(post_id, viewer_id=g.user["id"] if g.user else None)
    if row is None:
        return render_template("missing.html", message="That page is gone."), 404
    return render_template("post.html", post=serialize_post(row))


@app.route("/media/posts/<int:post_id>")
def post_image(post_id):
    row = db.get_post(post_id)
    if row is None:
        return "Not found", 404
    return serve_media(row["image_name"])


@app.route("/media/posts/<int:post_id>/photo")
def post_source(post_id):
    row = db.get_post(post_id)
    if row is None or not row["source_name"]:
        return "Not found", 404
    return serve_media(row["source_name"])


def serve_media(name: str):
    if os.path.exists(os.path.join(db.POSTS_DIR, name)):
        return send_from_directory(db.POSTS_DIR, name)
    if storage.enabled():
        return redirect(storage.public_url(name), code=302)
    return "Not found", 404


@app.route("/api/posts", methods=["POST"])
@login_required
def api_create_post():
    caption = (request.form.get("caption") or "").strip()
    payload = request.get_json(silent=True) or {}
    if not caption:
        caption = (payload.get("caption") or "").strip()
    if len(caption) > 280:
        return jsonify({"error": "Caption is too long"}), 400

    try:
        if "image" in request.files and request.files["image"]:
            source = load_request_image()
        elif payload.get("source_data"):
            source = ImageOps.exif_transpose(
                Image.open(io.BytesIO(base64.b64decode(payload["source_data"].split(",", 1)[1])))
            ).convert("RGB")
            if max(source.size) > MAX_IMAGE_DIMENSION:
                source.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.LANCZOS)
        else:
            return jsonify({"error": "Send the photograph so the machine can print the page"}), 400
        rendered, _meta = render_drawing(source, preview=False)
        name = save_pil_image(rendered, MAX_POST_SIDE, 95)
        source_name = save_pil_image(source, MAX_SOURCE_SIDE, 90)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Could not print the page: {e}"}), 500

    post_id = db.create_post(g.user["id"], caption, name, source_name)
    row = db.get_post(post_id, viewer_id=g.user["id"])
    return jsonify({"ok": True, "post": serialize_post(row)})


@app.route("/api/posts/<int:post_id>", methods=["DELETE"])
@login_required
def api_delete_post(post_id):
    row = db.delete_post(post_id, g.user["id"])
    if row is None:
        return jsonify({"error": "You can only take down your own page"}), 403
    for key in ("image_name", "source_name"):
        storage.delete(row[key])
    return jsonify({"ok": True})


@app.route("/api/posts/<int:post_id>/like", methods=["POST"])
@login_required
def api_like(post_id):
    if db.get_post(post_id) is None:
        return jsonify({"error": "That page is gone"}), 404
    return jsonify(db.toggle_like(post_id, g.user["id"]))


@app.route("/convert", methods=["POST"])
def convert():
    try:
        image = load_request_image()
    except Exception as e:
        return jsonify({"error": f"Invalid image: {e}"}), 400

    preview = request.form.get("preview", "0") in ("1", "true", "on")
    try:
        rendered, meta = render_drawing(image, preview=preview)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Could not draw the page: {e}"}), 500

    buf = io.BytesIO()
    if preview:
        rendered.save(buf, format="JPEG", quality=62)
        mime = "image/jpeg"
    else:
        rendered.save(buf, format="JPEG", quality=95, subsampling=0)
        mime = "image/jpeg"
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
