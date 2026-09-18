"""Local candidate: preserve broad dark shapes with fitted character strikes.

The shipped contour target is deliberately sensitive to edges and local
contrast. A uniform black object consequently has almost no interior target.
This experiment adds an absolute shadow floor, leaving highlights alone.
"""
from drawing.contour_engine import drawing_target as contour_target
from drawing.shadow_tone import preserve_shadows


def drawing_target(image, size, simplify=.55, contrast=1.4):
    target = contour_target(image, size, simplify, contrast)
    return preserve_shadows(image, size, target, simplify, contrast)
