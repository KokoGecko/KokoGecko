"""Timeline -> animated SVG, static SVG and GIF.

In the SVG every Item becomes one <path>. A shared CSS keyframe per visible-duration
switches it on for exactly that many frames, with `step-end` timing (no smoothing), and
animation-delay places it in time. Repeated geometry is written once and re-used with <use>.
Ghost items are re-used one frame later as a blurred accent copy: the faint glow of the
previous frame. Each ghost gets its own small blur region, so only the 1-3 ghosts visible
in a frame are ever blurred.
"""
from collections import defaultdict
from xml.sax.saxutils import escape, quoteattr

from PIL import Image, ImageDraw, ImageFilter

from timeline import Item

GHOST_BLUR = 2.5
BLUR_PAD = 8  # px around a ghost that the blur may spill into


def _path(rects):
    """Rectangles -> compact path data using relative moves between rectangles."""
    out, px, py = [], 0, 0
    for i, (x, y, w, h) in enumerate(rects):
        out.append(f"M{x} {y}" if i == 0 else f"m{x - px} {y - py}")
        out.append(f"h{w}v{h}h{-w}z")
        px, py = x, y
    return "".join(out)


def _fmt(v):
    return f"{v:.4f}".rstrip("0").rstrip(".") or "0"


def _bbox(rects):
    x0 = min(r[0] for r in rects) - BLUR_PAD
    y0 = min(r[1] for r in rects) - BLUR_PAD
    x1 = max(r[0] + r[2] for r in rects) + BLUR_PAD
    y1 = max(r[1] + r[3] for r in rects) + BLUR_PAD
    return x0, y0, x1 - x0, y1 - y0


def _merge(items):
    """Join items that share colour, timing and ghost flag into one path each."""
    groups = defaultdict(list)
    for it in items:
        groups[(it.color, it.on, it.off, it.ghost)].extend(it.rects)
    return [Item(r, *k) for k, r in groups.items()]


def _open_svg(w, h, title, desc):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'shape-rendering="crispEdges" role="img" aria-labelledby="title desc">'
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc>')


def write_svg(tl, palette, path, title, desc, static=False, background=True):
    n, period = tl.frames, tl.frames / tl.fps
    items = _merge(tl.items)
    if static:
        items = [it for it in items if it.on <= tl.rest < it.off]

    css = [f".i{{fill:{palette['ink']}}}.a{{fill:{palette['acc']}}}"
           f".f{{fill:{palette['ink']};fill-opacity:{palette['faint']}}}"]
    if not static:
        css.append(f".t{{visibility:hidden;animation:{_fmt(period)}s step-end infinite}}")
        for dur in sorted({it.off - it.on for it in items if it.off - it.on < n}):
            css.append(f".k{dur}{{animation-name:k{dur}}}"
                       f"@keyframes k{dur}{{0%{{visibility:visible}}{_fmt(100 * dur / n)}%,100%{{visibility:hidden}}}}")
        # Reduced motion: freeze on the rest frame and drop the ghost
        css.append("@media (prefers-reduced-motion:reduce){.t{animation:none}.r{visibility:visible}.g{display:none}}")

    # Geometry that appears more than once (or is ghosted) gets an id and is re-used
    seen = defaultdict(int)
    for it in items:
        seen[_path(it.rects)] += 1
    ids, body, ghosts, filters = {}, [], [], []
    cls = {"ink": "i", "acc": "a", "faint": "f"}

    def shape(d, reuse):
        if d in ids:
            return f'<use href="#{ids[d]}"/>'
        if not reuse:
            return f'<path d="{d}"/>'
        ids[d] = f"q{len(ids)}"
        return f'<path id="{ids[d]}" d="{d}"/>'

    for it in items:
        d = _path(it.rects)
        reuse = seen[d] > 1 or (it.ghost and not static)
        dur = it.off - it.on
        if static or dur >= n:
            body.append(f'<g class="{cls[it.color]}">{shape(d, reuse)}</g>')
            continue
        rest = " r" if it.on <= tl.rest < it.off else ""
        body.append(f'<g class="t k{dur} {cls[it.color]}{rest}" style="animation-delay:{_fmt(it.on / tl.fps)}s">'
                    f'{shape(d, reuse)}</g>')
        if it.ghost:
            fid = f"b{len(filters)}"
            x, y, w, h = _bbox(it.rects)
            filters.append(f'<filter id="{fid}" filterUnits="userSpaceOnUse" x="{x}" y="{y}" width="{w}" '
                           f'height="{h}"><feGaussianBlur stdDeviation="{GHOST_BLUR}"/></filter>')
            ghosts.append(f'<use class="t k{dur}" href="#{ids[d]}" filter="url(#{fid})" '
                          f'style="animation-delay:{_fmt(((it.on + 1) % n) / tl.fps)}s"/>')

    defs = f'<defs>{"".join(filters)}</defs>' if filters else ""
    ghost_layer = (f'<g class="g" fill="{palette["acc"]}" fill-opacity="{palette["ghost"]}" '
                   f'shape-rendering="auto">{"".join(ghosts)}</g>') if ghosts else ""
    svg = (_open_svg(tl.width, tl.height, title, desc) + f'<style>{"".join(css)}</style>{defs}'
           + (f'<rect width="100%" height="100%" fill="{palette["bg"]}"/>' if background else "")
           + f'{ghost_layer}{"".join(body)}</svg>')
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    return len(svg.encode())


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def render_frame(tl, palette, k, scale=1.0):
    """One frame as a PIL image, drawn from the same rectangles as the SVG."""
    W, H = tl.width, tl.height
    bg, ink, acc = _hex(palette["bg"]), _hex(palette["ink"]), _hex(palette["acc"])
    colors = {"ink": ink, "acc": acc, "faint": _mix(bg, ink, palette["faint"])}
    im = Image.new("RGB", (W, H), bg)

    # Ghost: the previous frame's moving parts, blurred, in the accent colour
    prev = (k - 1) % tl.frames
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    for it in tl.items:
        if it.ghost and it.on <= prev < it.off:
            for x, y, w, h in it.rects:
                md.rectangle([x, y, x + w - 1, y + h - 1], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(GHOST_BLUR)).point(lambda v: int(v * palette["ghost"]))
    im.paste(Image.new("RGB", (W, H), acc), (0, 0), mask)

    d = ImageDraw.Draw(im)
    for it in tl.items:
        if it.on <= k < it.off:
            for x, y, w, h in it.rects:
                d.rectangle([x, y, x + w - 1, y + h - 1], fill=colors[it.color])
    if scale != 1.0:
        im = im.resize((round(W * scale), round(H * scale)), Image.LANCZOS)
    return im


def write_gif(tl, palette, path, scale=1.0, step=1):
    """Animated GIF fallback (for places that cannot animate SVG). `step` > 1 drops frames."""
    frames = [render_frame(tl, palette, k, scale).quantize(colors=32, dither=Image.Dither.NONE)
              for k in range(0, tl.frames, step)]
    # GIF timing is in 1/100 s; alternate 80/80/90 ms so the average is exactly 1/12 s
    base = 1000 * step / tl.fps
    durations = [int(base // 10 * 10) + (10 if (i % 3 == 2) else 0) for i in range(len(frames))]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=durations, loop=0,
                   optimize=True, disposal=1)


def write_png(tl, palette, path, k=None, scale=1.0):
    render_frame(tl, palette, tl.rest if k is None else k, scale).save(path, optimize=True)


def write_typing_svg(letters, cursor, palette, path, width, height, title, static=False,
                     step=0.25, start=0.4, blinks=5):
    """Type-once SVG: letters appear one by one, the accent cursor blinks a few times, then holds."""
    n = len(letters)
    css = f".i{{fill:{palette['ink']}}}.a{{fill:{palette['acc']}}}"
    parts = []
    if static:
        parts = [f'<path class="i" d="{_path(sum(letters, []))}"/>', f'<path class="a" d="{_path(cursor(n))}"/>']
    else:
        done = start + (n + 1) * step
        css += (".l,.c,.b{visibility:hidden}"
                ".l{animation:on .01s step-end forwards}"
                f".c{{animation:on {step}s step-end}}"
                f".b{{animation:blink 1s step-end {blinks},on .01s step-end {_fmt(done + blinks)}s forwards}}"
                "@keyframes on{0%,100%{visibility:visible}}"
                "@keyframes blink{0%{visibility:visible}50%,100%{visibility:hidden}}"
                "@media (prefers-reduced-motion:reduce){.l,.b{animation:none;visibility:visible}.c{animation:none}}")
        for i, rects in enumerate(letters):
            t = start + (i + 1) * step
            parts.append(f'<path class="i l" style="animation-delay:{_fmt(t)}s" d="{_path(rects)}"/>')
            parts.append(f'<path class="a c" style="animation-delay:{_fmt(t - step)}s" d="{_path(cursor(i))}"/>')
        parts.append(f'<path class="a b" style="animation-delay:{_fmt(done)}s" d="{_path(cursor(n))}"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
           f'height="{height}" shape-rendering="crispEdges" role="img" aria-label={quoteattr(title)}>'
           f'<title>{escape(title)}</title><style>{css}</style>{"".join(parts)}</svg>')
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    return len(svg.encode())
