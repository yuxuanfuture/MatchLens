# MatchLens Pocket Stadium — design QA

Date: 2026-10-27. Result: **Passed for local interactive prototype handoff.**

This review covers the selected visual combination and frontend interactions. It does not certify a live data service, model integration, complete football simulation, hackathon eligibility, or a published release.

## References and actual captures

- Fan target: `docs/visual-targets/fan.png`.
- Fused Analyst target: `docs/visual-targets/analyst-modular.png`.
- Fan implementation: `docs/audit/pocket-fan-desktop.png` at 1672 × 941.
- Analyst implementation: `docs/audit/pocket-analyst-desktop.png` at 1672 × 941.
- Intermediate comparison: `docs/audit/pocket-analyst-pass1.png`.
- Tablet capture: `docs/audit/pocket-tablet.png` at 900 × 900.
- Mobile capture: `docs/audit/pocket-mobile.png`, full page at 390 px width. The fixed playback bar appears at the capture viewport boundary; scrolling the live page exposes the notebook underneath.

The Fan reference and actual Fan capture were inspected together. The fused Analyst reference and actual Analyst capture were also inspected together. Browser checks additionally covered 1280 × 720 and 320 × 844.

## Comparison passes

| Surface | Observation and result |
| --- | --- |
| Composition | Floating island is the dominant image, with clear sky behind the large headline. The commentator occupies the lower left; Analyst adds the notebook at lower right. Passed after revising the environment’s negative space. |
| Typography | Local Nunito Sans provides the bold headline and controls; Fraunces distinguishes the commentary and notebook. The Analyst headline keeps its intended two-line hierarchy on desktop. No clipped card text observed. |
| Spacing | Default modules clear the header and playback controls at desktop/tablet sizes. Settings and evidence panels remain scrollable. User-arranged modules may intentionally overlap. |
| Palette | Sky blue, grass green, cream paper and coral controls carry the selected warm daylight direction. Analyst uses a dark green active mode. |
| Imagery | The environment and independent transparent character sprites are actual generated raster assets. No CSS or SVG substitutes were used for the stadium or character artwork. Tactics, numbers and motion are separately rendered from data. |
| Icons | Phosphor Bold is loaded locally. Replay/pause glyphs were corrected to existing glyph names. Icon-only settings and source controls have explicit accessible names. |
| Responsiveness | 320/390 px layouts stack modules beneath the stadium; 900 px keeps separate desktop modules. Wide-screen positions are preserved when resizing through the mobile breakpoint. |
| Copy | Short Fan explanations and specific Analyst explanations refer to the same replay. Synthetic-source and scripted-commentary disclosure is available from playback on every breakpoint. |
| Interaction states | Active mode/scene, playing/paused, evidence selection, future events, arrangement handles, storage success, panel close, hidden modules and reset were exercised. |
| Accessibility | Semantic buttons, range, checkboxes and selects; visible keyboard focus; keyboard module movement; Escape handling; named icon controls; descriptive canvas alternative; reduced-motion handling. This was not a full assistive-technology certification. |

## Findings resolved

| Severity | Finding | Resolution |
| --- | --- | --- |
| P2 | Initial stadium trees and stands competed with the headline. | Generated a roomier environment and recalibrated the projection to its four field corners. |
| P2 | Analyst headline wrapped to an unintended third line at reference size. | Adjusted its width and responsive font scale; checked two-line wrapping. |
| P2 | Play/pause used names absent from the selected icon font. | Switched to supported Bold glyphs; verified visible controls. |
| P2 | Mobile settings and tablet source controls lost their accessible names when text was hidden. | Added persistent ARIA labels. |
| P2 | Smaller aspect ratios exposed an abrupt image edge below the island. | Blended the image edge into the cream page background and corrected horizontal coverage. |
| P2 | The final formation label appeared before all players had advanced into place. | Kept the transition label until the developed shape is reached; intermediate copy describes movement in progress. |
| P3 | Event list rebuilding could discard keyboard focus after seeking. | Restored focus to the corresponding event button. |

No open P0, P1 or P2 issues were found within the reviewed prototype scope.

## Functional evidence

- **Mode continuity:** paused Counter at 11.6 s / 83:21 remained at that time after Fan → Analyst. The view and explanatory density changed without resetting the replay.
- **Real pointer drag:** at 1280 × 720, the commentary handle was dragged to `left: 443px; top: 234px`. Reload retained those coordinates and Compact size. Keyboard movement was separately exercised.
- **Role separation:** Commentator’s notebook was hidden; Coach still showed its notebook. Returning to Commentator restored the hidden state. Test changes were reset using the product controls.
- **Evidence seeking:** end of Counter showed 1–1, 2 passes, 5 events. Selecting C02 returned to 83:16, 0–1, 1 pass and 2 events.
- **Shape:** the completed scene showed 3–2–5, 3 completed passes and 4 event references.
- **Replay:** Press started from its initial state and advanced the match clock and range while the pause control became active.
- **Mobile access:** the lower notebook’s evidence control scrolled into view and opened the complete event list with a visible close button.
- **Browser diagnostics:** no warnings/errors in the captured local app console during final verification.
- **Automated checks:** all 5 Node tests passed: unique/in-bounds players, pass/receiver alignment, rewind consistency, substitution/formation, and pitch-corner projection. JavaScript syntax and tracked diff whitespace checks passed.

## Deliberate implementation choices and limits

- One live scoreboard is placed in the header instead of duplicating it inside a raster stadium board.
- Roles are selected inside Your view; Fan / Analyst remains a direct top-right switch.
- The notebook is a usable paper-style card with real numbers and evidence links, rather than a baked-in screenshot of a notebook.
- This is a 2.5D raster-and-sprite renderer. It does not provide free 3D rotation, skeletal character animation or real player tracking.
- Preferences are explicitly remembered per browser, role and mode; no inferred user profiling or cloud synchronization is claimed.
- The page currently uses authored synthetic events and scripted text. No live model backend is connected.
- The existing hosted site was not changed. The local server is the reviewable implementation.
