import unittest

import numpy as np
from PIL import Image, ImageDraw

from experiments.contour_engine import ContourEngine, _atlas
from experiments.ribbon_color import RIBBONS, color_underlay


class RibbonTests(unittest.TestCase):
    def source(self):
        image = Image.new("RGB", (100, 100), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((15, 10, 50, 85), fill=(20, 100, 220))
        draw.ellipse((55, 25, 90, 75), fill=(220, 130, 10))
        return image

    def test_zero_amount_exactly_preserves_monochrome(self):
        engine = ContourEngine()
        mono, _ = engine.convert(self.source(), columns=40, scale=1)
        zero, meta = engine.convert(self.source(), columns=40, scale=1,
                                   color_mode="ribbon", color_amount=0)
        self.assertEqual(mono.tobytes(), zero.tobytes())
        self.assertEqual(meta["color_strikes"], [])

    def test_grayscale_has_no_spurious_color(self):
        engine = ContourEngine()
        source = self.source().convert("L")
        mono, _ = engine.convert(source, columns=40, scale=1)
        color, meta = engine.convert(source, columns=40, scale=1, color_mode="ribbon")
        self.assertEqual(mono.tobytes(), color.tobytes())
        self.assertEqual(meta["ribbons"], [])

    def test_color_preserves_black_strikes_and_is_reproducible(self):
        engine = ContourEngine()
        mono, mono_meta = engine.convert(self.source(), columns=40, scale=1)
        color, meta = engine.convert(self.source(), columns=40, scale=1, color_mode="ribbon")
        repeat, repeated = engine.convert(self.source(), columns=40, scale=1, color_mode="ribbon")
        self.assertEqual(meta["strikes"], mono_meta["strikes"])
        self.assertEqual(color.tobytes(), repeat.tobytes())
        self.assertNotEqual(color.tobytes(), mono.tobytes())
        self.assertGreater(len(meta["color_strikes"]), 0)
        self.assertLessEqual(len(meta["ribbons"]), 3)
        self.assertTrue(set(meta["ribbons"]).issubset(RIBBONS))

    def test_all_colored_pixels_are_covered_by_recorded_glyphs(self):
        chars, masks = _atlas("classic")
        paper = np.array([248, 246, 240], dtype=np.float32)
        pixels, meta = color_underlay(self.source(), 100, 100, paper, chars, masks, amount=1)
        support = np.zeros((124, 120), dtype=bool)
        for ch, x, y, strength, ribbon in meta["color_strikes"]:
            support[y:y+24, x:x+20] |= masks[chars.index(ch)] > 0
        changed = np.any(pixels != paper, axis=-1)
        self.assertTrue(changed.any())
        self.assertFalse(np.any(changed & ~support[12:112, 10:110]))


if __name__ == "__main__":
    unittest.main()
