"""Layouts: the two hero takes, the sine divider and the "stardust" tagline.

Every scene returns a Timeline (see timeline.py). Moving parts are drawn into a darkness
image and turned into scanlines (render.py); type is drawn straight from the pixel font.
"""
import numpy as np

import sim
from font import scanline_text_rects, text_rects, text_width
from render import Camera, Canvas, great_circle, latitude, scanlines
from timeline import Timeline

SLOT = sim.FRAMES_PER_PHOTON
LABEL = 3  # pixel size of every information label (3 px stays legible when the hero shrinks on a phone)

# Polarisation glyph for each BB84 state, (basis, bit) -> H, V, D, A.
# A z-rotation by phi on the Bloch sphere turns linear polarisation by phi/2, so after the
# full turn before Bob measures, the polarisation line is back where it started.
POL = {(0, 0): "⎯", (0, 1): "⏐", (1, 0): "⟋", (1, 1): "⟍"}


def block(x, y, size):
    """One chunky pixel block centred on (x, y), snapped to whole pixels."""
    s = int(size)
    return [(int(round(x - s / 2)), int(round(y - s / 2)), s, s)]


def sphere_art(cam, w, h):
    """The fixed Bloch sphere: glass shading, outline, rings and axes, as scanlines."""
    cv = Canvas(w, h)
    cv.shade_sphere(cam, inner=0.0, rim=0.3)
    t = np.linspace(0, 2 * np.pi, 241)
    cv.line([(cam.c[0] + cam.radius * np.cos(a), cam.c[1] + cam.radius * np.sin(a)) for a in t], 2.2, 0.9)
    cv.curve(cam, great_circle("z"), 2.0, 0.85, 0.3)          # equator
    cv.curve(cam, great_circle("y"), 2.4, 0.8, 0.10)          # x-z meridian (back half thinner: depth cue)
    cv.curve(cam, great_circle("x"), 2.4, 0.8, 0.10)          # y-z meridian
    s = np.linspace(-1.22, 1.22, 40)[:, None]
    for axis in np.eye(3):
        cv.curve(cam, s * axis, 2.2, 0.75, 0.10)
    return scanlines(cv.array())


def sphere_labels(cam):
    """|0>, |1>, |+>, |-> at the ends of the z and x axes."""
    rects = []
    for text, p, dx in (("|0⟩", (0, 0, 1.3), 16), ("|1⟩", (0, 0, -1.3), 16),
                        ("|+⟩", (1.55, 0, 0), 0), ("|−⟩", (-1.55, 0, 0), 0)):
        x, y, _ = cam.project(p)
        x = x + dx if dx else x - text_width(text, LABEL) / 2
        rects += text_rects(text, int(x), int(y - 3.5 * LABEL), LABEL)
    return rects


def vector_art(cam, fr, w, h):
    """The state vector for one frame: arrow shaft, precession circle and trail, as scanlines."""
    cv = Canvas(w, h)
    r = fr.r
    if abs(r[2]) < 0.98 and not fr.measured:
        cv.curve(cam, latitude(r[2]), 1.4, 0.38, 0.18, dashed=True)
    if not fr.measured:
        # Trail: short arcs the tip swept through in the previous steps, older = fainter
        pts = fr.trail + [r]
        for i in range(len(pts) - 1):
            arc = [sim.precess(pts[i], t) for t in np.linspace(0, 1 / sim.FPS, 14)]
            cv.curve(cam, arc, 3.0, 0.3 + 0.25 * (i + 3 - len(pts) + 1), 0.15)
    shaft = np.linspace(0, 0.94, 24)[:, None] * r
    cv.curve(cam, shaft, 5.0, 1.0, 0.7)
    return scanlines(cv.array())


def tip(cam, r):
    x, y, _ = cam.project(r)
    return block(x, y, 10)


def add_sphere(tl, cam, photons, frames, source=None):
    """Sphere, labels and the moving vector with its ghost.

    `source` (from clip.py) swaps the drawn sphere for AI-rendered frames, looped over the timeline.
    """
    if source is None:
        tl.add(sphere_art(cam, tl.width, tl.height))
    else:
        art = source(cam, tl.width, tl.height)
        if len(art) == 1:
            tl.add(art[0])
        else:
            for k in range(tl.frames):
                tl.add(art[k % len(art)], on=k, off=k + 1, ghost=True)
    tl.add(sphere_labels(cam))
    for fr in frames:
        tl.add(vector_art(cam, fr, tl.width, tl.height), on=fr.index, off=fr.index + 1, ghost=True)
        lit = fr.measured and fr.photon.sifted
        tl.add(tip(cam, fr.r), "acc" if lit else "ink", fr.index, fr.index + 1, ghost=True)


def add_key(tl, photons, x0, y, px=4, spacing=30):
    """The raw key typing out: Bob's bits, kept ones lit in accent then ink, dropped ones faint.

    Kept bits are underlined and dropped bits struck through, so meaning never relies on colour alone.
    """
    n = tl.frames
    for p in photons:
        x = x0 + p.index * spacing
        start = p.index * SLOT
        bit_on = start + SLOT - 1
        # Cursor while this photon is in flight: on two frames, off one (no strobing)
        for s in range(0, SLOT - 1, 3):
            tl.add(text_rects("█", x, y, px), "ink", start + s, min(start + s + 2, bit_on))
        glyph = text_rects(str(p.bob_bit), x, y, px)
        if p.sifted:
            tl.add(glyph, "acc", bit_on, min(bit_on + SLOT, n))
            tl.add(glyph, "ink", min(bit_on + SLOT, n), n)
            tl.add([(x, y + 7 * px + 4, 5 * px, 2)], "ink", bit_on, n)
        else:
            tl.add(glyph, "faint", bit_on, n)
            tl.add([(x - 2, y + 3 * px + px // 2 - 1, 5 * px + 4, 2)], "faint", bit_on, n)


def sifted_counter(tl, photons, x, y, right=False, px=LABEL):
    """'sifted 05/14' updating as each bit lands."""
    n_ph = len(photons)
    kept = 0
    for p in photons:
        on = p.index * SLOT + SLOT - 1
        kept += p.sifted
        nxt = (p.index + 1) * SLOT + SLOT - 1 if p.index + 1 < n_ph else tl.frames
        label = f"sifted {kept:02d}/{n_ph}"
        xx = x - text_width(label, px) if right else x
        tl.add(text_rects(label, xx, y, px), "ink", on, nxt)
    label = f"sifted 00/{n_ph}"
    xx = x - text_width(label, px) if right else x
    tl.add(text_rects(label, xx, y, px), "faint", 0, SLOT - 1)


def flicker(tl, rects, color, on, off):
    """Show for [on, off) but blank the second frame: a basis indicator settling."""
    tl.add(rects, color, on, on + 1)
    if off > on + 2:
        tl.add(rects, color, on + 2, off)


def rest_frame(photons):
    """Still frame for reduced motion: the last diagonal-basis photon, mid-precession on the equator."""
    diagonal = [p for p in photons if p.alice_basis == 1]
    p = diagonal[-1] if diagonal else photons[-1]
    return p.index * SLOT + 2


def header(tl, sub, px=2):
    tl.add(text_rects("KokoGecko", 48, 44, 4))
    tl.add(text_rects(sub, 48, 86, px), "faint")


def hero_a():
    """Take A: side-on sphere, readout panel to the right, raw key typing out below."""
    photons, frames = sim.run()
    W, H = 960, 520
    tl = Timeline(W, H, len(frames), sim.FPS, [], rest=rest_frame(photons))
    header(tl, "bb84 · bloch sphere · 12 fps")
    cam = Camera(320, 280, 136, elev=22, azim=30)
    add_sphere(tl, cam, photons, frames)

    px = 640
    for label, y in (("photon", 176), ("alice", 216), ("bob", 256), ("sift", 296)):
        tl.add(text_rects(label, px, y + 4, 2), "faint")
    vx = 736
    for p in photons:
        s = p.index * SLOT
        tl.add(text_rects(f"{p.index + 1:02d} / {len(photons)}", vx, 180, 2), "ink", s, s + SLOT)
        flicker(tl, text_rects(sim.BASIS_GLYPH[p.alice_basis], vx, 214, 3), "ink", s, s + SLOT)
        tl.add(text_rects(sim.STATE_LABEL[(p.alice_basis, p.alice_bit)], vx + 32, 220, 2), "ink", s, s + SLOT)
        flicker(tl, text_rects(sim.BASIS_GLYPH[p.bob_basis], vx, 254, 3), "ink", s + 2, s + SLOT)
        m = s + SLOT - 1
        tl.add(text_rects(f"→ {p.bob_bit}", vx + 32, 260, 2), "ink", m, s + SLOT)
        verdict = ("match · keep", "acc") if p.sifted else ("differ · drop", "faint")
        tl.add(text_rects(verdict[0], vx, 300, 2), verdict[1], m, s + SLOT)
    end = len(photons) * SLOT
    kept = [p for p in photons if p.sifted]
    qber = sum(p.alice_bit != p.bob_bit for p in kept) / max(len(kept), 1)
    tl.add(text_rects("done", vx, 180, 2), "ink", end, tl.frames)
    tl.add(text_rects(f"qber {qber:.2f}", vx, 300, 2), "ink", end, tl.frames)

    tl.add(text_rects("raw key", 48, 462, 2), "faint")
    add_key(tl, photons, 156, 456, px=3, spacing=24)
    sifted_counter(tl, photons, 912, 462, right=True, px=2)
    return tl


def hero_b(source=None, sub="bb84 · 12 fps"):
    """Take B (the live hero): dimetric sphere above an Alice -> Bob photon stream across the full width.

    Layout grid: 48 px side margins, label above value, every label in 3 px pixel type.
    """
    photons, frames = sim.run()
    W, H = 960, 568
    tl = Timeline(W, H, len(frames), sim.FPS, [], rest=rest_frame(photons))
    header(tl, sub, px=LABEL)
    cam = Camera(480, 240, 132, elev=30, azim=45)
    add_sphere(tl, cam, photons, frames, source)

    line_y, x_a, x_b = 444, 88, 872
    lw = 5 * LABEL                                       # width of one label glyph
    tl.add(text_rects("alice", 48, 404, LABEL), "faint")
    tl.add(text_rects("bob", 912 - text_width("bob", LABEL), 404, LABEL), "faint")
    tl.add([(48, line_y - 8, 16, 16)])                   # source, on the left margin
    tl.add([(896, line_y - 8, 16, 16)])                  # detector, on the right margin...
    tl.add([(900, line_y - 4, 8, 8)], "faint")           # ...with a window
    # Fibre: a sampled dotted line between them
    tl.add([(x, line_y - 1, 4, 2) for x in range(x_a, x_b, 12)], "faint")

    for p in photons:
        s = p.index * SLOT
        m = s + SLOT - 1
        glyph = POL[(p.alice_basis, p.alice_bit)]
        for step in range(SLOT - 1):
            # Photon hops along the fibre, one sampled position per frame
            x = x_a + (step + 0.5) / (SLOT - 1) * (x_b - x_a - 20)
            tl.add(text_rects(glyph, int(x), line_y - 14, 4), "ink", s + step, s + step + 1, ghost=True)
        # Basis row under each end: Alice's basis + state, Bob's basis + result
        flicker(tl, text_rects(sim.BASIS_GLYPH[p.alice_basis], 48, 476, LABEL), "ink", s, s + SLOT)
        tl.add(text_rects(sim.STATE_LABEL[(p.alice_basis, p.alice_bit)], 48 + lw + 12, 476, LABEL),
               "ink", s, s + SLOT)
        flicker(tl, text_rects(sim.BASIS_GLYPH[p.bob_basis], 912 - lw, 476, LABEL), "ink", s + 2, s + SLOT)
        tl.add(text_rects(str(p.bob_bit), 912 - 2 * lw - 12, 476, LABEL), "ink", m, s + SLOT)
        tl.add([(896, line_y - 8, 16, 16)], "acc" if p.sifted else "ink", m, m + 1, ghost=True)

    tl.add(text_rects("raw key", 48, 524, LABEL), "faint")
    add_key(tl, photons, 480 - (len(photons) * 28) // 2, 520, spacing=28)
    sifted_counter(tl, photons, 912, 524, right=True)
    return tl


def divider(width=960, height=40, frames=48, samples=60):
    """A slowly travelling sine, sampled like an oscilloscope: one dot per sample point."""
    tl = Timeline(width, height, frames, sim.FPS, [], rest=0)
    xs = (np.arange(samples) + 0.5) * width / samples
    wavelength = width / 4
    # Hann window so the wave fades in and out at the edges
    env = np.sin(np.pi * xs / width) ** 2
    for k in range(frames):
        # y = A sin(2π(x - vt)/λ): moves one wavelength per loop, so the loop is seamless
        y = height / 2 - (height / 2 - 6) * env * np.sin(2 * np.pi * (xs / wavelength - k / frames))
        rects = []
        for x, yy in zip(xs, y):
            rects += block(x, round(yy / 2) * 2, 4)
        tl.add(rects, "ink", k, k + 1)
    return tl


def stardust(width=960, height=160):
    """'stardust' in scanline pixel type plus an underscore cursor; the letters type in once."""
    text, px = "stardust", 10
    x0, y0 = 48, (height - 7 * px) // 2
    letters = [scanline_text_rects(ch, x0 + i * 6 * px, y0, px, line=3, gap=5) for i, ch in enumerate(text)]

    def cursor(i):
        # The bottom pixel row of a cell as two scanlines: an underscore, quieter than a full block
        x = x0 + i * 6 * px
        return [(x, y0 + 6 * px + 1, 5 * px, 3), (x, y0 + 6 * px + 6, 5 * px, 3)]
    return letters, cursor
