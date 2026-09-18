"""Preserve dark subject interiors in the target fitted by real glyphs."""
import numpy as np
from PIL import Image, ImageFilter, ImageOps


def preserve_shadows(image, size, target, simplify=.55, contrast=1.4, amount=1):
    amount = float(np.clip(amount, 0, 1))
    if amount <= 0:
        return np.asarray(target, dtype=np.float32)
    gray = ImageOps.exif_transpose(image).convert("L").resize(size, Image.Resampling.LANCZOS)
    gray = gray.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(1.1))
    luma = np.asarray(gray, dtype=np.float32)/255
    # Local contrast is near zero in both a white cloud and a black bird.
    # An absolute tone floor keeps the bird's body; highlights are unchanged.
    # amount=1 is the original full-body fill; 0 leaves the contour target alone.
    dark = np.clip((.50-luma)/.50, 0, 1)
    floor = .65 * amount * dark**1.25 * contrast/1.25
    floor *= 1-.2*float(np.clip(simplify, 0, 1))
    return np.maximum(target, np.clip(floor, 0, .78)).astype(np.float32)
