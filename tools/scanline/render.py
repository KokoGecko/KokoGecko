"""Frame -> scanlines.

1. Draw the scene as a greyscale "darkness" image (0 = paper, 1 = full ink) at SS x resolution.
2. Cut the image into horizontal bands PITCH px tall and cells CELL px wide.
3. Each cell's mean darkness sets the thickness of a black rule (0..MAX_LINE px),
   quantised to whole pixels, so the picture becomes chunky horizontal blocks.
4. Neighbouring cells of equal thickness merge into one rectangle (smaller files).
"""
import numpy as np
from PIL import Image, ImageDraw

SS = 2          # supersampling factor for the darkness image
PITCH = 6       # px between scanlines
CELL = 4        # px width of one block
MAX_LINE = 5    # thickest rule, leaves a 1 px gap between rows
GAMMA = 0.7     # < 1 lifts thin strokes so they survive sampling


class Camera:
    """Orthographic camera looking at the Bloch sphere from elevation `elev`, azimuth `azim` (degrees)."""

    def __init__(self, cx, cy, radius, elev, azim):
        e, a = np.radians(elev), np.radians(azim)
        self.c = np.array([cx, cy], float)
        self.radius = radius
        # d points from the sphere centre toward the viewer
        self.d = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
        self.right = np.array([-np.sin(a), np.cos(a), 0.0])
        self.up = np.cross(self.d, self.right)

    def project(self, p):
        """Bloch-space point -> (screen x, screen y, depth). depth > 0 is the front half."""
        p = np.asarray(p, float)
        return (self.c[0] + self.radius * (p @ self.right),
                self.c[1] - self.radius * (p @ self.up),
                float(p @ self.d))


def great_circle(normal_axis, n=180):
    """Points on the unit circle perpendicular to one of the axes 'x', 'y', 'z'."""
    t = np.linspace(0, 2 * np.pi, n + 1)
    c, s, z = np.cos(t), np.sin(t), np.zeros_like(t)
    return {"z": np.stack([c, s, z], 1), "x": np.stack([z, c, s], 1), "y": np.stack([c, z, s], 1)}[normal_axis]


def latitude(z, n=120):
    """Circle of constant height z: the path of a state precessing about z."""
    rho = np.sqrt(max(0.0, 1 - z * z))
    t = np.linspace(0, 2 * np.pi, n + 1)
    return np.stack([rho * np.cos(t), rho * np.sin(t), np.full_like(t, z)], 1)


class Canvas:
    """A darkness image at SS x scale. Later strokes win where they overlap."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = Image.new("L", (w * SS, h * SS), 0)
        self.draw = ImageDraw.Draw(self.img)

    @staticmethod
    def _v(dark):
        return int(round(255 * min(max(dark, 0.0), 1.0)))

    def line(self, pts, width, dark):
        pts = [(x * SS, y * SS) for x, y in pts]
        self.draw.line(pts, fill=self._v(dark), width=max(1, int(round(width * SS))), joint="curve")

    def curve(self, cam, pts, width, front, back, dashed=False):
        """Draw a 3D polyline; segments behind the sphere centre use the lighter `back` darkness."""
        proj = [cam.project(p) for p in pts]
        for i in range(len(proj) - 1):
            if dashed and (i // 3) % 2:
                continue
            (x0, y0, d0), (x1, y1, d1) = proj[i], proj[i + 1]
            self.line([(x0, y0), (x1, y1)], width, front if (d0 + d1) >= 0 else back)

    def shade_sphere(self, cam, inner, rim):
        """Glass-like shading: almost clear in the middle, darker toward the rim (Fresnel-ish)."""
        yy, xx = np.mgrid[0:self.h * SS, 0:self.w * SS] / SS
        rho = np.hypot(xx - cam.c[0], yy - cam.c[1]) / cam.radius
        shade = np.where(rho <= 1, inner + (rim - inner) * rho ** 10, 0)
        a = np.asarray(self.img, float) / 255
        self.img = Image.fromarray((np.maximum(a, shade) * 255).astype(np.uint8))
        self.draw = ImageDraw.Draw(self.img)

    def array(self):
        return np.asarray(self.img, float) / 255


def scanlines(dark, pitch=PITCH, cell=CELL, max_line=MAX_LINE, gamma=GAMMA):
    """Darkness image (at SS scale) -> list of (x, y, w, h) rectangles in 1x pixels."""
    H, W = dark.shape
    bh, bw = pitch * SS, cell * SS
    rows, cols = H // bh, W // bw
    cells = dark[:rows * bh, :cols * bw].reshape(rows, bh, cols, bw).mean(axis=(1, 3))
    # Brightness -> rule thickness, quantised to whole pixels
    thick = np.round(max_line * np.power(cells, gamma)).astype(int)
    rects = []
    for r in range(rows):
        row, c = thick[r], 0
        while c < cols:
            t = row[c]
            if t == 0:
                c += 1
                continue
            start = c
            while c < cols and row[c] == t:
                c += 1
            y = r * pitch + (pitch - t) // 2  # centre the rule in its band
            rects.append((start * cell, y, (c - start) * cell, int(t)))
    return rects
