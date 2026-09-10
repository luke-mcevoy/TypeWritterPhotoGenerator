"""Copy post images from the local data/posts/ directory into the bucket.

Every file referenced by a post row is uploaded, verified with a HEAD request,
and only then removed from disk so the app switches that post's URLs to the
bucket. Run with --keep to leave the local copies in place.

    python migrate_to_bucket.py [--keep]
"""
import os
import sys

import db
import storage


def main(keep_local: bool) -> None:
    if not storage.enabled():
        raise SystemExit("BUCKET_NAME is not set; nothing to migrate to")
    db.init_db()
    with db.get_db() as conn:
        rows = conn.execute("SELECT id, image_name, source_name FROM posts ORDER BY id").fetchall()

    names = []
    for row in rows:
        for key in ("image_name", "source_name"):
            if row[key]:
                names.append((row["id"], row[key]))

    uploaded = skipped = removed = 0
    for post_id, name in names:
        path = os.path.join(db.POSTS_DIR, name)
        if not os.path.exists(path):
            if storage.exists_remote(name):
                skipped += 1
                print(f"p/{post_id}  {name}  already in bucket")
            else:
                print(f"p/{post_id}  {name}  MISSING locally and remotely", file=sys.stderr)
            continue
        with open(path, "rb") as f:
            storage.put_bytes(name, f.read(), "image/jpeg")
        if not storage.exists_remote(name):
            print(f"p/{post_id}  {name}  upload could not be verified; keeping local", file=sys.stderr)
            continue
        uploaded += 1
        print(f"p/{post_id}  {name}  -> {storage.public_url(name)}")
        if not keep_local:
            os.remove(path)
            removed += 1

    leftovers = [n for n in os.listdir(db.POSTS_DIR)] if os.path.isdir(db.POSTS_DIR) else []
    print(f"\nuploaded {uploaded}, already present {skipped}, removed locally {removed}")
    if leftovers:
        print(f"{len(leftovers)} file(s) left in {db.POSTS_DIR} (not referenced by any post or kept): {leftovers}")


if __name__ == "__main__":
    main(keep_local="--keep" in sys.argv[1:])
