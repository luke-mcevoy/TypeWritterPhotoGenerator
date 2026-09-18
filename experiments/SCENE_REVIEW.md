# Local color audit — 2026-09-10

Tested 12 additional photographs: seven nature scenes and five buildings. The
unchanged current Vibrant renderer was compared with the previous Refined color
at the same settings, with 40%, 70% and 100% color previews. Images and source
credits are in the gallery; full settings and hashes are in results.json.

The colors work beyond Harvard, but unevenly. Bright foliage, autumn leaves,
turquoise water, red brick and large colored accents improve substantially.
Dark subjects, muted facades and pale transitions expose real weaknesses.

| Scene | Finding at 70% |
| --- | --- |
| Sunlit forest | Green canopy and warm path work; deep shade is too pale. |
| Shaded forest | Olive foliage becomes patchy gold; dark volume is lost. |
| Autumn lake | Strong yellow/blue separation and reflections; dark green is weak. |
| Alpine lake | Turquoise water works; pines and dark mountain faces are too light. |
| Sandstone desert | Warm color restored, but terrain flattens toward terracotta. |
| Wildflower meadow | Red, green and yellow accents work; small/pale details disappear. |
| Turquoise coast | Blue/teal distinction works; broad pale gaps remain in the water. |
| Waterfront houses | Red/yellow improve; muted blue facade and dark boats are weak. |
| Red brick | Strong result: brick, blue sky and teal signage stay distinct. |
| White facade | Stone stays appropriately neutral; sky and tree color are weak. |
| Glass towers | Large blue/teal/red accents work; subtle glass colors disappear. |
| Night city | Colored lights survive but dark surroundings become pale. |

The amount slider fades a fixed set of colored impressions. Increasing it makes
existing color stronger; it cannot add missing marks, correct hue selection or
restore black interiors. At 100%, broad sky/water areas can dominate the scene.

## The holes in posts 30 and 31

The publicly saved photographs and drawings confirm the cows and raven are
rendered almost hollow. Local rerenders reproduce this at fixed audit settings
(the original posts' exact settings are not exposed on their public pages).

The contour target intentionally suppresses flat tone. Where a dark object has
little internal contrast, the target is tiny; the fitter therefore places few
characters. Existing shadow hatching also relies on local contrast. This is
why a black bird can receive a detailed outline but a near-white interior.

A separate local experiment adds an absolute shadow floor to the ink target.
It uses the same glyph fitter and color planner: all added darkness comes from
character impressions. The raven, cows, forest shadows and boats gain clearer
dark bodies. Bright areas remain largely unchanged. All 14 photos were rendered
with the same candidate settings; no image-specific masks or tuning were used.

See http://127.0.0.1:8008/shadow-coverage/ for source/current/candidate comparisons.
This is an experiment, not a live change. It darkens broad night backgrounds too
and can make fine letter texture busier. It does not fix pale color rejection,
muted blue facades, coarse pigment grouping or every white gap around highlights.

The next color work should address those omissions with softer confidence
transitions and more stable local hue selection, while keeping neutral stone
and genuine white highlights clean. That work has not been implemented here.

Coverage diagnostics measure where colored ink was deposited, not artistic
quality. Hue agreement is conditional on retained marks and excludes omitted
colors. No segmentation or object-level ground truth was used.
