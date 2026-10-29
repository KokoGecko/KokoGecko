"""Bloch sphere + BB84 physics.

A qubit state |psi> = cos(theta/2)|0> + e^{i phi} sin(theta/2)|1> is drawn as the
unit vector r = (sin theta cos phi, sin theta sin phi, cos theta) on the Bloch sphere.

The BB84 run is a fixed-seed random sequence, so regenerating the assets always
produces the identical loop.
"""
from dataclasses import dataclass, field

import numpy as np

FPS = 12                 # the hero steps at 12 frames per second
FRAMES_PER_PHOTON = 6    # one photon every 0.5 s
N_PHOTONS = 14           # photons sent per loop
HOLD_SLOTS = 2           # quiet slots at the end where the finished key is shown
SEED = 8                 # fixed seed: the loop is identical every time it is built

# Basis index -> measurement axis on the sphere.
# 0 = rectilinear "+" basis {|0>, |1>}  (z axis)
# 1 = diagonal    "x" basis {|+>, |->}  (x axis)
AXES = (np.array([0.0, 0.0, 1.0]), np.array([1.0, 0.0, 0.0]))
BASIS_GLYPH = ("+", "×")
STATE_LABEL = {(0, 0): "|0⟩", (0, 1): "|1⟩", (1, 0): "|+⟩", (1, 1): "|−⟩"}

# Precession steps shown before Bob measures. Bob measures at t = 5/12 s.
PRECESS_STEPS = FRAMES_PER_PHOTON - 1
T_MEASURE = PRECESS_STEPS / FPS
# Precession frequency chosen so the state makes exactly one turn by the time Bob measures,
# so the collapse is drawn at Alice's original azimuth. (After one turn U = e^{-iπσz} = -1:
# the state picks up a global sign, which is unobservable, so the Bloch vector is unchanged.)
OMEGA = 2 * np.pi / T_MEASURE


def bloch_vector(theta, phi):
    # r = (sin θ cos φ, sin θ sin φ, cos θ): the point on the sphere for |psi>
    return np.array([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)])


def prepare(bit, basis):
    # Alice's state is the +axis eigenstate for bit 0 and the -axis eigenstate for bit 1
    return (1 - 2 * bit) * AXES[basis]


def precess(r, t):
    # H = (ħω/2) σz rotates r about z by φ = ωt; z is unchanged.
    # (Larmor precession for a spin; for a photon in fibre the same z-rotation is Faraday rotation.)
    phi = OMEGA * t
    c, s = np.cos(phi), np.sin(phi)
    return np.array([c * r[0] - s * r[1], s * r[0] + c * r[1], r[2]])


def measure(r, basis, t, rng):
    # Bob measures in the frame that co-rotates with H: his axis is the lab axis turned by ωt.
    # A real receiver does the same by compensating the channel's known rotation.
    n = precess(AXES[basis], t)
    # Born rule on the sphere: P(+n) = |<+n|psi>|^2 = (1 + r·n) / 2
    p_plus = (1.0 + float(r @ n)) / 2.0
    bit = 0 if rng.random() < p_plus else 1
    # Projective measurement: the state collapses to the eigenstate that was found
    return bit, (1 - 2 * bit) * n


@dataclass
class Photon:
    index: int
    alice_bit: int
    alice_basis: int
    bob_basis: int
    bob_bit: int
    state: np.ndarray      # Alice's prepared Bloch vector
    collapsed: np.ndarray  # Bloch vector after Bob's measurement

    @property
    def sifted(self):
        # Sifting: Alice and Bob publicly compare bases and keep only matching ones
        return self.alice_basis == self.bob_basis


@dataclass
class Frame:
    index: int
    slot: int              # which 0.5 s slot this frame is in
    step: int              # 0..5 inside the slot
    photon: "Photon | None"
    r: np.ndarray          # vector drawn this frame
    trail: list = field(default_factory=list)  # earlier vectors in this slot, newest last
    measured: bool = False # True on the frame where Bob measures


def run(seed=SEED, n_photons=N_PHOTONS, hold_slots=HOLD_SLOTS):
    """Return (photons, frames) for one loop of the animation."""
    rng = np.random.default_rng(seed)
    photons = []
    for i in range(n_photons):
        # Draw order is fixed so the same seed always gives the same run
        a_bit, a_basis, b_basis = (int(v) for v in rng.integers(0, 2, size=3))
        state = prepare(a_bit, a_basis)
        arriving = precess(state, T_MEASURE)
        b_bit, collapsed = measure(arriving, b_basis, T_MEASURE, rng)
        photons.append(Photon(i, a_bit, a_basis, b_basis, b_bit, state, collapsed))

    frames = []
    last = photons[-1].collapsed
    for slot in range(n_photons + hold_slots):
        p = photons[slot] if slot < n_photons else None
        start = p.state if p else last
        history = []
        for step in range(FRAMES_PER_PHOTON):
            k = slot * FRAMES_PER_PHOTON + step
            if p and step == PRECESS_STEPS:
                frames.append(Frame(k, slot, step, p, p.collapsed, history[-3:], measured=True))
                continue
            # During a photon, time restarts at Alice's preparation; in the hold it runs on continuously
            t = step if p else (slot - n_photons) * FRAMES_PER_PHOTON + step
            r = precess(start, t / FPS)
            frames.append(Frame(k, slot, step, p, r, history[-3:]))
            history.append(r)
    return photons, frames


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
    photons, frames = run()
    for p in photons:
        print(p.index, "alice", p.alice_bit, BASIS_GLYPH[p.alice_basis], STATE_LABEL[(p.alice_basis, p.alice_bit)],
              "bob", BASIS_GLYPH[p.bob_basis], p.bob_bit, "sifted" if p.sifted else "-")
    s = [p for p in photons if p.sifted]
    errors = sum(p.alice_bit != p.bob_bit for p in s)
    print(f"{len(s)}/{len(photons)} sifted, QBER {errors / max(len(s), 1):.2f}, {len(frames)} frames")
