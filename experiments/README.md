# Typewriter algorithm studies

The visual target is James Cook's [shop gallery](https://www.jamescookartworkshop.com/collections/shop),
especially *Empire State Building and NYC Taxi*, *Girl with a Pearl Earring*,
and *Crossing Paths, Manhattan*. Viewed September 10, 2026. Reference artwork
is not bundled or used as a rendering input.

The reference changes the priority: connected outlines, deliberate white space,
overlapping shade, and locally coherent character patterns matter more than
matching photographic grayscale. These experiments are isolated from the app.

## Run a comparison

```sh
.venv/bin/python -m experiments.compare your-photo.jpg --columns 150
# A separate experiment focused on tonal fidelity:
.venv/bin/python -m experiments.compare your-photo.jpg --mode tone --output output/tone-comparison
.venv/bin/python -m unittest discover -s experiments -p 'test_*.py' -v
```

Open `output/algorithm-comparison/index.html` for a draggable comparison.
The folder also contains standalone three-way JPEGs, full drawings, copies of
the inputs, and local conversion timings. Current output is regenerated from
the checked-out production engine with `fast=True`, matching the app's current
call path; existing wall posts may have different settings or engine versions.

## Colored ribbon study

```sh
.venv/bin/python -m experiments.color_study your-photo.jpg --columns 150 --color-amount .7
```

Open `output/algorithm-comparison/color/index.html`, or `/color/` on the existing
port 8008 comparison server. Explicit buttons show Original algorithm, New
monochrome, New color, or Photo. The output includes side-by-side sheets.

`ContourEngine.convert(..., color_mode="ribbon", color_amount=.7)` enables a
separate layer of colored glyph impressions. The default remains monochrome;
zero color amount reproduces it exactly. Source hue, saturation and geometric
activity choose up to three ribbons from an ochre/red/blue/green/teal/violet
palette. Related marks repeat within small regions, with denser color around
forms and light color in open areas. Black contours and the complete black
strike plan remain unchanged. Color is deposited only through glyph masks,
with overlapping pigment darkening by multiplicative transmission. This is a
rendering approximation, not a physical calibration of real ribbon chemistry.

Cook's own [Crossing Paths description](https://www.jamescookartworkshop.com/products/crossing-paths-manhattan)
confirms colored typewriter ribbons are used to emphasize selected street
details. Our automatic selection still has no object understanding or manual
region mask; it can color skin or background where an artist would choose not
to. Region selection and coherent hatching remain the next artistic priorities.

## Refined color and shadow hatching

```sh
.venv/bin/python -m experiments.color_study your-photo.jpg --refined --columns 150 --output output/algorithm-comparison/refined
```

Open `/refined/` on the local comparison server. The gallery retains the original
algorithm, first contour drawing, and earlier color pass, with an additional
**Refined color** button. Its comparison sheet shows monochrome, earlier color,
and refined color at the same viewing size.

The optional `color_mode="layered"` builds connected hue regions before printing.
It discards isolated specks, separates nearby warm hues, and uses strong chroma
within a region to decide whether its paler parts should also receive color.
At most three ribbons are selected. Short runs of upright characters follow
local slopes; offset overstrikes deepen color. Smooth open areas receive sparse
short marks, and absolute chroma reduces weak color casts in dark/neutral areas.
An additional set of black character runs develops local shadow around forms.

The default monochrome mode is unchanged. The refined mode adds black hatching
as well as color, so grayscale inputs can still gain shadow detail. Color and
hatching now have independent amounts: setting `color_amount=0` keeps the
refined black shadows, and setting both `color_amount=0, hatch_amount=0`
reproduces the first contour drawing. Colored marks are planned at full strength
and faded as a complete layer, avoiding changing patterns while adjusting color.
The full-strength color plan and fixed black plan are recorded in
`color_strikes` / `hatch_strikes`; `color_amount` records the global fade.
The original contour strike plan is retained. Preview and export share the
same plan, with scale affecting only the output size.

This remains geometric grouping, not semantic scene segmentation. Subtle color
can be omitted, and dense areas can still show repeated patterns. The viewer
keeps both color approaches available for aesthetic comparison. Twenty
behavior tests cover deterministic plans, unchanged zero-amount output, removal
of isolated accents, glyph support for every added ink pixel, interpolation of
color endpoints, and fixed black hatching across color amounts.

## Interactive color amount

Both color versions in a newly generated gallery have a **Color amount** slider
from 0% to 100%. It blends lossless no-color/full-color endpoints locally in the
browser, so dragging is immediate and the black drawing stays fixed. Each photo
retains its percentage when switching versions. **Download this version** saves
a PNG matching the current canvas; the full-size image link uses that same PNG.
The static comparison sheet remains at the generation-time amount.

The Python parameter uses 0–1, for example:

```python
page, meta = ContourEngine().convert(photo, color_mode="layered",
    color_amount=0.35, hatch_amount=0.7)
```

`--color-amount .35` sets the gallery's starting slider value. Non-finite values
are rejected and finite out-of-range values clamp to 0–1. Download encoding is
debounced while dragging; links activate after the current percentage is ready.

## Experiments

- `strike_engine.py`: measures the same atlas it prints; jointly fits glyph
  unions and pressure using fine shape, coarse shape, and tone; bounded matching
  batches and row rendering. More continuous shade, but visibly regular texture.
- `contour_engine.py`: traces persistent edges with directional keys, then
  deposits independently positioned, overlapping glyphs against the remaining
  ink target. The target suppresses flat tone and emphasizes local shadow and
  form. Actual character masks make every mark; no photograph or drawn vector
  lines are blended into the output. This is the more relevant artistic direction.

The contour experiment is not a drop-in engine replacement: `columns` controls
spatial detail, text/HTML exports are unavailable, and the supported controls
are charset, paper, ink, simplify, contrast, pressure, overstrike, seed, scale,
color mode, color amount and hatch amount.
It accepts other keyword settings for the comparison harness, but does not apply
them. It also uses directional keys from the architecture bank for its outlines.
The overstrike control changes the shade pass budget, not an exact strike cap.
Export scale resamples the same plan. Neither experiment has been deployed or
benchmarked on Fly; local runtime alone does not establish production suitability.

## What remains for the reference aesthetic

1. Region planning: distinguish sky, masonry, foliage, skin, water and lettering.
   Current geometric activity cannot decide that dark sky should stay white
   while equally dark hair should receive dense type.
2. Connected runs of repeated characters following surfaces and perspective,
   with curved marks around facial forms. Random jitter alone cannot do this.
3. More deliberate focal detail and clustered dark hatching; the current contour
   results are still too pale and busy in some areas.
4. A calibrated set of typewriter impressions with varied pressure and worn ribbon.
5. Evaluation across actual user photographs, then app/export integration and
   memory checks on the Fly machine.

The original engine also has specific fixable issues: matching geometry differs
from rendered geometry, glyph gradients can cancel when used as orientation,
random top-five substitution can undo reserved whitespace, and the non-fast
error diffusion propagates errors without updating each quantized choice as it
goes. Fixing those helps fidelity but does not by itself provide artistic planning.
