import unittest

import numpy as np
from PIL import Image, ImageDraw

from drawing.contour_engine import ContourEngine, drawing_target
from drawing.shadow_tone import preserve_shadows


class ShadowToneTests(unittest.TestCase):
    def test_full_fill_covers_black_and_leaves_highlights(self):
        for tone in (0, 15, 30, 130, 200, 255):
            photo = Image.new("RGB", (100, 100), (tone, tone, tone))
            old = drawing_target(photo, photo.size)
            new = preserve_shadows(photo, photo.size, old, amount=1)
            if tone < 40:
                self.assertGreater(float(new[50, 50]), .4)
            else:
                np.testing.assert_array_equal(new, old)

    def test_zero_fill_matches_the_contour_target(self):
        photo = Image.new("RGB", (80, 80), (8, 8, 8))
        old = drawing_target(photo, photo.size)
        np.testing.assert_array_equal(preserve_shadows(photo, photo.size, old, amount=0), old)

    def test_vibrant_fills_a_black_subject_with_color_turned_off(self):
        source = Image.new("RGB", (240, 160), "white")
        ImageDraw.Draw(source).rectangle((70, 35, 170, 125), fill=(12, 12, 12))
        engine = ContourEngine()
        old, _ = engine.convert(source, columns=40, scale=2, color_mode="layered", color_amount=0)
        new, _ = engine.convert(source, columns=40, scale=2, color_mode="vibrant",
                               color_amount=0, shadow_fill=1)
        center = (175, 130, 240, 170)
        self.assertLess(np.asarray(new.crop(center)).mean(), np.asarray(old.crop(center)).mean()-40)
        self.assertEqual(new.crop((30, 30, 65, 60)).tobytes(), old.crop((30, 30, 65, 60)).tobytes())


if __name__ == "__main__":
    unittest.main()
