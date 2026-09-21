"""Export fidelity, exact phone dimensions, and bounded resource use."""
import io
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from drawing.contour_engine import ContourEngine
from drawing.export import MAX_PIXELS, MAX_SIDE, output_size, print_plan
from typewriter_engine import PAPERS, INKS
from test_studio import StudioTests


class PrintPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Image.new("RGB", (160, 120), "white")
        draw = ImageDraw.Draw(source)
        draw.rectangle((5, 5, 65, 115), fill=(30, 90, 25))
        draw.ellipse((60, 20, 150, 100), fill=(210, 40, 30))
        cls.page, cls.meta = ContourEngine().convert(source, columns=40,
            color_mode="vibrant", color_amount=.37, scale=2)

    def test_same_size_replay_preserves_ink_and_paper(self):
        with patch("drawing.export.output_size", return_value=self.page.size):
            replay = print_plan(self.meta, PAPERS["white"], INKS["carbon"], "maximum")
        error = np.abs(np.asarray(replay).astype(int)-np.asarray(self.page).astype(int))
        self.assertLessEqual(error.max(), 1)
        self.assertTrue(np.all(np.asarray(replay)[:20] == PAPERS["white"]))

    def test_exact_phone_sizes_and_bounded_maximum(self):
        self.assertEqual(output_size((800, 600), "phone_tall"), (2160, 4680))
        self.assertEqual(output_size((800, 600), "phone_classic"), (2160, 3840))
        for size in ((400, 400), (1500, 3200), (2000, 800), (300, 4000)):
            width, height = output_size(size, "maximum")
            self.assertLessEqual(width*height, MAX_PIXELS)
            self.assertLessEqual(max(width, height), MAX_SIDE)
            self.assertLess(abs(width/height-size[0]/size[1]), .005)
        with self.assertRaises(ValueError):
            output_size((800, 600), "unlimited")

    def test_phone_framing_preserves_whole_page_or_crops_as_requested(self):
        with patch("drawing.export.output_size", return_value=(216, 468)):
            whole = print_plan(self.meta, PAPERS["white"], INKS["carbon"], "phone_tall")
            fill = print_plan(self.meta, PAPERS["white"], INKS["carbon"], "phone_tall", "cover")
        self.assertEqual(whole.size, fill.size)
        whole_ink = np.any(np.asarray(whole) != PAPERS["white"], axis=2)
        fill_ink = np.any(np.asarray(fill) != PAPERS["white"], axis=2)
        self.assertFalse(whole_ink[:100].any())
        self.assertTrue(fill_ink[:100].any())
        self.assertGreater(fill_ink.sum(), whole_ink.sum())

    def test_color_amount_fades_fixed_high_resolution_ink(self):
        pages = []
        with patch("drawing.export.output_size", return_value=(880, 680)):
            for amount in (0, .37, 1):
                pages.append(np.asarray(print_plan({**self.meta, "color_amount": amount},
                    PAPERS["white"], INKS["carbon"], "maximum")))
        expected = np.rint(pages[0].astype(np.float32)*.63+pages[2].astype(np.float32)*.37)
        np.testing.assert_array_equal(pages[1], expected)


class ExportRequestTests(StudioTests):
    # Reuse the disposable database/image setup, not the inherited test cases.
    def test_opt_in_binary_export_and_standard_path_unchanged(self):
        normal = self.request(preview="0")
        with patch("drawing.export.output_size", return_value=(432, 936)):
            export = self.request("/export", export_profile="phone_tall", preview="0", color_amount=".37")
        self.assertEqual(export.status_code, 200, export.data[:100])
        self.assertEqual(export.mimetype, "image/png")
        self.assertEqual(Image.open(io.BytesIO(export.data)).size, (432, 936))
        self.assertIn("phone-wallpaper-432x936.png", export.headers["Content-Disposition"])
        again = self.request(preview="0")
        self.assertEqual(normal.json, again.json)

    def test_invalid_options_and_original_fail_without_allocating_big_pages(self):
        for settings in ({}, {"export_profile": "huge"},
                         {"export_profile": "maximum", "wallpaper_fit": "stretch"},
                         {"export_profile": "maximum", "drawing_style": "original"}):
            response = self.request("/export", **settings)
            self.assertEqual(response.status_code, 400)
        with self.server.render_slot:
            response = self.request("/export", export_profile="maximum")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(self.client.get("/health").status_code, 200)


# unittest also discovers inherited methods. Only add the export-specific cases;
# the existing Studio suite exercises its own methods once in test_studio.py.
def load_tests(loader, tests, pattern):
    suite = loader.loadTestsFromTestCase(PrintPlanTests)
    suite.addTest(ExportRequestTests("test_opt_in_binary_export_and_standard_path_unchanged"))
    suite.addTest(ExportRequestTests("test_invalid_options_and_original_fail_without_allocating_big_pages"))
    return suite


if __name__ == "__main__":
    unittest.main()
