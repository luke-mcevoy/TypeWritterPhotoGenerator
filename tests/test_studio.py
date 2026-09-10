"""Exercise the Studio's preview, print and persisted-post contract in a temporary DB."""
import base64
import importlib
import io
import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

import db
import storage


class StudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="carriage-studio-test-")
        cls.patches = [
            patch.object(db, "DATA_DIR", cls.directory.name),
            patch.object(db, "DB_PATH", os.path.join(cls.directory.name, "test.db")),
            patch.object(db, "POSTS_DIR", os.path.join(cls.directory.name, "posts")),
            patch.object(storage, "BUCKET", ""),
        ]
        for item in cls.patches:
            item.start()
        cls.server = importlib.import_module("app")
        db.init_db()
        cls.server.app.config.update(TESTING=True)
        cls.user = db.create_user("studio_test", "Studio test", "test password")
        source = Image.new("RGB", (100, 80), "white")
        draw = ImageDraw.Draw(source)
        draw.rectangle((8, 8, 45, 70), fill=(25, 85, 195))
        draw.rectangle((60, 20, 92, 60), fill=(220, 140, 15))
        draw.line((10, 65, 40, 15), fill=(10, 18, 30), width=4)
        buffer = io.BytesIO()
        source.save(buffer, "PNG")
        cls.photo = buffer.getvalue()

    @classmethod
    def tearDownClass(cls):
        for item in reversed(cls.patches):
            item.stop()
        cls.directory.cleanup()

    def setUp(self):
        self.client = self.server.app.test_client()

    def request(self, endpoint="/convert", **settings):
        return self.client.post(endpoint, data={
            "image": (io.BytesIO(self.photo), "photo.png"), "columns": "40",
            "drawing_style": "refined", "preview": "1", **settings,
        })

    def decode(self, url):
        return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))

    def test_color_endpoints_share_the_selected_drawing(self):
        response = self.request(color_amount="0.37")
        self.assertEqual(response.status_code, 200, response.json)
        data = response.json
        mono, full = map(self.decode, data["color_endpoints"])
        expected = np.rint(np.asarray(mono, dtype=np.float32)*.63 + np.asarray(full, dtype=np.float32)*.37)
        np.testing.assert_array_equal(np.asarray(self.decode(data["image_data"])), expected)
        self.assertNotEqual(mono.tobytes(), full.tobytes())
        for amount, endpoint in (("0", mono), ("1", full)):
            result = self.request(color_amount=amount)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(self.decode(result.json["image_data"]).tobytes(), endpoint.tobytes())

    def test_all_styles_export_their_supported_formats(self):
        for style in ("original", "monochrome", "ribbon", "refined"):
            result = self.request(drawing_style=style, preview="0", color_amount=".37")
            self.assertEqual(result.status_code, 200, result.json)
            self.assertEqual(result.json["drawing_style"], style)
            self.assertEqual(result.json["color_endpoints"], [])
            self.assertEqual(self.decode(result.json["image_data"]).format, "JPEG" if style == "original" else "PNG")
            self.assertEqual(bool(result.json["text_data"]), style == "original")

    def test_post_uses_the_same_style_and_color_as_print(self):
        # Posts always print at the top scale, so compare against a scale-3 export.
        export = self.request(preview="0", color_amount=".37", scale="3").json
        expected = io.BytesIO()
        self.decode(export["image_data"]).save(expected, format="JPEG", quality=95, subsampling=0)
        with self.client.session_transaction() as session:
            session["user_id"] = self.user["id"]
        posted = self.request("/api/posts", color_amount=".37", caption="Color check")
        self.assertEqual(posted.status_code, 200, posted.json)
        with self.client.get(posted.json["post"]["image_url"]) as image:
            self.assertEqual(image.data, expected.getvalue())
        with self.client.get(posted.json["post"]["source_url"]) as image:
            self.assertEqual(image.status_code, 200)

    def test_bad_settings_and_extreme_aspects_fail_cleanly(self):
        for settings in ({"color_amount": "nan"}, {"contrast": "inf"},
                         {"color_amount": "bad"}, {"drawing_style": "unknown"}):
            response = self.request(**settings)
            self.assertEqual(response.status_code, 400, response.json)
        for value, expected in (("-2", 0), ("4", 1)):
            response = self.request(color_amount=value)
            self.assertEqual(response.json["color_amount"], expected)
        photo = Image.new("RGB", (1, 1000), "white")
        buffer = io.BytesIO()
        photo.save(buffer, "PNG")
        response = self.client.post("/convert", data={"drawing_style": "refined",
            "image": (io.BytesIO(buffer.getvalue()), "tall.png")})
        self.assertEqual(response.status_code, 400, response.json)

    def test_busy_press_keeps_health_responsive_and_releases_slot(self):
        with self.server.render_slot:
            response = self.request()
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.headers["Retry-After"], "2")
            self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.request().status_code, 200)
        self.assertEqual(self.request(color_amount="bad").status_code, 400)
        self.assertEqual(self.request().status_code, 200)

    def test_existing_clients_default_to_original_and_posts_require_login(self):
        response = self.client.post("/convert", data={"columns": "40",
            "image": (io.BytesIO(self.photo), "photo.png")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["drawing_style"], "original")
        response = self.client.post("/api/posts", headers={"X-Requested-With": "fetch"})
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
