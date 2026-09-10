import unittest

import numpy as np
from PIL import Image, ImageDraw

from experiments.contour_engine import ContourEngine


class ContourTests(unittest.TestCase):
    def test_blank_white_has_no_strikes(self):
        _, meta = ContourEngine().convert(Image.new("L", (80, 80), 255), columns=40)
        self.assertEqual(meta["strike_count"], 0)

    def test_silhouette_receives_directional_keys_and_is_reproducible(self):
        source = Image.new("L", (100, 100), 255)
        ImageDraw.Draw(source).rectangle((30, 20, 70, 80), fill=0)
        first, a = ContourEngine().convert(source, columns=40, seed=7, scale=1)
        second, b = ContourEngine().convert(source, columns=40, seed=7, scale=2)
        self.assertTrue(any(ch == "|" for ch, *_ in a["strikes"]))
        self.assertTrue(any(ch == "-" for ch, *_ in a["strikes"]))
        self.assertEqual(a["strikes"], b["strikes"])
        self.assertGreater(second.width, first.width)

    def test_unprintable_extreme_aspect_is_rejected(self):
        with self.assertRaises(ValueError):
            ContourEngine().convert(Image.new("L", (2, 1000)), columns=240)


if __name__ == "__main__":
    unittest.main()
