import unittest
from collections import Counter

import numpy as np
from PIL import Image, ImageDraw

from drawing.contour_engine import ContourEngine, _atlas
from drawing.illustration import illustration_plan, illustrated_underlay
from drawing.vibrant_color import RIBBONS


class IllustrationTests(unittest.TestCase):
    def scene(self):
        source = Image.new("RGB", (240, 160), "white")
        draw = ImageDraw.Draw(source)
        draw.rectangle((10, 15, 75, 145), fill=(55, 135, 25))
        draw.rectangle((90, 15, 150, 145), fill=(200, 45, 40))
        draw.ellipse((166, 15, 230, 145), fill=(8, 8, 8))
        return source

    def test_direction_is_measured_from_structure(self):
        for vertical, expected in ((True, 3), (False, 1)):
            source = Image.new("RGB", (240, 240), "white")
            draw = ImageDraw.Draw(source)
            for position in range(12, 240, 24):
                box = (position, 0, position+8, 240) if vertical else (0, position, 240, position+8)
                draw.rectangle(box, fill=(90, 90, 90))
            plan = illustration_plan(source, 240, 240)
            self.assertGreater(float(np.mean(plan["families"][5:-5, 5:-5] == expected)), .9)

    def test_deep_shadow_has_body_but_paper_stays_blank(self):
        source = self.scene()
        plan = illustration_plan(source, 240, 160)
        self.assertGreater(float(plan["target"][50:110, 180:214].mean()), .5)
        self.assertEqual(float(plan["target"][:5].max()), 0)
        no_fill = illustration_plan(source, 240, 160, shadow_fill=0)
        self.assertGreater(float(plan["target"][80, 200]), float(no_fill["target"][80, 200]))
        page, _ = ContourEngine().convert(source, columns=40, color_mode="illustrated", color_amount=0)
        margin = max(20, round(400*.035))
        black_body = np.asarray(page)[margin+95:margin+170, margin+306:margin+346]
        self.assertLess(float(black_body.mean()), 170)

    def test_colored_ink_is_entirely_replayable_glyphs(self):
        chars, masks = _atlas("classic")
        paper = np.array([248, 246, 240], np.float32)
        actual, meta = illustrated_underlay(self.scene(), 240, 160, paper, chars, masks)
        replay = np.empty((184, 260, 3), np.float32)
        replay[:] = paper
        self.assertTrue({"green", "vermilion"} <= set(meta["ribbons"]))
        for ch, x, y, strength, ribbon in meta["color_strikes"]:
            self.assertTrue(0 < strength <= 1)
            transmission = np.clip(np.array(RIBBONS[ribbon], np.float32)/paper, 0, 1)
            replay[y:y+24, x:x+20] *= 1-masks[chars.index(ch), :, :, None]*strength*(1-transmission)
        np.testing.assert_allclose(actual, replay[12:172, 10:250], atol=.0001)

    def test_color_amount_export_and_repeatability_share_one_drawing(self):
        engine = ContourEngine()
        outputs = [engine.convert(self.scene(), columns=40, scale=1,
            color_mode="illustrated", color_amount=amount, include_color_endpoints=True)
            for amount in (0, .37, 1)]
        (mono, a), (part, b), (full, c) = outputs
        expected = np.rint(np.asarray(mono, np.float32)*.63 + np.asarray(full, np.float32)*.37)
        np.testing.assert_array_equal(np.asarray(part), expected.astype(np.uint8))
        again, repeat = engine.convert(self.scene(), columns=40, scale=1,
            color_mode="illustrated", color_amount=.37)
        self.assertEqual(part.tobytes(), again.tobytes())
        _, large = engine.convert(self.scene(), columns=40, scale=3, color_mode="illustrated")
        for meta in (a, c, repeat, large):
            self.assertEqual(b["strikes"], meta["strikes"])
        self.assertEqual(b["color_strikes"], large["color_strikes"])
        self.assertEqual(mono.tobytes(), b["color_endpoints"][0].tobytes())
        self.assertEqual(full.tobytes(), b["color_endpoints"][1].tobytes())

    def test_neutral_photos_stay_neutral_and_progress_is_monotonic(self):
        calls = []
        _, meta = ContourEngine().convert(self.scene().convert("L"), columns=40,
            color_mode="illustrated", progress=lambda fraction, label: calls.append(fraction))
        self.assertFalse(meta["color_strikes"])
        self.assertEqual(calls, sorted(calls))

    def test_bright_colored_objects_keep_substantial_ribbon_ink(self):
        source = Image.new("RGB", (240, 160), "white")
        ImageDraw.Draw(source).rectangle((50, 30, 190, 130), fill=(240, 190, 20))
        chars, masks = _atlas("classic")
        pixels, _ = illustrated_underlay(source, 240, 160, np.array([248, 246, 240], np.float32), chars, masks)
        interior = pixels[50:110, 70:170]
        # A bright yellow object must have visible pigment, not just isolated
        # pale punctuation; highlights outside the object remain paper.
        self.assertGreater(float((interior[:, :, 0]-interior[:, :, 2]).mean()), 20)
        self.assertTrue(np.all(pixels[:12] == [248, 246, 240]))

    def test_one_character_does_not_dominate_a_colored_surface(self):
        source = Image.new("RGB", (300, 200), (85, 145, 28))
        _, meta = ContourEngine().convert(source, columns=40, color_mode="illustrated")
        counts = Counter(strike[0] for strike in meta["color_strikes"])
        self.assertGreater(len(counts), 15)
        self.assertLess(max(counts.values())/sum(counts.values()), .15)


if __name__ == "__main__":
    unittest.main()
