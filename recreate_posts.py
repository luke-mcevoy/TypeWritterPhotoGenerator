"""Apply reviewed reprints using new immutable image names; retain originals.

Usage: python recreate_posts.py apply /app/data/reprints/RUN/manifest.json
       python recreate_posts.py restore /app/data/reprints/RUN/manifest.json
The manifest and reviewed JPEGs are prepared locally before deployment.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import db
import storage


def apply_manifest(path, restore=False):
    path = Path(path)
    manifest = json.loads(path.read_text())
    posts = manifest["posts"]
    ids = [p["id"] for p in posts]
    if not posts or len(set(ids)) != len(ids) or any(type(i) is not int for i in ids):
        raise ValueError("Expected distinct numeric post IDs")
    for post in posts:
        for key in ("old_name", "new_name", "source_name"):
            if not re.fullmatch(r"[a-f0-9]{32}\.jpg", post[key]):
                raise ValueError(f"Invalid {key}")
        if post["old_name"] == post["new_name"]:
            raise ValueError("Reprints must use new immutable image names")
        if not restore:
            data = (path.parent/post["new_name"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != post["sha256"]:
                raise ValueError(f"Reviewed image changed for post {post['id']}")
    old_key, new_key = ("new_name", "old_name") if restore else ("old_name", "new_name")

    def check_rows(conn):
        rows = [conn.execute("SELECT image_name, source_name FROM posts WHERE id = ?", (p["id"],)).fetchone() for p in posts]
        if any(row is None or row["source_name"] != post["source_name"] for row, post in zip(rows, posts)):
            raise RuntimeError("A post/source changed since review; nothing was replaced")
        if all(row["image_name"] == post[new_key] for row, post in zip(rows, posts)):
            return False
        if any(row["image_name"] != post[old_key] for row, post in zip(rows, posts)):
            raise RuntimeError("A drawing changed since review; nothing was replaced")
        return True

    # Preflight before uploading; recheck under a write transaction afterwards.
    with db.get_db() as conn:
        if not check_rows(conn):
            return {"status": "already restored" if restore else "already applied", "posts": ids}
    if not restore:
        for post in posts:
            storage.put_bytes(post["new_name"], (path.parent/post["new_name"]).read_bytes(), "image/jpeg")
    with db.get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if check_rows(conn):
            for post in posts:
                conn.execute("UPDATE posts SET image_name = ? WHERE id = ?", (post[new_key], post["id"]))
    # Original bucket objects and local backups are intentionally retained.
    return {"status": "restored" if restore else "applied", "posts": ids,
            "images": [storage.public_url(p[new_key]) if storage.enabled() else p[new_key] for p in posts]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("apply", "restore"))
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    print(json.dumps(apply_manifest(args.manifest, restore=args.action == "restore")))
