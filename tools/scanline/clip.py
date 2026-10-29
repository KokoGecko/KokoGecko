"""AI-rendered input -> the same scanline look, for the alternative hero.

The committed alternative (assets/hero-alt) comes from ONE Higgsfield still
(assets/source/higgsfield-sphere.png): video generation needs a paid Higgsfield plan.
Only the sphere is traced from it; the vector, photons and key are the same BB84
simulation drawn on top. A real clip (with its own rotating arrow) can replace it later.

Feed it a still image, an animated GIF, a folder of PNG frames, or an MP4
(MP4 needs `pip install imageio[ffmpeg]`). Each source frame becomes a darkness image:
  - edges (gradient magnitude) give glass its engraved outline,
  - anything darker than the background adds ink.
The sphere is found automatically and scaled onto the hero's sphere position, then
render.scanlines() turns it into the same black rules as the simulation.

    python tools/scanline/clip.py assets/source/sphere.png
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageFilter

import scenes
from export import write_gif, write_svg
from render import SS, scanlines
from theme import ALT_DESC, STATIC_DESC, palettes

EDGE_PERCENTILE = 99.5  # edge strength that maps to full ink
EDGE_FLOOR = 0.3        # weaker edges (sensor noise, soft gradients) stay paper
DARK_FLOOR = 0.15       # glass is nearly background-grey; only clearly darker pixels add ink
DARK_GAIN = 3.0         # how strongly "darker than background" adds ink
MASK_MARGIN = 1.04      # keep a little outside the fitted circle (rim glow), drop the floor shadow


def load_frames(path):
    """Greyscale float frames (0..1) from a still, GIF, PNG folder or MP4."""
    if os.path.isdir(path):
        names = sorted(n for n in os.listdir(path) if n.lower().endswith(".png"))
        return [np.asarray(Image.open(os.path.join(path, n)).convert("L"), float) / 255 for n in names]
    if path.lower().endswith((".mp4", ".mov", ".webm")):
        import imageio.v3 as iio  # optional dependency, only for video input
        return [np.asarray(Image.fromarray(f).convert("L"), float) / 255 for f in iio.imiter(path)]
    im = Image.open(path)
    frames = []
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        frames.append(np.asarray(im.convert("L"), float) / 255)
    return frames


def darkness(frame):
    """Brightness -> ink: strong edges plus anything darker than the (median) background."""
    blurred = np.asarray(Image.fromarray((frame * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)), float) / 255
    gy, gx = np.gradient(blurred)
    edge = np.hypot(gx, gy)
    e = np.clip(edge / np.percentile(edge, EDGE_PERCENTILE), 0, 1)
    e = np.clip((e - EDGE_FLOOR) / (1 - EDGE_FLOOR), 0, 1)
    dark = np.clip((np.median(frame) - frame - DARK_FLOOR) * DARK_GAIN, 0, 1)
    return np.maximum(e, dark)


def fit_circle(d):
    """Centre and radius of the subject: robust bounding box of strong ink, ignoring the bottom fifth (shadow)."""
    h = d.shape[0]
    ys, xs = np.nonzero(d[: int(h * 0.8)] > 0.5)
    if xs.size == 0:
        raise SystemExit("clip.py: no subject found in the first frame (is it on a plain light background?)")
    x0, x1 = np.percentile(xs, [0.5, 99.5])
    y0, y1 = np.percentile(ys, [0.5, 99.5])
    return (x0 + x1) / 2, (y0 + y1) / 2, ((x1 - x0) + (y1 - y0)) / 4


def place(d, fit, cam, w, h):
    """Resample the source so its fitted circle lands on the camera's sphere; mask outside it."""
    cx, cy, r = fit
    s = r / cam.radius                                   # source px per hero px
    yy, xx = np.mgrid[0:h * SS, 0:w * SS] / SS           # hero coordinates at supersampled resolution
    sx = cx + (xx - cam.c[0]) * s
    sy = cy + (yy - cam.c[1]) * s
    inside = (np.hypot(xx - cam.c[0], yy - cam.c[1]) <= cam.radius * MASK_MARGIN)
    sxi = np.clip(sx.astype(int), 0, d.shape[1] - 1)
    syi = np.clip(sy.astype(int), 0, d.shape[0] - 1)
    return np.where(inside, d[syi, sxi], 0.0)


def source_art(path):
    """A callable for scenes.hero_b: camera -> list of per-source-frame scanline rects."""
    frames = [darkness(f) for f in load_frames(path)]
    fit = fit_circle(frames[0])

    def art(cam, w, h):
        return [scanlines(place(d, fit, cam, w, h)) for d in frames]
    return art


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Render a still / GIF / PNG folder / MP4 as the scanline hero.")
    ap.add_argument("source", help="path relative to where you run it (run from the repo root)")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "..", "assets", "hero-alt"),
                    help="output folder (default assets/hero-alt)")
    ap.add_argument("--gif", action="store_true", help="also write GIFs")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    tl = scenes.hero_b(source=source_art(args.source), sub="bb84 · ai still · 12 fps")
    title = "KokoGecko: BB84, sphere traced from an AI still"
    for mode, pal in palettes("b").items():
        size = write_svg(tl, pal, f"{args.out}/hero-{mode}.svg", title, ALT_DESC)
        write_svg(tl, pal, f"{args.out}/hero-{mode}-static.svg", title, STATIC_DESC, static=True)
        print(f"hero-alt {mode}: {size / 1024:.1f} KB")
        if args.gif:
            write_gif(tl, pal, f"{args.out}/hero-{mode}.gif")
