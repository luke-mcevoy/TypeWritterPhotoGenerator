# Session handoff

## 2026-09-10 — typewriter algorithm exploration

- Inspected local production engine and public Carriage wall images. User clarified
  the artistic target is https://www.jamescookartworkshop.com/collections/shop.
- Added isolated experiments under `experiments/`: calibrated glyph/pressure
  fitting, and a more relevant contour renderer with freely positioned,
  overlapping character strikes. No app integration or deployment performed.
- Generated four comparisons (lighthouse, car, Pearl Earring, Empire State) at
  `output/algorithm-comparison/index.html`; output is gitignored. Reproduce with
  `python -m experiments.compare PHOTO ... --columns 150` in the project venv.
- Eight behavior tests pass via unittest discovery in `experiments`.
- Main remaining gap: artistic region planning, coherent hatching, and dark mass.
  Current contour algorithm is a visual proof of direction, not equivalent to
  Cook's work or ready as a drop-in replacement. See `experiments/README.md`.
- Existing/concurrently changing edits to app, templates, styles, Fly settings,
  Dockerfile and reprint tooling belong to other work and were not modified here.

## 2026-09-10 — selective ribbon color

- User strongly prefers the new monochrome contour drawing and wants color in
  the spirit of Cook's real typewriter work. His Crossing Paths product text
  confirms that he uses colored ribbons for selected details.
- Added optional `color_mode="ribbon"`, `color_amount` to the contour engine;
  default monochrome output and black strike plan are preserved. All color is
  deposited through real glyph masks using at most three simulated ribbons.
- Added `python -m experiments.color_study PHOTO ...` and generated four
  studies at `output/algorithm-comparison/color/index.html`, served at
  http://127.0.0.1:8008/color/ (verified HTTP 200).
- Replaced the confusing slider in this new viewer with explicit buttons:
  Original algorithm / New monochrome / New color / Photo.
- All 12 behavior tests pass, including exact preservation with zero color,
  grayscale fallback, reproducibility, and glyph-only color support.
- Color still uses hue and geometric activity rather than object segmentation.
  No deployment or changes to the main app or other concurrent work.

## 2026-09-10 — connected color and richer shadows

- Continued at user's request to improve quality toward the Cook reference.
- Added `experiments/layered_color.py` and `color_mode="layered"`: connected
  hue regions, warm-hue separation, rejection of isolated color specks, short
  repeated character runs, overlapping colored impressions, and black shadow
  hatching. Absolute chroma reduces weak casts; open backgrounds use sparse
  short marks. Existing monochrome and earlier ribbon modes remain available.
- `experiments.color_study --refined` creates explicit five-version comparison
  controls. Four updated studies live at http://127.0.0.1:8008/refined/.
- Browser check passed all 20 version selections, image loads, active labels,
  full-image links, and mobile width. Script is in
  `/private/tmp/carriage-refinement-browser.mjs` and uses local Playwright.
- Added five meaningful behavior checks for the refinement (17 tests total).
  Important limitation: grouping still uses hue, chroma and texture rather than
  object understanding. Some subtle hues are omitted; keep alternatives visible.
- No app integration or deployment; other changes in the dirty worktree are
  from concurrent work and were not touched.

## 2026-09-10 — interactive color amount

- Added the requested 0–100% Color amount slider to both color versions in
  generated galleries. Refreshed all four studies at
  http://127.0.0.1:8008/refined/. `experiments/color_controls.js` supplies the UI.
- `ContourEngine.convert` plans fixed full-color marks, then fades their layer
  with `color_amount` (0–1). Black hatching uses a separate `hatch_amount`
  (default .7) and stays identical across slider values. Zero color now retains
  refined hatching; zero color plus zero hatching matches the first monochrome.
- The gallery generator emits lossless endpoints. The browser blends them
  immediately and exports the displayed amount as PNG, with stale-download
  guards during dragging/switching. Percentages persist between versions.
- All 20 Python tests pass. Browser verification passed 20 version selections,
  24 endpoint/intermediate pixel checks, eight matching PNG downloads, rapid
  switching, retained amount and mobile width. Screenshot:
  `/private/tmp/carriage-color-slider.jpg`.
- Existing production app remains untouched; these controls are local only.

## 2026-09-10 — stronger, more faithful object color

- The intervening Studio integration, serial preview queue, and faster contour
  matching were committed by another session (HEAD initially `75889ef`). The
  deployed app already exposes Refined color. Earlier entries above describe
  the state before that integration.
- User identified missing foliage/object color in public post 19. Downloaded
  its public source and drawing into `/private/tmp/carriage-post19-*.jpg`.
  Source foliage is mostly 64–92 degree hue; the old palette routed much of it
  to ochre, then region filtering and global top-three selection removed color.
- Added `drawing/vibrant_color.py`: explicit source hue centers with yellow-green
  ribbon, nine pigments, local color support without the global top-three cap,
  three overlapping glyph feeds, near-neutral/dark-cast suppression. Reuses the
  exact existing black hatching and outline plan. Old modes remain unchanged.
- Added Vibrant color to the Studio/API, retaining the instant amount slider,
  PNG downloads and server-side posts. It is the new Studio default locally.
- Added a five-photo comparison at http://127.0.0.1:8008/vibrant/; regenerate
  with `python -m experiments.vibrant_study PHOTO ...`. No reference artwork
  is included. Post 19 now has clear green foliage and colored street details.
- 31 tests pass (11 app/vibrant tests plus 20 prior renderer tests). They cover
  yellow-green hue including shadows, six local object colors, exact glyph
  replay, neutral/dark/speck rejection, identical black plans and amount fades.
- Browser tests passed in the disposable 2 GB / one-CPU container: uploads,
  0/37/100% slider pixel checks, all five styles, PNG download, retained amount,
  mobile layout and an authenticated stored post at 37%. Peak cgroup memory was
  846,049,280 bytes (about 807 MiB).
- Corrected browser color interpolation to blend cached RGBA endpoints directly;
  native canvas globalAlpha rounding introduced up to two levels of error with
  the stronger pigments. The preview now follows the export calculation.
- Deployed at the user's explicit request with `fly deploy --app
  carriage-typewriter --remote-only --ha=false`. Image:
  `registry.fly.io/carriage-typewriter:deployment-01M2745VA0D095CSHR7PRBW7H4`.
  Fly rollout/DNS checks passed and the public `/health` returns `{"ok":true}`.
  The previous image for rollback was
  `registry.fly.io/carriage-typewriter:deployment-01M24YJS9D689HQAS2P8JHQZTH`.
- Existing saved posts, including post 19, were not rewritten. Vibrant color
  applies when generating a new drawing; the old styles remain selectable.
- Production browser checks passed uploads, instant 0/37/100% color, matching
  side-by-side output, PNG download, all five drawing styles, retained color,
  mobile width and no browser errors. No public test posts were created.
  Fly reports machine version 14 started with its health check passing. The
  disposable local container was stopped; the comparison viewer remains available.

## 2026-09-10 — broader local color audit and hollow dark subjects

- Tested 12 additional photographs (7 nature, 5 buildings), with identical
  renderer settings and 40/70/100% color comparisons. Local gallery:
  http://127.0.0.1:8008/nature-buildings/. Sources and credits are in
  `experiments/scene_validation.json`; findings are in `SCENE_REVIEW.md` and
  `scene_findings.json`. Generated images/settings/hashes are gitignored output.
- Bright green foliage, autumn colors, turquoise water and red brick improve
  substantially. Dark forests/night scenes lose volume; muted blue facades and
  pale color transitions are still omitted. Increasing the amount does not fill
  rejected regions. This is an honest mixed result, not a blanket quality pass.
- User added posts 30 and 31 as failures. Downloaded their public source/drawing
  images to `/private/tmp/carriage-post{30,31}-{source,drawing}.jpg`. Reproduced
  the hollow black cows/raven. Root cause: contour target and black hatching
  suppress uniform dark interiors because they rely on local contrast.
- Added isolated `experiments/tonal_target.py` and `tonal_study.py`. An absolute
  shadow floor makes the existing fitter place more character impressions
  inside dark subjects. Only the experiment process substitutes this target;
  **no application algorithm changes or deployment in this session**.
- Compared candidate vs current Vibrant on all 14 photos at fixed settings:
  http://127.0.0.1:8008/shadow-coverage/. Raven/cows/boats and forest shadows gain
  clear dark bodies. Broad night backgrounds also become dense; pale color
  omissions and coarse hue grouping are unresolved. Review before integration.
- Three targeted tests pass: flat dark interior coverage, unchanged highlights,
  and fixed black drawing across color amounts. Browser verification passed
  26 per-photo viewers, 52 version selections, 208 sampled pixel/amount checks,
  download readiness, photo tabs, overview filters and four mobile widths,
  with no browser errors. Script: `experiments/scene-browser.mjs`; screenshot:
  `/private/tmp/carriage-shadow-mobile.jpg`. `git diff --check` passed.
- Existing comparison HTTP server on port 8008 remains running. Renderer and
  app files were concurrently receiving progress-reporting/deployment edits;
  these belong to other work and were preserved. The audit records its renderer
  hashes; current progress callback edits mean those hashes now differ.

## 2026-09-18 — algorithm review, cropping and repository sync

- User requested a review against James Cook, GitHub synchronization, cropping,
  and concrete improvement examples. Reviewed Crossing Paths and Evening in
  Tokyo plus the current public SF drawing. Findings and two fresh comparison
  sheets are in `docs/algorithm-review-2026-09-18.md` and `docs/examples/`.
- Main finding: improved hue coverage and dark interiors do not supply deliberate
  character patterns, region planning or selective color emphasis. Dense black
  is also present in Cook's work; removing shadows wholesale is not a solution.
  No renderer formulas/defaults were changed during this review.
- Verified Fly release 17, image `deployment-01M2786VKVSSYWSSFEMX9CF09H`, healthy.
  Live contour/vibrant/shadow source hashes exactly match the local files. The
  earlier deployment progressed beyond the previous journal entry. Post 33 now
  points to a different image than the pre-reprint snapshot. No deployment or
  production-post mutation was performed in this review.
- GitHub and local HEAD started at `75889ef`; recent features existed only as
  uncommitted changes. Repository sync includes that existing work, docs, tests,
  the review/examples and the new crop workflow. Generated galleries and runtime
  data remain ignored; reference artwork downloaded to temporary files is excluded.
- Cropping now opens before upload rendering; includes free/square/landscape/
  portrait/wide selection, reset, cancel, full image, retained original/selection,
  Escape/focus containment, bounded crop export and stale-callback protection.
  Preview, download and post all use the same selected photo. Source photos in
  saved posts reflect the crop; the uncropped original remains in the browser
  for reframing during that Studio session.
- 19 application tests and 23 experiment tests passed. The new crop browser test
  verified selection geometry, dragging, cancel/reset/full image, retained
  original, actual cropped uploads/exports/posts, saved source pixels and mobile.
  The Studio browser suite passed all styles, color interpolation, download and
  local authenticated posting after fixing its Shadow fill visibility assertion
  to open the More panel. No public test posts were created.
- Local test app runs on 5012 with disposable data. Gallery server on 8008 remains
  available at `/review-examples/`. New crop workflow is local/GitHub only until a
  subsequent Fly deployment. Historical shadow study now explicitly disables
  shadow fill for its baseline when regenerating the cow/raven comparisons.

## 2026-09-18 — full-keyboard illustration preview; repeated motifs rejected

- User requested closer alignment with Cook, then explicitly rejected the first
  new examples: too many repeated characters and insufficient detail/impact.
  The initial region-family prototype did overconstrain selection: `c` made up
  8,993/25,397 marks in the forest. Do not return to fixed per-surface alphabets.
- Added optional `illustrated` mode in `drawing/illustration.py`. The corrected
  implementation fits the full selected keyboard for both black and colored
  impressions, uses weak direction preferences, and discourages locally repeated
  keys only among fits within 82% of the best score. Fine tonal detail supplements
  coarse shadows. Contours match straight, curved and punctuation glyphs.
- Retains dark interiors, real whole-glyph ink, deterministic plans, fixed black
  drawing across color amounts and exact lossless endpoint interpolation. Uses
  existing Pillow/NumPy dependencies. Earlier modes' renderer paths remain intact.
- Studio exposes `Typed illustration (preview)`; **Vibrant remains the default**.
  No Fly deployment or production-post rewrite. This is a local study, not a
  claim of Cook-level quality: geometry does not provide object interpretation,
  deliberate lettering or composition; dense text and weak muted colors remain.
- Six final source/Vibrant/preview comparisons at
  http://127.0.0.1:8008/illustrated/ (crow, forest, brick, colored houses, SF, night).
  Both modes use 180 columns, 70% color and identical other settings. Generator:
  `python -m experiments.illustration_study --columns 180 PHOTO...`. Source/renderer
  hashes and settings are in the ignored gallery manifest. Rejected snapshots
  remain in ignored `illustrated-rejected/`; earlier drafts are not the final mode.
- `docs/typed-illustration.md` includes assessment and committed comparison/detail
  images. Reference artwork remains outside the repository. The new close-up
  compares rejected 150-column and revised 180-column studies at matching page
  width; full-source baseline/final gallery uses 180 columns for both renderers.
- 26 application/renderer tests and 23 experiment tests pass. New checks cover
  geometric directions, paper/highlights, dark bodies, whole-glyph color replay,
  repeatability, scale/endpoints, bright pigment and avoiding a dominant character.
  Studio browser check passes all styles, color fades, PNG export, mobile and
  local authenticated posting. Gallery passes 18 versions and 36 amount/download
  states. A test initially selected the hidden style selector before upload;
  corrected the test to select after rendering. No product workaround was needed.
- Disposable local Studio remains on 5012 (fresh temporary DB, no bucket); gallery
  server remains on 8008. Preview/crop changes are being synced to GitHub; neither
  was deployed in this session. Next iteration should address intentional object
  construction and visual hierarchy, not just increase character diversity.

## 2026-09-18 — production deployment

- User explicitly requested updating production with the revised preview.
  Deployed tested code commit `f847c2d` with `fly deploy --app carriage-typewriter
  --remote-only`. Fly release 18 uses image
  `deployment-01M2TRZASGDPE3DA72NDH2PRM5` (digest
  `sha256:7a875140c5d6ce6db90f810d24fe27c567404e02023ebd68d60c8ef9997593f4`).
- Machine `840e95a2d5ee28` started successfully and its HTTP health check passes.
  Public `/health` returned `{"ok":true}`. The production browser check verified
  the new renderer, instant color interpolation, side-by-side view and PNG export.
  All six styles, retained color, mobile width and browser-error checks passed.
- Upload cropping is included in this deployment. The revised renderer is
  available as `Typed illustration (preview)` after framing an uploaded photo;
  Vibrant remains the default. No existing public posts were regenerated and
  the browser check skips account creation/posting on production.
- Updated README and the study document to reflect the live deployment. The
  artistic limitations remain those documented in the previous handoff.

## 2026-09-20 — visual GitHub README

- Rebuilt the README around a source/drawing hero, an animated 0–100% color
  example, a glyph close-up, actual Studio/crop screenshots, and two clickable
  wall examples. Seven optimized assets total 3.52 MiB in `docs/media/`.
- Assets prepared September 18 use actual, validated Vibrant renderer output
  and saved public posts; photo credits and exact settings are documented in
  `docs/media/README.md`. Screenshots came from the disposable local Studio.
  No renderer or production posts were changed.
- Clarified account-free rendering/downloads, six available styles, crop flow,
  Dark fill, local setup, and SQLite/Tigris storage. The illustration preview
  remains accurately labeled as experimental. Developer details are expandable.
- Verified all 20 local links, seven decodable images with alt text, the animated
  GIF's 15 frames, and six live demo URLs (HTTP 200). Rendered Markdown through
  GitHub's API and checked a local desktop/mobile browser preview, with no page
  overflow. Studio captures completed without JavaScript errors; diff check passes.
- Publishing this documentation-only update to `main` with `[skip ci]` to avoid
  an unnecessary Fly deployment. Existing production code remains unchanged.

## 2026-09-20 — optional high-resolution and phone wallpaper exports

- User requested the README before/after plus the highest-resolution output as
  an opt-in setting suitable for phone wallpapers. README comparison is at
  `output/readme-review/before-after.jpg` and its scrollable HTML companion.
- Added More → Save as: Standard remains the default, Maximum PNG preserves
  proportions within 6,000 px / 12 MP, and phone presets are 2160×4680 (9:19.5)
  and 2160×3840 (9:16). No particular phone model was supplied. Phone framing
  offers the full drawing on matching paper or centered fill/crop, with a live
  thumbnail. Export choices do not trigger previews or affect wall posts.
- `drawing/export.py` re-rasterizes the existing glyph plan from the font at
  output size, with horizontal strips bounding working memory. Preserves selected
  paper, ink, black hatching, and color amount. `/export` returns a binary PNG
  with a dimensions-based filename. The original grid renderer retains its
  existing options; high-resolution export is available for the five newer styles.
- The six new export checks and existing app tests pass (32 total), plus all
  23 experiment tests. Native-size replay matches existing rendering within
  one channel value; color endpoints retain exact float32 interpolation.
- Docker validation on Python 3.12, capped at one CPU / 2 GB: forest maximum
  4173×2874, brick phone 2160×3840, crow phone 2160×4680, and a tall forest crop
  2160×4680 all exported successfully. Times 2.88–10.23 s; cumulative peak RSS
  590.6 MiB. PNGs and benchmark JSON are in `output/wallpaper-study/`.
- Browser checks passed real phone download, retained color, fit/fill preview,
  both ratios, reset-to-standard, original-style compatibility, and mobile width.
  Existing Studio suite also passed all six modes, instant color, regular PNG
  downloads, and signed-in posting against the disposable local container.
- README documents settings and the distinction between key count and pixel
  resolution. GitHub Actions' last two deployments failed independently of this
  work; using a manually verified Fly deployment and `[skip ci]` for this release.
