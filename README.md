# Carriage

Photographs, redrawn in type. A vintage machine chooses the keys for tone and line. From across the room it is a drawing. Up close it is letters.

Join, type a photograph in the studio, and post it to a shared wall. Open any page to see the original beside the drawing.

## Demos

Live app: **[https://carriage-typewriter.fly.dev](https://carriage-typewriter.fly.dev)**

| Try this | Link |
| --- | --- |
| Shared wall | [carriage-typewriter.fly.dev](https://carriage-typewriter.fly.dev) |
| Studio | [Open the studio](https://carriage-typewriter.fly.dev/studio) |
| Fish | [Photo / Drawing / Both](https://carriage-typewriter.fly.dev/p/7) |
| Turkey | [Photo / Drawing / Both](https://carriage-typewriter.fly.dev/p/6) |
| Desert | [Photo / Drawing / Both](https://carriage-typewriter.fly.dev/p/8) |
| Stevens | [Photo / Drawing / Both](https://carriage-typewriter.fly.dev/p/9) |
| Car | [Photo / Drawing / Both](https://carriage-typewriter.fly.dev/p/10) |

On a drawing page, use **Drawing**, **Photo**, and **Both** to compare the typed page with the original.

To make your own: **Join** → **Studio** → drop a photo → frame it → **Post**.

Uploads open **Frame your photo** before rendering. Drag to crop, choose a shape
(free, square, landscape, portrait or wide), reset the selection, or choose
**Use full image**. The **Crop** button reopens the original photo for reframing.
The same crop is used for previews, downloads and the posted source photograph.

The Studio starts with **Vibrant color**. **Color amount** fades the colored
character impressions from 0–100% while keeping the black drawing fixed.
This mode preserves yellow-green foliage, uses a wider ribbon palette for
different objects, and layers more colored impressions for stronger coverage.
The earlier **Refined color**, **Earlier color**, **New monochrome**, and
**Original algorithm** styles remain available. Save exports a PNG for the
new styles; posts use the same color setting. Existing posts are saved images
and do not change when the renderer is updated.

This checkout also includes **Typed illustration (preview)**. It fits the full
keyboard to local shapes, discourages a single character from dominating a
patch, and matches curves as well as straight contour strokes. It remains an
opt-in study; Vibrant is still the default. The [comparison and limitations](docs/typed-illustration.md)
include six photographs and a close-up. The crop workflow and illustration
preview are deployed to Fly. Upload a photo in the Studio, then choose
**Typed illustration (preview)** in the drawing-style menu to try the new renderer.

**More → Shadow fill** controls the extra character coverage inside dark subjects
in Vibrant color. It prevents hollow silhouettes but can also make dark
backgrounds dense. Color amount and Shadow fill address different parts of the
drawing. See the [algorithm review](docs/algorithm-review-2026-09-18.md) for the
current limitations and the proposed direction toward more deliberate typed art.

To compare the color algorithms locally:

```sh
.venv/bin/python -m experiments.vibrant_study your-photo.jpg
.venv/bin/python -m experiments.illustration_study --columns 180 your-photo.jpg
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s experiments -p 'test_*.py'
```

The comparison is written to `output/algorithm-comparison/vibrant/index.html`.

Fly’s free trial stops the machine every five minutes until a payment method is on the account. After that, the first visit following a quiet stretch may take a few seconds to wake.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001). Drawings and accounts live in `data/` (gitignored).

## Share from this Mac

Quick Cloudflare tunnels only work while this process is running. Plug the laptop in, leave the lid open, and in Terminal:

```bash
./serve-public.sh
```

Copy the `https://….trycloudflare.com` URL it prints. Closing the window, sleeping the Mac, or Ctrl+C kills that link. Posts made through the tunnel are stored in this machine’s `data/` folder, not on Fly.

## Deploy

```bash
fly deploy --app carriage-typewriter
```

SQLite and uploaded pages sit on the Fly volume mounted at `/app/data`.
