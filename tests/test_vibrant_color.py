import unittest

import numpy as np
from PIL import Image, ImageDraw

from drawing.contour_engine import ContourEngine, _atlas
from drawing.vibrant_color import RIBBONS, color_plan, vibrant_underlay


class VibrantColorTests(unittest.TestCase):
    def scene(self):
        image = Image.new("RGB", (240, 160), "white")
        draw = ImageDraw.Draw(image)
        for i, color in enumerate(((139, 166, 59), (38, 100, 42), (195, 48, 40),
                                   (27, 98, 182), (178, 40, 123), (16, 136, 130))):
            x, y = 8+(i % 3)*80, 8+(i // 3)*80
            draw.rectangle((x, y, x+62, y+62), fill=color)
        return image

    def test_yellow_green_leaves_choose_green_ribbons_including_shadows(self):
        for hue in (64, 78, 95, 120):
            for value in (90, 150, 210):
                source = Image.new("HSV", (80, 80), (round(hue/360*255), 125, value)).convert("RGB")
                labels, *_ = color_plan(source, 160, 160)
                names = {list(RIBBONS)[i] for i in np.unique(labels) if i >= 0}
                self.assertTrue(names)
                self.assertTrue(names <= {"leaf_green", "green"}, (hue, value, names))

    def test_multiple_local_object_colors_survive_without_global_top_three(self):
        chars, masks = _atlas("classic")
        _, meta = vibrant_underlay(self.scene(), 480, 320, np.array([248, 246, 240]), chars, masks)
        self.assertTrue({"leaf_green", "green", "vermilion", "blue", "magenta", "teal"} <= set(meta["ribbons"]))
        # Every colored object has a substantial body of impressions.
        counts = np.zeros(6, dtype=int)
        for _, x, y, _, _ in meta["color_strikes"]:
            counts[min(y//160, 1)*3 + min(x//160, 2)] += 1
        self.assertTrue(np.all(counts > 100), counts)

    def test_neutrals_dark_casts_and_isolated_specks_stay_uncolored(self):
        chars, masks = _atlas("classic")
        sources = [Image.new("RGB", (160, 120), color) for color in (
            "white", (120, 120, 120), (30, 25, 12), (15, 25, 39))]
        specks = Image.new("RGB", (160, 120), "white")
        draw = ImageDraw.Draw(specks)
        for y in (24, 60, 96):
            for x in (24, 60, 96, 132):
                draw.rectangle((x, y, x+2, y+2), fill=(220, 40, 20))
        for source in [*sources, specks]:
            _, meta = vibrant_underlay(source, 160, 120, np.array([248, 246, 240]), chars, masks)
            self.assertFalse(meta["color_strikes"])

    def test_every_ink_pixel_can_be_replayed_from_real_glyphs(self):
        chars, masks = _atlas("classic")
        paper = np.array([248, 246, 240], dtype=np.float32)
        pixels, meta = vibrant_underlay(self.scene(), 240, 160, paper, chars, masks)
        replay = np.empty((184, 260, 3), dtype=np.float32)
        replay[:] = paper
        for strike in [*meta["hatch_strikes"], *meta["color_strikes"]]:
            ch, x, y, strength = strike[:4]
            self.assertGreater(strength, 0)
            self.assertLessEqual(strength, 1)
            pigment = RIBBONS[strike[4]] if len(strike) == 5 else (28, 22, 18)
            transmission = np.clip(np.asarray(pigment, dtype=np.float32)/paper, 0, 1)
            replay[y:y+24, x:x+20] *= 1-masks[chars.index(ch), :, :, None]*strength*(1-transmission)
        np.testing.assert_allclose(pixels, replay[12:172, 10:250], atol=.0001)

    def test_amount_and_export_keep_the_same_black_drawing(self):
        engine = ContourEngine()
        outputs = [engine.convert(self.scene(), columns=40, scale=1,
            color_mode="vibrant", color_amount=value) for value in (0, .37, 1)]
        (none, a), (part, b), (full, c) = outputs
        expected = np.rint(np.asarray(none, dtype=np.float32)*.63 + np.asarray(full, dtype=np.float32)*.37)
        np.testing.assert_array_equal(np.asarray(part), expected.astype(np.uint8))
        _, export = engine.convert(self.scene(), columns=40, scale=2,
            color_mode="vibrant", color_amount=.37)
        for key in ("strikes", "hatch_strikes"):
            self.assertEqual(a[key], b[key])
            self.assertEqual(a[key], c[key])
            self.assertEqual(a[key], export[key])
        self.assertEqual(b["color_strikes"], c["color_strikes"])
        self.assertEqual(b["color_strikes"], export["color_strikes"])


if __name__ == "__main__":
    unittest.main()
