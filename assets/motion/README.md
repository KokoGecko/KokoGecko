# motion

Slot for Claude Motion exports (MP4 / GIF), if access comes later.

To use one as the hero, run it through the same scanline renderer so it matches the rest of the page:

```bash
python tools/scanline/clip.py assets/motion/<file>.gif --out assets/hero-alt
```

MP4 input needs `pip install imageio[ffmpeg]`. Keep source clips around 4 s, on a plain white background, with the subject centred.
