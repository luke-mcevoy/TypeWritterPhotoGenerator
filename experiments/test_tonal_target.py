import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from drawing.contour_engine import ContourEngine, drawing_target as old_target
from experiments.tonal_target import drawing_target


class TonalTargetTests(unittest.TestCase):
    def test_flat_black_interior_has_target_and_highlights_stay_unchanged(self):
        for tone in (0, 15, 30):
            photo = Image.new("RGB", (120, 120), (tone, tone, tone))
            self.assertGreater(float(drawing_target(photo, photo.size)[60, 60]), .4)
        for tone in (130, 200, 255):
            photo = Image.new("RGB", (120, 120), (tone, tone, tone))
            np.testing.assert_array_equal(drawing_target(photo, photo.size), old_target(photo, photo.size))

    def test_dark_object_interior_gets_ink_without_marking_white_background(self):
        source = Image.new("RGB", (240, 160), "white")
        ImageDraw.Draw(source).rectangle((70, 35, 170, 125), fill=(12, 12, 12))
        engine = ContourEngine()
        old, _ = engine.convert(source, columns=40, scale=2, color_mode="layered")
        with patch("drawing.contour_engine.drawing_target", drawing_target):
            new, _ = engine.convert(source, columns=40, scale=2, color_mode="vibrant")
        # Both regions lie well inside the source object/background at 400px.
        center = (175, 130, 240, 170)
        self.assertLess(np.asarray(new.crop(center)).mean(), np.asarray(old.crop(center)).mean()-40)
        self.assertEqual(new.crop((30, 30, 65, 60)).tobytes(), old.crop((30, 30, 65, 60)).tobytes())

    def test_black_coverage_is_fixed_across_color_amounts(self):
        photo = Image.new("RGB", (120, 80), (20, 65, 25))
        ImageDraw.Draw(photo).ellipse((35, 15, 90, 70), fill=(8, 8, 8))
        with patch("drawing.contour_engine.drawing_target", drawing_target):
            results = [ContourEngine().convert(photo, columns=40, scale=1,
                color_mode="vibrant", color_amount=amount) for amount in (0, .37, 1)]
        for key in ("strikes", "hatch_strikes"):
            self.assertEqual(results[0][1][key], results[1][1][key])
            self.assertEqual(results[0][1][key], results[2][1][key])
        expected = np.rint(np.asarray(results[0][0], dtype=np.float32)*.63 + np.asarray(results[2][0], dtype=np.float32)*.37)
        np.testing.assert_array_equal(np.asarray(results[1][0]), expected.astype(np.uint8))


if __name__ == "__main__":
    unittest.main()
