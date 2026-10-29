"""Colours and descriptions, in one place.

faint = opacity of secondary text over the background (about 4.5:1 contrast in both modes).
ghost = opacity of the blurred previous-frame glow (stronger on paper, where gold is quieter).
"""
PAPER = {"bg": "#FAFAF7", "ink": "#111111", "faint": 0.58, "ghost": 0.32}
NIGHT = {"bg": "#0E0F11", "ink": "#E9E9E4", "faint": 0.50, "ghost": 0.16}
ACCENT = {
    "a": {"light": "#0A7A93", "dark": "#4CCBE2"},   # cold signal cyan (take A)
    "b": {"light": "#8F6C1E", "dark": "#D9B45C"},   # soft gold (take B, the live hero)
}

HERO_DESC = ("A Bloch sphere drawn in horizontal scanlines above a fibre from Alice to Bob. Every half second "
             "Alice sends a BB84 photon in the state zero, one, plus or minus; the qubit vector precesses about "
             "the vertical axis, Bob measures in a random basis, and the raw key types out along the bottom: "
             "kept bits underlined, dropped bits struck through.")
STATIC_DESC = ("A still of the BB84 scene: the qubit vector mid-precession on the equator, a photon on the fibre "
               "from Alice to Bob, and the raw key typed out so far, kept bits underlined, dropped bits struck through.")
ALT_DESC = ("The same BB84 scene, but the sphere is traced from a single AI-generated still (Higgsfield); "
            "the vector, photons and key are the simulation drawn on top.")


def palettes(take="b"):
    """{"light": {...}, "dark": {...}} for one take."""
    return {mode: {**base, "acc": ACCENT[take][mode]} for mode, base in (("light", PAPER), ("dark", NIGHT))}
