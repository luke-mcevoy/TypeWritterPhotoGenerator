"""Reprint a saved post from its source photograph (local disk or bucket)."""
import io
import os
import sys
import urllib.request

import db
import storage
from PIL import Image
from typewriter_engine import TypewriterEngine


def load_source(name: str) -> Image.Image:
    path = os.path.join(db.POSTS_DIR, name)
    if os.path.exists(path):
        return Image.open(path).convert("RGB")
    with urllib.request.urlopen(storage.public_url(name)) as resp:
        return Image.open(io.BytesIO(resp.read())).convert("RGB")


def reprint(post_id: int) -> str:
    db.init_db()
    row = db.get_post(post_id)
    if row is None:
        raise SystemExit(f"No post {post_id}")
    if not row["source_name"]:
        raise SystemExit(f"Post {post_id} has no source photograph")
    source = load_source(row["source_name"])
    page, _meta = TypewriterEngine().convert(source, columns=180, scale=2, fast=False)
    if max(page.size) > 4800:
        page = page.copy()
        page.thumbnail((4800, 4800), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    page.save(buf, format="JPEG", quality=95, subsampling=0)
    storage.put_bytes(row["image_name"], buf.getvalue(), "image/jpeg")
    where = storage.public_url(row["image_name"]) if storage.enabled() else row["image_name"]
    return f"{page.size[0]}x{page.size[1]} -> {where}"


if __name__ == "__main__":
    print(reprint(int(sys.argv[1])))
