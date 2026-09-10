"""Where post images live.

With BUCKET_NAME set (Fly + Tigris), objects go to S3-compatible storage and
are served straight from the bucket's public URL. Without it (local dev),
files are written to data/posts/ and served by Flask as before.
"""

from __future__ import annotations

import os

import db

BUCKET = os.environ.get("BUCKET_NAME", "").strip()
ENDPOINT = os.environ.get("AWS_ENDPOINT_URL_S3", "https://fly.storage.tigris.dev").rstrip("/")
PUBLIC_BASE = os.environ.get("MEDIA_PUBLIC_URL", "").rstrip("/")
PREFIX = "posts/"

_client = None


def enabled() -> bool:
    return bool(BUCKET)


def _s3():
    global _client
    if _client is None:
        import boto3
        from botocore.config import Config

        _client = boto3.client(
            "s3",
            endpoint_url=ENDPOINT,
            region_name=os.environ.get("AWS_REGION", "auto"),
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )
    return _client


def key_for(name: str) -> str:
    return PREFIX + name


def public_url(name: str) -> str:
    if PUBLIC_BASE:
        return f"{PUBLIC_BASE}/{key_for(name)}"
    # Tigris serves public buckets virtual-hosted: https://<bucket>.fly.storage.tigris.dev/<key>
    host = ENDPOINT.split("://", 1)[1]
    return f"https://{BUCKET}.{host}/{key_for(name)}"


def put_bytes(name: str, data: bytes, content_type: str = "image/jpeg") -> None:
    if enabled():
        _s3().put_object(
            Bucket=BUCKET,
            Key=key_for(name),
            Body=data,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
    else:
        db.ensure_dirs()
        with open(os.path.join(db.POSTS_DIR, name), "wb") as f:
            f.write(data)


def delete(name: str) -> None:
    if not name:
        return
    if enabled():
        try:
            _s3().delete_object(Bucket=BUCKET, Key=key_for(name))
        except Exception:
            pass
    path = os.path.join(db.POSTS_DIR, name)
    if os.path.exists(path):
        os.remove(path)


def exists_remote(name: str) -> bool:
    if not enabled():
        return False
    try:
        _s3().head_object(Bucket=BUCKET, Key=key_for(name))
        return True
    except Exception:
        return False
