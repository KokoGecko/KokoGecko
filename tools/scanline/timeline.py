"""The data model shared by scenes (which fill it) and export (which writes it).

A Timeline is a list of Items. Each Item is a set of rectangles in one colour that is
visible from frame `on` up to (not including) frame `off`. That one idea covers everything:
  - static art:      on=0, off=N
  - one video frame: on=k, off=k+1
  - a typed bit:     on=k, off=N   (appears and stays)
Items marked `ghost` are shown again one frame later as a blurred accent copy.
"""
from dataclasses import dataclass


@dataclass
class Item:
    rects: list         # (x, y, w, h) in whole pixels
    color: str          # "ink", "acc" or "faint"
    on: int
    off: int
    ghost: bool = False


@dataclass
class Timeline:
    width: int
    height: int
    frames: int
    fps: int
    items: list
    rest: int           # frame shown when motion is reduced / in the static export

    def add(self, rects, color="ink", on=0, off=None, ghost=False):
        if rects:
            self.items.append(Item(list(rects), color, on, self.frames if off is None else off, ghost))
