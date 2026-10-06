"""Offline stand-in for a vision model. Finds the dominant colours in a photo/sketch with Pillow.
For the bundled sample images it reads the 'true' spec stored in the PNG metadata, simulating a perfect model."""
import io, json, hashlib
from PIL import Image

NAMED = {
    "red": (200, 20, 40), "crimson": (123, 30, 43), "orange": (232, 112, 42), "yellow": (242, 194, 48),
    "lime green": (155, 226, 45), "green": (31, 110, 50), "sky blue": (95, 168, 211), "blue": (29, 47, 111),
    "purple": (91, 42, 134), "pink": (231, 84, 128), "brown": (120, 72, 40), "silver": (183, 188, 194),
    "grey": (90, 94, 100), "black": (20, 20, 20), "white": (245, 245, 240),
}


def _nearest(rgb):
    return min(NAMED, key=lambda n: sum((a - b) ** 2 for a, b in zip(rgb, NAMED[n])))


def embedded_spec(data: bytes):
    try:
        im = Image.open(io.BytesIO(data))
        raw = im.info.get("spec")
        return json.loads(raw) if raw else None
    except Exception:
        return None


def dominant_colours(data: bytes, k: int = 6):
    im = Image.open(io.BytesIO(data)).convert("RGB")
    im.thumbnail((160, 160))
    q = im.quantize(colors=k + 4, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)
    total = sum(c for c, _ in counts)
    out = {}
    for c, idx in counts:
        rgb = tuple(pal[idx * 3 : idx * 3 + 3])
        if min(rgb) > 225:  # paper background
            continue
        name = _nearest(rgb)
        out[name] = out.get(name, 0) + c / total
    return sorted(out.items(), key=lambda x: -x[1])


def seeded_choice(data: bytes, options, salt=""):
    h = int(hashlib.md5(data[:4096] + salt.encode()).hexdigest(), 16)
    return options[h % len(options)]
