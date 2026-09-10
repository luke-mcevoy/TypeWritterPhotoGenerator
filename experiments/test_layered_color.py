import unittest

import numpy as np
from PIL import Image, ImageDraw

from experiments.contour_engine import ContourEngine, _atlas
from experiments.layered_color import layered_underlay


class LayeredColorTests(unittest.TestCase):
    def scene(self):
        image = Image.new("RGB", (160, 120), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((12, 12, 68, 106), fill=(30, 96, 178))
        draw.rectangle((90, 22, 148, 98), fill=(225, 158, 30))
        draw.line((16, 85, 60, 24), fill=(10, 20, 38), width=5)
        return image

    def test_zero_color_and_hatching_preserve_the_original(self):
        engine = ContourEngine()
        for source, amount in [(self.scene(), 0), (Image.new("RGB", (80, 80), "white"), .7)]:
            mono, _ = engine.convert(source, columns=40, scale=1)
            refined, meta = engine.convert(source, columns=40, scale=1,
                color_mode="layered", color_amount=amount, hatch_amount=0)
            self.assertEqual(mono.tobytes(), refined.tobytes())
            self.assertFalse(meta["color_strikes"])
            self.assertFalse(meta.get("hatch_strikes", []))

    def test_refinement_plan_is_stable_across_export_sizes(self):
        engine = ContourEngine()
        small, a = engine.convert(self.scene(), columns=40, scale=1, color_mode="layered")
        _, b = engine.convert(self.scene(), columns=40, scale=2, color_mode="layered")
        repeat, c = engine.convert(self.scene(), columns=40, scale=1, color_mode="layered")
        for key in ("strikes", "color_strikes", "hatch_strikes", "ribbons"):
            self.assertEqual(a[key], b[key])
            self.assertEqual(a[key], c[key])
        self.assertEqual(small.tobytes(), repeat.tobytes())
        self.assertGreater(len(a["color_strikes"]), 0)
        self.assertGreater(len(a["hatch_strikes"]), 0)
        self.assertLessEqual(len(a["ribbons"]), 3)

    def test_added_ink_is_fully_explained_by_recorded_glyphs(self):
        chars, masks = _atlas("classic")
        paper = np.array([248, 246, 240], dtype=np.float32)
        pixels, meta = layered_underlay(self.scene(), 160, 120, paper, chars, masks)
        support = np.zeros((144, 180), dtype=bool)
        for strike in meta["color_strikes"] + meta["hatch_strikes"]:
            ch, x, y, strength = strike[:4]
            self.assertGreater(strength, 0)
            self.assertLessEqual(strength, 1)
            support[y:y+24, x:x+20] |= masks[chars.index(ch)] > 0
        changed = np.any(pixels != paper, axis=-1)
        self.assertTrue(changed.any())
        self.assertFalse(np.any(changed & ~support[12:132, 10:170]))
        self.assertTrue(np.isfinite(pixels).all())
        self.assertGreaterEqual(float(pixels.min()), 0)
        self.assertLessEqual(float(pixels.max()), 255)

    def test_isolated_color_specks_do_not_become_accents(self):
        source = Image.new("RGB", (160, 120), "white")
        draw = ImageDraw.Draw(source)
        for y in (24, 60, 96):
            for x in (24, 60, 96, 132):
                draw.rectangle((x, y, x+2, y+2), fill=(220, 40, 20))
        chars, masks = _atlas("classic")
        _, meta = layered_underlay(source, 160, 120,
            np.array([248, 246, 240], dtype=np.float32), chars, masks)
        self.assertFalse(meta["color_strikes"])

    def test_grayscale_has_only_black_hatching(self):
        _, meta = ContourEngine().convert(self.scene().convert("L"),
            columns=40, scale=1, color_mode="layered")
        self.assertFalse(meta["ribbons"])
        self.assertFalse(meta["color_strikes"])
        self.assertTrue(meta["hatch_strikes"])


if __name__ == "__main__":
    unittest.main()
