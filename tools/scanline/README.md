# scanline

Generates every image in the profile README: a Bloch sphere + BB84 simulation drawn as black
horizontal scanlines, stepping at 12 fps, with a faint glowing ghost of the previous frame.
Everything is baked into SVG (CSS `step-end` animation, no JavaScript), so GitHub can show it.

## Regenerate

Python 3.13 (what CI uses). Run everything from the repo root.

```bash
pip install -r tools/scanline/requirements.txt
python tools/scanline/build.py --gif                                   # hero, tagline, divider -> assets/hero
python tools/scanline/clip.py assets/source/higgsfield-sphere.png      # AI-still hero -> assets/hero-alt
python tools/scanline/contrib.py KokoGecko                             # contribution graph -> assets/contrib
```

Add `--out some/folder` to any of them to experiment without touching `assets/`
(`build.py --take a` writes the same file names as take B, so give it its own `--out`).
`--help` lists every option. The build is deterministic: same code, same bytes.

The GitHub Action (`.github/workflows/assets.yml`) runs `build.py --gif` and `contrib.py` on every push
to `main` that touches `tools/` or the workflow, and commits whatever changed. Run it by hand from the
Actions tab ("Run workflow") to refresh the contribution graph.

## Files

| file | what it does |
| --- | --- |
| `sim.py` | the physics: Bloch vectors, precession, BB84 prepare / measure / sift, fixed seed |
| `render.py` | darkness image -> scanlines (band average -> rule thickness -> merged blocks) |
| `timeline.py` | the data model: rectangles + the frames they are visible in |
| `export.py` | timeline -> animated SVG, static SVG, GIF |
| `scenes.py` | layouts: hero takes A and B, sine divider, "stardust" |
| `font.py` | the 5 x 7 pixel font (g j p q y hang two rows lower) |
| `theme.py` | colours, contrast levels and image descriptions |
| `build.py` | builds the README images |
| `clip.py` | any still / GIF / MP4 -> the same scanline look (alternative hero) |
| `contrib.py` | contribution graph (GraphQL with a token, public page without) |

GIFs are for places that cannot animate SVG (your site, a social card); the README only uses the SVGs.

## The alternative hero

`assets/hero-alt` traces its sphere from `assets/source/higgsfield-sphere.png`, a single Higgsfield
still. Video generation needed a paid Higgsfield plan, so the vector, photons and key on top of it are
the same simulation as the main hero. To compare with a real clip later (Higgsfield or a Claude Motion
export in `assets/motion/`), run `clip.py` on the clip. To make it the live hero, point the README
`<picture>` at `assets/hero-alt/` instead of `assets/hero/`.

## Tweak

- **Different random run:** change `SEED` in `sim.py`. `python tools/scanline/sim.py` prints the run first.
- **More or fewer photons:** `N_PHOTONS` and `HOLD_SLOTS` in `sim.py` (loop length = (photons + hold) x 0.5 s).
- **Speed:** `FPS` and `FRAMES_PER_PHOTON` in `sim.py`. 12 fps is the look; smoother loses it.
- **Chunkier or finer lines:** `PITCH`, `CELL`, `MAX_LINE`, `GAMMA` in `render.py`.
- **Ghost:** `ghost` opacity per mode in `theme.py`, `GHOST_BLUR` in `export.py`.
- **Colours and label contrast:** `PAPER`, `NIGHT`, `ACCENT` in `theme.py`.
- **Camera:** `Camera(...)` in `scenes.hero_b` (elevation and azimuth in degrees; 30/45 is a dimetric view).
- **Label size:** `LABEL` in `scenes.py` (3 px keeps labels readable on a phone).

## Physics in one place

- A state |ψ⟩ = cos(θ/2)|0⟩ + e^{iφ} sin(θ/2)|1⟩ is the unit vector r = (sin θ cos φ, sin θ sin φ, cos θ).
- Alice: basis + (z axis) or × (x axis); bit 0 -> +axis, bit 1 -> -axis. So |0⟩, |1⟩, |+⟩, |−⟩
  (as polarisation: H, V, D, A).
- Precession: H = (ħω/2)σz turns r about z by φ = ωt (for a spin this is Larmor precession; for a photon
  in fibre the same rotation is Faraday rotation). ω is set so the state makes exactly one turn by the time
  Bob measures. One turn is U = e^{-iπσz} = −1: a global sign, invisible, so the vector is back where it began.
- Bob measures in the frame that co-rotates with H (his axis is turned by ωt, as a real receiver compensates
  a known channel rotation). Born rule: P(+n) = (1 + r·n)/2, then the state collapses to what he found.
  Same basis -> always Alice's bit; other basis -> exactly 50/50.
- Sifting keeps only the bits where the bases matched. Without an eavesdropper the error rate is 0.

Size budget: hero SVG < 1 MB, GIF < 5 MB (now about 90 KB and 230 KB). Cut frames or rows before quality.
