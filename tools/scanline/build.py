"""Regenerate the README images. Run from the repo root.

    python tools/scanline/build.py                    # hero (take B), tagline, divider -> assets/hero
    python tools/scanline/build.py --gif              # also the GIF fallbacks
    python tools/scanline/build.py --take a --out x   # the other take, into a scratch folder
"""
import argparse
import os

import scenes
from export import write_gif, write_svg, write_typing_svg
from theme import HERO_DESC, STATIC_DESC, palettes

TITLE = "KokoGecko: BB84 on a Bloch sphere"


def build(out, take, gif):
    os.makedirs(out, exist_ok=True)
    hero = {"a": scenes.hero_a, "b": scenes.hero_b}[take]()
    div = scenes.divider()
    letters, cursor = scenes.stardust()
    for mode, pal in palettes(take).items():
        f = lambda name: os.path.join(out, name)
        sizes = {
            f"hero-{mode}.svg": write_svg(hero, pal, f(f"hero-{mode}.svg"), TITLE, HERO_DESC),
            f"hero-{mode}-static.svg": write_svg(hero, pal, f(f"hero-{mode}-static.svg"), TITLE, STATIC_DESC, static=True),
            f"divider-{mode}.svg": write_svg(div, pal, f(f"divider-{mode}.svg"), "divider", "A sampled sine wave.",
                                             background=False),
            f"divider-{mode}-static.svg": write_svg(div, pal, f(f"divider-{mode}-static.svg"), "divider",
                                                    "A sampled sine wave.", static=True, background=False),
            f"stardust-{mode}.svg": write_typing_svg(letters, cursor, pal, f(f"stardust-{mode}.svg"), 960, 160, "stardust"),
            f"stardust-{mode}-static.svg": write_typing_svg(letters, cursor, pal, f(f"stardust-{mode}-static.svg"),
                                                            960, 160, "stardust", static=True),
        }
        if gif:
            write_gif(hero, pal, f(f"hero-{mode}.gif"))
            sizes[f"hero-{mode}.gif"] = os.path.getsize(f(f"hero-{mode}.gif"))
        for name, size in sizes.items():
            print(f"{name:28s} {size / 1024:8.1f} KB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build the README hero, tagline and divider.")
    ap.add_argument("--take", default="b", choices=["a", "b"], help="hero layout (b is the live one)")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "..", "assets", "hero"),
                    help="output folder (default assets/hero; note --take a writes the same file names)")
    ap.add_argument("--gif", action="store_true", help="also write hero GIFs (for places that cannot animate SVG)")
    args = ap.parse_args()
    build(args.out, args.take, args.gif)
