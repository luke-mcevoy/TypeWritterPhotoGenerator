import unittest

import numpy as np
from PIL import Image, ImageDraw

from experiments.contour_engine import ContourEngine


class ColorAmountTests(unittest.TestCase):
    def source(self):
        source = Image.new("RGB", (100, 80), "white")
        draw = ImageDraw.Draw(source)
        draw.rectangle((8, 8, 45, 70), fill=(25, 85, 195))
        draw.rectangle((60, 20, 92, 60), fill=(220, 140, 15))
        draw.line((10, 65, 40, 15), fill=(10, 18, 30), width=4)
        return source

    def test_amount_fades_color_with_an_identical_black_strike_plan(self):
        engine = ContourEngine()
        for mode in ("ribbon", "layered"):
            results = [engine.convert(self.source(), columns=40, scale=1,
                color_mode=mode, color_amount=amount) for amount in (0, .5, 1)]
            (none, a), (half, b), (full, c) = results
            expected = np.rint((np.asarray(none, dtype=np.float32)+np.asarray(full, dtype=np.float32))/2)
            np.testing.assert_array_equal(np.asarray(half), expected.astype(np.uint8))
            self.assertNotEqual(none.tobytes(), full.tobytes())
            self.assertEqual(a["strikes"], c["strikes"])
            self.assertEqual(a.get("hatch_strikes", []), c.get("hatch_strikes", []))
            self.assertEqual(b["color_strikes"], c["color_strikes"])
            self.assertEqual(a["color_strikes"], [])
            if mode == "layered":
                self.assertTrue(a["hatch_strikes"])

    def test_grayscale_shadows_do_not_change_with_color_amount(self):
        engine = ContourEngine()
        source = self.source().convert("L")
        zero, _ = engine.convert(source, columns=40, scale=1, color_mode="layered", color_amount=0)
        full, meta = engine.convert(source, columns=40, scale=1, color_mode="layered", color_amount=1)
        self.assertEqual(zero.tobytes(), full.tobytes())
        self.assertFalse(meta["ribbons"])

    def test_invalid_amounts_fail_and_finite_out_of_range_values_clamp(self):
        engine = ContourEngine()
        for amount in (float("nan"), float("inf"), -float("inf")):
            with self.assertRaisesRegex(ValueError, "finite"):
                engine.convert(self.source(), columns=40, color_mode="layered", color_amount=amount)
        for amount, expected in ((-2, 0), (4, 1)):
            _, meta = engine.convert(self.source(), columns=40, scale=1,
                color_mode="layered", color_amount=amount)
            self.assertEqual(meta["color_amount"], expected)


if __name__ == "__main__":
    unittest.main()
