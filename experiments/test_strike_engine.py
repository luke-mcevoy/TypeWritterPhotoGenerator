"""Behavior checks for the experimental ink fitter; no production changes."""

import unittest

import numpy as np
from PIL import Image

from experiments.strike_engine import StrikeEngine, _bank, _features, _fit


class StrikeTests(unittest.TestCase):
    def test_float64_input_features_are_finite_and_equivalent(self):
        # Pillow's explicit F mode must never reinterpret float64 buffer bytes.
        tiles = np.random.default_rng(4).random((10, 8, 6))
        actual = _features(tiles)
        self.assertTrue(np.isfinite(actual).all())
        np.testing.assert_allclose(actual, _features(tiles.astype(np.float32)))

    def test_white_paper_is_blank_for_every_seed_and_overstrike_level(self):
        for level in (0, 1, 2):
            for seed in (1, 7, 32):
                _, meta = StrikeEngine().convert(Image.new("L", (80, 80), 255),
                    columns=40, scale=1, overstrike=level, seed=seed)
                self.assertFalse(meta["text"].strip())
                self.assertEqual(meta["overstrike_cells"], 0)

    def test_tone_ramp_is_monotone_and_tracks_printable_ink(self):
        tiles, features, keys, _, _ = _bank("portrait", .9, 1)
        density = tiles.mean(axis=(1, 2))
        targets = np.linspace(0, float(density.max()) * .9, 32, dtype=np.float32)
        patches = np.broadcast_to(targets[:, None, None], (32, 8, 6))
        chosen, pressure = _fit(_features(patches), features, keys, 7, 1)
        actual = density[chosen] * pressure
        self.assertTrue(np.all(np.diff(actual) >= -.003))
        self.assertLess(float(np.max(np.abs(actual - targets))), .02)

    def test_preview_and_export_choose_same_keys_and_repeat_exactly(self):
        arr = np.tile(np.linspace(0, 255, 80).astype(np.uint8), (70, 1))
        source = Image.fromarray(arr)
        engine = StrikeEngine()
        first, a = engine.convert(source, columns=40, scale=1, fast=True)
        repeat, b = engine.convert(source, columns=40, scale=1, fast=True)
        _, c = engine.convert(source, columns=40, scale=2, fast=False)
        self.assertEqual(first.tobytes(), repeat.tobytes())
        self.assertEqual(a["text"], b["text"])
        self.assertEqual(a["text"], c["text"])
        self.assertEqual(a["overstrike_cells"], c["overstrike_cells"])

    def test_no_overstrike_means_single_keys_only(self):
        _, meta = StrikeEngine().convert(Image.new("L", (80, 80), 0),
                                         columns=40, scale=1, overstrike=0)
        self.assertEqual(meta["overstrike_cells"], 0)
        self.assertTrue(meta["text"].strip())


if __name__ == "__main__":
    unittest.main()
